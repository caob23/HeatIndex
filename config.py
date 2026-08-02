#    HeatIndex - NASDAQ ETF Market Heat Index Dashboard
#    Copyright (C) 2026  caob23
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""HeatIndex 数据集 - 热度指数
采集成都银行(601838)的每日价格 + 东方财富股吧讨论热度。
"""

# ── 标的配置 ──────────────────────────────────────────
SYMBOL = "601838"           # 成都银行
SYMBOL_NAME = "成都银行"
GUBA_CODE = "601838"        # 股吧代码（与股票代码一致）

# ── 热度指数范围 ──────────────────────────────────────
BUZZ_SCALE_MIN = 0
BUZZ_SCALE_MAX = 273

# ── 热度公式权重 ──────────────────────────────────────
WEIGHT_READ = 0.4           # 阅读量权重
WEIGHT_REPLY = 0.6          # 回复数权重

# ── 时间衰减半衰期（天） ──────────────────────────────
HALF_LIFE_DAYS = 7

# ── 股吧采集 ──────────────────────────────────────────
GUBA_PAGE_SIZE = 50         # 每页条数
GUBA_MAX_PAGES = 10         # 最大翻页数
REQUEST_INTERVAL = 1.0      # 请求间隔（秒）

# ── 输出 ──────────────────────────────────────────────
DATA_DIR = "data"
OUTPUT_FILE = "dashboard_data.json"
