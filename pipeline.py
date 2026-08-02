"""HeatIndex Pipeline
采集广发纳指ETF(159941)每日价格 + 东方财富纳斯达克吧(zsgjndx)热度 → 输出 dashboard_data.json
独立脚本，供 GitHub Actions 调用。
帖子数据持久化：data/guba_posts_zsgjndx.json，增量累积不丢弃。
"""

import json
import math
import os
import re
import time
import random
from datetime import datetime, timedelta

import pandas as pd
import requests

# ═══════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════
SYMBOL = "159941"
SYMBOL_NAME = "广发纳指ETF"
GUBA_CODE = "zsgjndx"

BUZZ_SCALE_MIN = 0
BUZZ_SCALE_MAX = 100

WEIGHT_READ = 0.4
WEIGHT_REPLY = 0.6
HALF_LIFE_DAYS = 7

HEAT_CONFIG_FILE = "heat_config.json"

GUBA_MAX_PAGES = 30

DATA_DIR = "data"
OUTPUT_FILE = "dashboard_data.json"
POSTS_FILE = f"guba_posts_{GUBA_CODE}.json"

# ═══════════════════════════════════════════════════
# 反检测请求头
# ═══════════════════════════════════════════════════
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
]


def _browser_headers(referer="https://guba.eastmoney.com"):
    ua = random.choice(_USER_AGENTS)
    version = ua.split("Chrome/")[1].split(".")[0]
    return {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
        "Referer": referer,
        "sec-ch-ua": f'"Not_A Brand";v="8", "Chromium";v="{version}", "Google Chrome";v="{version}"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
    }


# ═══════════════════════════════════════════════════
# 帖子持久化
# ═══════════════════════════════════════════════════

def load_posts() -> list[dict]:
    """加载已持久化的帖子列表。"""
    path = os.path.join(DATA_DIR, POSTS_FILE)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_posts(posts: list[dict]):
    """持久化帖子列表。"""
    os.makedirs(DATA_DIR, exist_ok=True)
    path = os.path.join(DATA_DIR, POSTS_FILE)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)


def post_key(p: dict) -> str:
    """唯一键：日期 + 阅读数 + 回复数（股吧无独立帖子ID）。"""
    return f"{p['post_date']}|{p['read_count']}|{p['reply_count']}"


def merge_posts(existing: list[dict], new: list[dict]) -> list[dict]:
    """合并去重，保留已有帖子，追加新帖子。"""
    seen = {post_key(p) for p in existing}
    added = 0
    for p in new:
        if post_key(p) not in seen:
            existing.append(p)
            seen.add(post_key(p))
            added += 1
    print(f"  [帖子] 已有 {len(existing) - added} 条，新增 {added} 条，合计 {len(existing)} 条")
    return existing


# ═══════════════════════════════════════════════════
# 热度配置持久化（动态归一化）
# ═══════════════════════════════════════════════════

def load_heat_config() -> dict:
    """加载热度配置，不存在时返回默认值。"""
    path = os.path.join(DATA_DIR, HEAT_CONFIG_FILE)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"max_raw_score": 1000}


def save_heat_config(config: dict):
    """持久化热度配置。"""
    os.makedirs(DATA_DIR, exist_ok=True)
    path = os.path.join(DATA_DIR, HEAT_CONFIG_FILE)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


# ═══════════════════════════════════════════════════
# 腾讯财经日K线 API
# ═══════════════════════════════════════════════════
KLINE_URL = "http://web.ifzq.gtimg.cn/appstock/app/fqkline/get"


def get_stock_daily(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """通过腾讯财经 API 获取前复权日K线。
    返回 DataFrame，列: date, open, close, high, low, volume, amount。
    """
    prefix = "sh" if symbol.startswith("6") else "sz"

    def _fmt(d: str) -> str:
        if len(d) == 8:
            return f"{d[:4]}-{d[4:6]}-{d[6:]}"
        return d

    params = f"{prefix}{symbol},day,{_fmt(start_date)},{_fmt(end_date)},2000,qfq"

    for retry in range(3):
        try:
            resp = requests.get(
                f"{KLINE_URL}?param={params}",
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=20,
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("code") != 0:
                raise ValueError(f"API 错误: {data.get('msg')}")

            key = f"{prefix}{symbol}"
            raw = data.get("data", {}).get(key, {}).get("qfqday", [])
            if not raw:
                print(f"  [腾讯] {symbol} 无数据")
                return pd.DataFrame()

            rows = []
            for item in raw:
                if not isinstance(item, list) or len(item) < 6:
                    continue
                dt_str = item[0]
                dt = f"{dt_str[:4]}-{dt_str[4:6]}-{dt_str[6:]}" if len(dt_str) == 8 else dt_str
                rows.append({
                    "date": dt,
                    "open": float(item[1]),
                    "close": float(item[2]),
                    "high": float(item[3]),
                    "low": float(item[4]),
                    "volume": int(float(item[5])),
                    "amount": 0,
                })
            return pd.DataFrame(rows)

        except Exception as e:
            wait = (retry + 1) * 3
            print(f"  [腾讯] 第{retry + 1}次失败: {e}，{wait}s后重试...")
            time.sleep(wait)

    print(f"  [腾讯] 重试3次均失败，返回空数据")
    return pd.DataFrame()


# ═══════════════════════════════════════════════════
# 股吧爬虫
# ═══════════════════════════════════════════════════

def fetch_guba_posts(code: str, start_date: str) -> list[dict]:
    """爬取股吧帖子，翻页直到日期早于 start_date 或达到页数上限。
    start_date 格式: YYYYMMDD
    """
    posts = []
    start_dt = datetime.strptime(start_date, "%Y%m%d")

    for page in range(1, GUBA_MAX_PAGES + 1):
        if page == 1:
            url = f"https://guba.eastmoney.com/list,{code}.html"
        else:
            url = f"https://guba.eastmoney.com/list,{code}_{page}.html"

        html = ""
        for retry in range(3):
            try:
                headers = _browser_headers()
                resp = requests.get(url, headers=headers, timeout=20)
                resp.encoding = "utf-8"
                html = resp.text
                break
            except Exception as e:
                wait = (retry + 1) * 3
                print(f"  [股吧] 第{page}页第{retry + 1}次失败: {e}，{wait}s后重试...")
                time.sleep(wait)
        if not html:
            print(f"  [股吧] 第{page}页重试3次均失败，跳过")
            continue

        read_pat = re.compile(r'class="read">(\d+)<', re.DOTALL)
        reply_pat = re.compile(r'class="reply">(\d+)<', re.DOTALL)
        date_pat = re.compile(r'class="update">(\d{2}-\d{2}\s+\d{2}:\d{2})<', re.DOTALL)

        reads = read_pat.findall(html)
        replies = reply_pat.findall(html)
        dates_raw = date_pat.findall(html)

        page_posts = 0
        reached_start = False

        for i in range(min(len(reads), len(replies), len(dates_raw))):
            date_str = dates_raw[i].strip()
            try:
                dt = datetime.strptime(date_str, "%m-%d %H:%M")
                dt = dt.replace(year=datetime.now().year)
            except ValueError:
                continue

            if dt < start_dt:
                reached_start = True
                break

            posts.append({
                "read_count": int(reads[i]),
                "reply_count": int(replies[i]),
                "post_date": dt.strftime("%Y-%m-%d"),
            })
            page_posts += 1

        print(f"  [股吧] 第{page}页 → {page_posts} 条帖子")

        if reached_start or page_posts < 40:
            break

        time.sleep(random.uniform(1.0, 2.0))

    print(f"  [股吧] 本轮抓取 {len(posts)} 条帖子")
    return posts


# ═══════════════════════════════════════════════════
# 热度计算（动态归一化，0-100+ 标度）
# ═══════════════════════════════════════════════════

def calc_raw_score(posts: list[dict], target_date: str) -> float:
    """计算指定日期的原始得分（未归一化）。"""
    target_dt = datetime.strptime(target_date, "%Y-%m-%d")
    total_score = 0.0

    for p in posts:
        post_dt = datetime.strptime(p["post_date"], "%Y-%m-%d")
        days_ago = (target_dt - post_dt).days
        if days_ago < 0:
            continue
        decay = 2 ** (-days_ago / HALF_LIFE_DAYS)
        heat = p["read_count"] * WEIGHT_READ + p["reply_count"] * WEIGHT_REPLY
        total_score += heat * decay

    return total_score


def calc_buzz_index(total_score: float, max_raw_score: float) -> float | None:
    """将原始得分归一化为 0-100+ 热度指数。
    total_score == 0 时返回 None，表示无数据。
    """
    if total_score == 0:
        return None

    log_score = math.log1p(total_score)
    denominator = math.log1p(max_raw_score * 1.5)
    buzz = min(log_score / denominator * BUZZ_SCALE_MAX, BUZZ_SCALE_MAX)
    return round(buzz, 1)


def calc_slopes(records: list[dict]):
    """为每个交易日计算 5 日滚动线性回归斜率。
    对每个交易日，取最近 5 个交易日（含当日）的收盘价做线性回归，
    斜率追加到 record["slope"]；非交易日设为 None。
    x = [0, 1, 2, 3, 4]，y = 收盘价。
    """
    # 收集所有交易日索引
    trading_indices = [i for i, r in enumerate(records) if r["is_trading"]]

    for idx in trading_indices:
        # 找到当前交易日在此列表中的位置
        pos = trading_indices.index(idx)
        # 取最近 5 个交易日（含当前）
        start_pos = max(0, pos - 4)
        window = trading_indices[start_pos:pos + 1]

        if len(window) < 2:
            records[idx]["slope"] = None
            continue

        n = len(window)
        closes = [records[i]["close"] for i in window]
        x = list(range(n))  # [0, 1, 2, 3, 4] 或更短

        sum_x = sum(x)
        sum_y = sum(closes)
        sum_xy = sum(x[i] * closes[i] for i in range(n))
        sum_x2 = sum(x[i] ** 2 for i in range(n))

        denom = n * sum_x2 - sum_x ** 2
        if denom == 0:
            records[idx]["slope"] = None
        else:
            records[idx]["slope"] = round((n * sum_xy - sum_x * sum_y) / denom, 4)


# ═══════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════

def run():
    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=365)
    end_date = end_dt.strftime("%Y%m%d")
    start_date = start_dt.strftime("%Y%m%d")

    print(f"[HeatIndex] 采集 {SYMBOL} {SYMBOL_NAME}  ×  股吧 {GUBA_CODE}")
    print(f"  日期范围: {start_date} → {end_date}")
    print(f"  热度标度: {BUZZ_SCALE_MIN}–{BUZZ_SCALE_MAX}")
    print(f"  阈值: 冰点0 / 微弱25 / 基础活跃37 / 中等50 / 高热度75 / 爆款顶流100")

    # 生成全部日历日（含非交易日）
    all_dates = []
    d = start_dt
    while d <= end_dt:
        all_dates.append(d.strftime("%Y-%m-%d"))
        d += timedelta(days=1)

    print("[HeatIndex] 步骤 1/5: 获取价格数据...")
    price_df = get_stock_daily(SYMBOL, start_date, end_date)
    price_map = {}
    if not price_df.empty:
        for _, row in price_df.iterrows():
            price_map[row["date"]] = row
    print(f"  → 获取 {len(price_map)} 条价格记录 ({len(all_dates)} 个日历日)")

    print("[HeatIndex] 步骤 2/5: 加载已有帖子 + 爬取新股吧帖子...")
    existing = load_posts()
    print(f"  → 已持久化 {len(existing)} 条帖子")

    # 爬取最近 180 天的帖子
    guba_start = (end_dt - timedelta(days=180)).strftime("%Y%m%d")
    print(f"  → 爬取范围: {guba_start} 以来（最多 {GUBA_MAX_PAGES} 页）")
    new_posts = fetch_guba_posts(GUBA_CODE, guba_start)

    merged = merge_posts(existing, new_posts)
    save_posts(merged)

    print("[HeatIndex] 步骤 3/5: 计算热度指数（动态归一化）...")
    print(f"  → 帖子池总计 {len(merged)} 条")
    # 统计帖子日期分布
    post_dates = {}
    for p in merged:
        post_dates[p["post_date"]] = post_dates.get(p["post_date"], 0) + 1
    min_pd = min(post_dates.keys()) if post_dates else "N/A"
    max_pd = max(post_dates.keys()) if post_dates else "N/A"
    print(f"  → 帖子覆盖日期: {min_pd} ~ {max_pd}")

    # 加载热度配置
    heat_config = load_heat_config()
    stored_max = heat_config.get("max_raw_score", 1000)
    print(f"  → 历史 max_raw_score: {stored_max}")

    # 第一轮：计算所有日期的原始得分，追踪新的最大值
    raw_scores = {}
    new_max_raw = 0.0
    for ds in all_dates:
        raw = calc_raw_score(merged, ds)
        raw_scores[ds] = raw
        if raw > new_max_raw:
            new_max_raw = raw
    print(f"  → 本次 max_raw_score: {new_max_raw:.2f}")

    # 更新配置文件（仅在突破历史最大值时）
    if new_max_raw > stored_max:
        heat_config["max_raw_score"] = new_max_raw
        save_heat_config(heat_config)
        print(f"  → 更新 heat_config.json: max_raw_score = {new_max_raw:.2f}")

    effective_max = max(stored_max, new_max_raw)
    print(f"  → 归一化分母: log1p({effective_max * 1.5:.2f})")

    # 第二轮：使用动态分母归一化，生成 records
    records = []
    last_close = None
    for ds in all_dates:
        total_score = raw_scores[ds]
        buzz = calc_buzz_index(total_score, effective_max)
        row = price_map.get(ds)
        if row is not None:
            last_close = float(row["close"])
            records.append({
                "date": ds,
                "buzz_index": buzz,
                "close": last_close,
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "volume": int(row["volume"]),
                "amount": float(row["amount"]),
                "is_trading": True,
            })
        else:
            records.append({
                "date": ds,
                "buzz_index": buzz,
                "close": last_close,
                "open": None, "high": None, "low": None,
                "volume": None, "amount": None,
                "is_trading": False,
            })

    print("[HeatIndex] 步骤 4/5: 计算价格斜率...")
    calc_slopes(records)

    dashboard = {
        "symbol": SYMBOL,
        "name": SYMBOL_NAME,
        "guba_code": GUBA_CODE,
        "updated": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "records": records,
        "posts_count": len(merged),
    }

    print("[HeatIndex] 步骤 5/5: 输出 dashboard_data.json...")
    out_path = os.path.join(DATA_DIR, OUTPUT_FILE)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(dashboard, f, ensure_ascii=False, indent=2)

    print(f"[HeatIndex] 完成 → {out_path} ({len(records)} 条记录, {len(merged)} 条帖子)")
    return dashboard


if __name__ == "__main__":
    run()
