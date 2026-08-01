"""HeatIndex Pipeline
采集成都银行(601838)每日价格 + 东方财富股吧热度 → 输出 dashboard_data.json
独立脚本，无内部包依赖，供 GitHub Actions 调用。
"""

import json
import math
import os
import time
import re
from datetime import datetime, timedelta

import akshare as ak
import pandas as pd
import requests

# ── 配置 ──────────────────────────────────────────────
SYMBOL = "601838"
SYMBOL_NAME = "成都银行"
GUBA_CODE = "601838"

BUZZ_SCALE_MIN = 0
BUZZ_SCALE_MAX = 273

WEIGHT_READ = 0.4
WEIGHT_REPLY = 0.6
HALF_LIFE_DAYS = 7

GUBA_PAGE_SIZE = 50
GUBA_MAX_PAGES = 10
REQUEST_INTERVAL = 1.0

DATA_DIR = "data"
OUTPUT_FILE = "dashboard_data.json"


def get_stock_daily(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """通过 AKShare 获取 A 股日线数据。"""
    df = ak.stock_zh_a_hist(
        symbol=symbol,
        period="daily",
        start_date=start_date,
        end_date=end_date,
        adjust=""
    )
    if df.empty:
        return df
    df = df.rename(columns={
        "日期": "date",
        "开盘": "open",
        "收盘": "close",
        "最高": "high",
        "最低": "low",
        "成交量": "volume",
        "成交额": "amount",
    })
    df["date"] = df["date"].astype(str)
    return df


def fetch_guba_posts(guba_code: str, start_date: str) -> list[dict]:
    """爬取东方财富股吧帖子列表，返回 [{title, read_count, reply_count, post_date}]。

    使用东方财富股吧 API，按发布时间降序遍历直到日期早于 start_date。
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "Referer": f"https://guba.eastmoney.com/list,{guba_code}.html",
    }
    posts = []
    start_dt = datetime.strptime(start_date, "%Y%m%d")

    for page in range(1, GUBA_MAX_PAGES + 1):
        url = (
            "https://guba.eastmoney.com/interface/GetData.aspx"
            f"?code={guba_code}&page={page}&pagesize={GUBA_PAGE_SIZE}"
            "&type=1&sort=1"
        )
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            resp.encoding = "utf-8"
            html = resp.text

            pattern = (
                r"<div class='articleh.*?'>.*?"
                r"<span class='l3 a3'>.*?title='阅读'>(?P<read>\d+)</span>.*?"
                r"<span class='l2 a2'>.*?title='回复'>(?P<reply>\d+)</span>.*?"
                r"<span class='l5 a5'>(?P<date>\d{4}-\d{2}-\d{2})</span>"
            )
            matches = list(re.finditer(pattern, html, re.DOTALL))

            if not matches:
                break

            for m in matches:
                post_date = m.group("date")
                try:
                    dt = datetime.strptime(post_date, "%Y-%m-%d")
                except ValueError:
                    continue
                if dt < start_dt:
                    return posts
                posts.append({
                    "read_count": int(m.group("read")),
                    "reply_count": int(m.group("reply")),
                    "post_date": post_date,
                })

            if len(matches) < GUBA_PAGE_SIZE:
                break
            time.sleep(REQUEST_INTERVAL)

        except Exception as e:
            print(f"  [股吧] 第 {page} 页请求失败: {e}")
            time.sleep(2)
            continue

    return posts


def calc_buzz_index(posts: list[dict], target_date: str) -> float:
    """计算指定日期的热度指数，含时间衰减。

    公式：对每个帖子，热度 = (read_count * WEIGHT_READ + reply_count * WEIGHT_REPLY)
           衰减因子 = 2 ^ (-days_ago / HALF_LIFE_DAYS)
           日热度 = Σ(热度 * 衰减因子)
    归一化到 [0, BUZZ_SCALE_MAX]。
    """
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

    if total_score == 0:
        return 0.0

    log_score = math.log1p(total_score)
    buzz = min(log_score / math.log1p(50000) * BUZZ_SCALE_MAX, BUZZ_SCALE_MAX)
    return round(buzz, 1)


def run():
    """主流程：采集价格 + 热度 → 输出 dashboard_data.json"""
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")

    print(f"[HeatIndex] 采集 {SYMBOL} {SYMBOL_NAME}")
    print(f"  日期范围: {start_date} → {end_date}")

    print("[HeatIndex] 步骤 1/3: 获取价格数据...")
    price_df = get_stock_daily(SYMBOL, start_date, end_date)
    print(f"  → 获取 {len(price_df)} 条价格记录")

    print("[HeatIndex] 步骤 2/3: 爬取股吧帖子...")
    guba_start = (datetime.now() - timedelta(days=37)).strftime("%Y%m%d")
    posts = fetch_guba_posts(GUBA_CODE, guba_start)
    print(f"  → 获取 {len(posts)} 条帖子")

    print("[HeatIndex] 步骤 3/3: 计算热度指数并输出...")
    records = []
    if not price_df.empty:
        price_df = price_df.sort_values("date")
        for _, row in price_df.iterrows():
            date_str = row["date"]
            buzz = calc_buzz_index(posts, date_str)
            records.append({
                "date": date_str,
                "buzz_index": buzz,
                "close": float(row["close"]),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "volume": int(row["volume"]),
                "amount": float(row["amount"]),
            })
    else:
        date_range = pd.date_range(
            start=start_date[:4] + "-" + start_date[4:6] + "-" + start_date[6:],
            end=end_date[:4] + "-" + end_date[4:6] + "-" + end_date[6:],
        )
        for d in date_range:
            ds = d.strftime("%Y-%m-%d")
            buzz = calc_buzz_index(posts, ds)
            records.append({
                "date": ds, "buzz_index": buzz,
                "close": None, "open": None, "high": None, "low": None,
                "volume": None, "amount": None,
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
