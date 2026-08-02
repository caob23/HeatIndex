# HeatIndex

广发纳指ETF (159941) 热度指数看板：价格走势与东方财富纳斯达克吧讨论热度的双轴可视化。

## 概述

- **热度指数 (0–100)**：基于股吧帖子阅读量/回复量，经时间衰减加权 + 对数归一化计算，量化市场关注度
- **热度档位**：冰点 0 / 微弱 25 / 基础活跃 37 / 中等热度 50 / 高热度 75 / 爆款顶流 100
- **价格走势**：腾讯财经前复权日K线，非交易日延续前一交易日收盘价（虚线标注）
- **自动更新**：每日北京时间 00:00 通过 GitHub Actions 自动采集，部署到 GitHub Pages

## 数据来源

| 数据 | 来源 | 说明 |
|------|------|------|
| 日K线 | [腾讯财经 API](http://web.ifzq.gtimg.cn) | 前复权，免费无认证，标的 sz159941 |
| 帖子热度 | 东方财富股吧 | [纳斯达克吧](https://guba.eastmoney.com/list,zsgjndx.html)，爬取近 180 天帖子，按阅读量 ×0.4 + 回复量 ×0.6 加权 |

## 热度指数算法

```
热度 = log1p(Σ 衰减权重 × 帖子热度) / log1p(50000) × 100
衰减权重 = 2^(-距今天数 / 7)     # 半衰期 7 天
```

## 项目结构

```
HeatIndex/
├── index.html                # 前端看板 (MDUI + ECharts)
├── pipeline.py               # 数据采集脚本
├── data/
│   ├── dashboard_data.json   # 采集结果
│   └── guba_posts_zsgjndx.json  # 帖子持久化
├── .github/workflows/
│   └── update.yml            # GitHub Actions 定时任务
├── requirements.txt          # Python 依赖
└── README.md
```

## 前端功能

- ECharts 双轴折线图：热度指数（紫色 0–100）+ 收盘价（灰色）
- 非交易日虚线标注
- Y 轴自适应范围（非固定从 0 开始）
- 底部 dataZoom 滑块，可拖拽查看任意时间范围
- 日期范围快捷按钮：30天 / 3个月 / 6个月 / 1年 / 全部
- 纳斯达克数据明细表（日期、热度、档位、OHLCV）

## 本地运行

```bash
pip install -r requirements.txt
python pipeline.py
```

脚本输出 `data/dashboard_data.json`，在浏览器打开 `index.html` 即可查看。

## 部署

1. Fork 仓库，启用 GitHub Pages（main 分支根目录）
2. 推送后 Actions 自动采集并部署
