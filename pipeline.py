"""HeatIndex Pipeline
采集成都银行(601838)每日价格 + 东方财富股吧热度 → 输出 dashboard_data.json
独立脚本，供 GitHub Actions 调用。
"""

import json
import math
import os
import re
import time
import html as html_mod
import random
from datetime import datetime, timedelta

import pandas as pd
import requests

# ═══════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════
SYMBOL = "601838"
SYMBOL_NAME = "成都银行"
GUBA_CODE = "601838"

BUZZ_SCALE_MIN = 0
BUZZ_SCALE_MAX = 273

WEIGHT_READ = 0.4
WEIGHT_REPLY = 0.6
HALF_LIFE_DAYS = 7

GUBA_MAX_PAGES = 10

DATA_DIR = "data"
OUTPUT_FILE = "dashboard_data.json"

# ═══════════════════════════════════════════════════
# 反检测请求头（适配自 mommy-index）
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


# 腾讯财经日K线 API
KLINE_URL = "http://web.ifzq.gtimg.cn/appstock/app/fqkline/get"

def get_stock_daily(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """通过腾讯财经 API 获取前复权日K线。
    返回 DataFrame，列: date, open, close, high, low, volume, amount。
    """
    prefix = "sh" if symbol.startswith("6") else "sz"
    # 腾讯API要求 YYYY-MM-DD
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
                # 第7项可能是分红字典，跳过
                if not isinstance(item, list) or len(item) < 6:
                    continue
                dt_str = item[0]
                # 统一为 YYYY-MM-DD
                if len(dt_str) == 8:
                    dt = f"{dt_str[:4]}-{dt_str[4:6]}-{dt_str[6:]}"
                else:
                    dt = dt_str
                rows.append({
                    "date": dt,
                    "open": float(item[1]),
                    "close": float(item[2]),
                    "high": float(item[3]),
                    "low": float(item[4]),
                    "volume": int(float(item[5])),
                    "amount": 0,  # 腾讯API无成交额
                })
            return pd.DataFrame(rows)

        except Exception as e:
            wait = (retry + 1) * 3
            print(f"  [腾讯] 第{retry+1}次失败: {e}，{wait}s后重试...")
            time.sleep(wait)

    print(f"  [腾讯] 重试3次均失败，返回空数据")
    return pd.DataFrame()


def fetch_guba_posts(code: str, start_date: str) -> list[dict]:
    """爬取股吧帖子，翻页直到日期早于 start_date。"""
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
                print(f"  [股吧] 第{page}页第{retry+1}次失败: {e}，{wait}s后重试...")
                time.sleep(wait)
        if not html:
            print(f"  [股吧] 第{page}页重试3次均失败，跳过")
            continue

        # 新结构：<tr class="listitem"> + <div class="read"> / <div class="reply"> / <div class="update">
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
                "read_count": reads[i],
                "reply_count": replies[i],
                "post_date": dt.strftime("%Y-%m-%d"),
            })
            page_posts += 1

        print(f"  [股吧] 第{page}页 → {page_posts} 条帖子")

        if reached_start or page_posts < 40:
            break

        time.sleep(random.uniform(1.0, 2.0))

    print(f"  [股吧] 总计 {len(posts)} 条帖子")
    return posts


def calc_buzz_index(posts: list[dict], target_date: str) -> float:
    target_dt = datetime.strptime(target_date, "%Y-%m-%d")
    total_score = 0.0

    for p in posts:
        post_dt = datetime.strptime(p["post_date"], "%Y-%m-%d")
        days_ago = (target_dt - post_dt).days
        if days_ago < 0:
            continue
        decay = 2 ** (-days_ago / HALF_LIFE_DAYS)
        heat = int(p["read_count"]) * WEIGHT_READ + int(p["reply_count"]) * WEIGHT_REPLY
        total_score += heat * decay

    if total_score == 0:
        return 0.0

    log_score = math.log1p(total_score)
    buzz = min(log_score / math.log1p(50000) * BUZZ_SCALE_MAX, BUZZ_SCALE_MAX)
    return round(buzz, 1)


def run():
    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=30)
    end_date = end_dt.strftime("%Y%m%d")
    start_date = start_dt.strftime("%Y%m%d")

    print(f"[HeatIndex] 采集 {SYMBOL} {SYMBOL_NAME}")
    print(f"  日期范围: {start_date} → {end_date}")

    # 生成全部日历日（含非交易日）
    all_dates = []
    d = start_dt
    while d <= end_dt:
        all_dates.append(d.strftime("%Y-%m-%d"))
        d += timedelta(days=1)

    print("[HeatIndex] 步骤 1/3: 获取价格数据...")
    price_df = get_stock_daily(SYMBOL, start_date, end_date)
    price_map = {}
    if not price_df.empty:
        for _, row in price_df.iterrows():
            price_map[row["date"]] = row
    print(f"  → 获取 {len(price_map)} 条价格记录 ({len(all_dates)} 个日历日)")

    guba_start = (end_dt - timedelta(days=60)).strftime("%Y%m%d")
    print(f"[HeatIndex] 步骤 2/3: 爬取股吧帖子（{guba_start} 以来）...")
    posts = fetch_guba_posts(GUBA_CODE, guba_start)

    print("[HeatIndex] 步骤 3/3: 计算热度指数并输出...")
    records = []
    last_close = None
    for ds in all_dates:
        buzz = calc_buzz_index(posts, ds)
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

    dashboard = {
        "symbol": SYMBOL,
        "name": SYMBOL_NAME,
        "updated": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "records": records,
    }

    os.makedirs(DATA_DIR, exist_ok=True)
    out_path = os.path.join(DATA_DIR, OUTPUT_FILE)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(dashboard, f, ensure_ascii=False, indent=2)

    print(f"[HeatIndex] 完成 → {out_path} ({len(records)} 条记录)")
    return dashboard


if __name__ == "__main__":
    run()
