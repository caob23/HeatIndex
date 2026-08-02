# HeatIndex

广发纳指ETF热度看板 — 基于东方财富股吧讨论数据的市场热度指数可视化。

## 热度计算公式

热度指数 (0-100+) 由以下六步推导得出：

### 1. 帖子热度
```
帖子热度 = read_count × 0.4 + reply_count × 0.6
```
综合阅读量和回复量，回复权重更高（反映互动深度）。

### 2. 时间衰减
```
衰减权重 = 2^(-距今天数 / 7)
```
半衰期 7 天：7 天前的帖子权重衰减为 1/2，旧帖影响力自然消退。

### 3. 原始得分
```
原始得分 = Σ(帖子热度 × 衰减权重)
```
汇总目标日期及之前所有帖子的加权热度，随时间推移滚动累积。

### 4. 动态归一化分母
```
归一化分母 = log1p(max_raw_score × 1.5)
```
- `max_raw_score`：历史上所有日期中原始得分的最大值
- 首次运行默认 1000，后续运行自动追踪更新
- 存储在 `data/heat_config.json` 中
- 乘以 1.5 的安全系数防止新数据破表

### 5. 热度指数
```
热度指数 = log1p(原始得分) / 归一化分母 × 100
```
取值范围 0-100+。对数归一化压缩极端值，确保热度指数不会因个别日期帖子爆炸而无限制增长。当原始得分为 0 时（无任何帖子覆盖），热度指数为 null 表示无数据。

### 6. 六档划分
| 档位 | 范围 | 含义 |
|------|------|------|
| 冰点 | 0-25 | 几乎无讨论 |
| 微弱 | 25-37 | 零星关注 |
| 基础活跃 | 37-50 | 日常讨论水平 |
| 中等热度 | 50-75 | 关注度明显上升 |
| 高热度 | 75-100 | 市场热议 |
| 爆款顶流 | ≥100 | 极端关注，可能破表 |

## 配置说明（GitHub 用户）

### 1. Fork 仓库
点击右上角 Fork 按钮，将仓库复制到你的 GitHub 账号下。

### 2. 启用 GitHub Pages
进入仓库 Settings → Pages，Source 选择 **GitHub Actions**。

### 3. 修改 pipeline.py 顶部配置
```python
SYMBOL = "股票代码"         # 如 "159941"，腾讯财经日K线API自动识别 sh/sz 前缀
SYMBOL_NAME = "股票名称"     # 如 "广发纳指ETF"，显示在看板标题
GUBA_CODE = "股吧代码"       # 从 https://guba.eastmoney.com/list,{code}.html 获取
```
- 价格源：自动从腾讯财经日K线API获取前复权数据，无需额外配置

### 4. 设置 GitHub Secrets（如需）
如有额外敏感配置，在 Settings → Secrets and variables → Actions 中添加。

### 5. 手动触发
推送代码后，手动触发一次 Actions 或等待每日 00:00 (UTC+8) 自动运行。

## 文件结构

```
HeatIndex/
├── index.html                    # 前端看板 (MDUI + ECharts 四轴图表)
├── pipeline.py                   # 数据采集与热度计算脚本
├── README.md                     # 本文件
├── requirements.txt              # Python 依赖
├── data/
│   ├── dashboard_data.json       # 前端数据源 (自动生成)
│   ├── guba_posts_*.json         # 帖子持久化 (自动生成，增量累积)
│   └── heat_config.json          # 动态归一化配置 (自动生成)
└── .github/workflows/
    └── update.yml                # GitHub Actions 定时任务
```

## 自定义热度标度

### 修改热度上限
编辑 `pipeline.py` 中：
```python
BUZZ_SCALE_MIN = 0    # 热度指数下限
BUZZ_SCALE_MAX = 100  # 热度指数上限
```

### 修改档位划分
编辑 `index.html` 中的 `buzzLevel()` 函数，调整各档位阈值。

### 重置动态归一化
删除 `data/heat_config.json` 后重新运行 `pipeline.py`，系统将使用默认 `max_raw_score = 1000` 重新开始追踪。

## 本地运行

```bash
pip install -r requirements.txt
python pipeline.py
```

脚本输出 `data/dashboard_data.json`，在浏览器打开 `index.html` 即可查看看板。
