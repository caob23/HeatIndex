"""主流程：串联价格采集 + 热度采集 → 输出日频 CSV"""

import os
import json
import pandas as pd
from datetime import datetime, timedelta

from heatindex.collectors.price_collector import PriceCollector
from heatindex.collectors.buzz_collector import BuzzCollector
from heatindex.calculator import calc_buzz_index
from heatindex.config import DATA_DIR


def run(symbol: str, start_date: str, end_date: str = None,
        data_dir: str = None) -> pd.DataFrame:
    """运行一次完整采集，返回价格 + 热度合并的日频数据。

    Args:
        symbol: 股票代码，如 '600519'
        start_date: 起始日期 'YYYYMMDD'
        end_date: 结束日期 'YYYYMMDD'，默认为今天
        data_dir: 数据存储目录

    Returns:
        DataFrame with columns: date, open, high, low, close, volume, amount, buzz_index
    """
    if end_date is None:
        end_date = datetime.now().strftime("%Y%m%d")
    if data_dir is None:
        data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), DATA_DIR)

    os.makedirs(data_dir, exist_ok=True)

    # 1. 获取价格数据
    print(f"[HeatIndex] 采集 {symbol} 价格数据 {start_date} → {end_date}")
    price = PriceCollector()
    price_df = price.get_stock_daily(symbol, start_date, end_date)
    print(f"  → 获取 {len(price_df)} 条价格记录")

    # 2. 获取热度数据（最近 N 天帖子）
    lookback_days = (datetime.now() - datetime.strptime(
        start_date, "%Y%m%d")).days + 1
    print(f"[HeatIndex] 采集 {symbol} 股吧帖子（最近 {lookback_days} 天）")
    buzz = BuzzCollector()
    try:
        posts_df = buzz.get_posts(symbol, days=lookback_days)
        print(f"  → 获取 {len(posts_df)} 条帖子")
    finally:
        buzz.close()

    # 3. 按日期计算热度指数
    date_buzz_map = {}
    if not posts_df.empty:
        date_range = pd.date_range(
            start=start_date[:4] + "-" + start_date[4:6] + "-" + start_date[6:],
            end=end_date[:4] + "-" + end_date[4:6] + "-" + end_date[6:],
        )
        for d in date_range:
            ds = d.strftime("%Y-%m-%d")
            idx = calc_buzz_index(posts_df, ds)
            date_buzz_map[ds] = idx

    # 4. 合并
    if price_df.empty:
        result = pd.DataFrame({"date": list(date_buzz_map.keys())})
        result["buzz_index"] = result["date"].map(date_buzz_map)
    else:
        result = price_df.copy()
        result["buzz_index"] = result["date"].map(date_buzz_map).fillna(0.0)

    # 5. 保存
    out_path = os.path.join(data_dir, f"{symbol}_{end_date}.csv")
    result.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"[HeatIndex] 结果已保存 → {out_path}")

    return result


def run_batch(symbols: list, start_date: str, end_date: str = None,
              data_dir: str = None) -> dict:
    """批量运行多只股票。

    Returns:
        {symbol: DataFrame}
    """
    results = {}
    for sym in symbols:
        try:
            results[sym] = run(sym, start_date, end_date, data_dir)
        except Exception as e:
            print(f"[HeatIndex] {sym} 失败: {e}")
            results[sym] = None
    return results


if __name__ == "__main__":
    import sys

    symbol = sys.argv[1] if len(sys.argv) > 1 else "600519"
    start = sys.argv[2] if len(sys.argv) > 2 else (
        datetime.now() - timedelta(days=30)).strftime("%Y%m%d")

    df = run(symbol, start)
    print(df.tail(10))
