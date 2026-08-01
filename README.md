---
AIGC:
    Label: "1"
    ContentProducer: 001191440300708461136T1XGW3
    ProduceID: f5f3ccd3d9bee1d6f76b558277fc099f_fe7618728dc811f196d8525400f8a581
    ReservedCode1: dLqdxuHLRM2AAVKu5Mig/KoBt6xfKHsH0iGmT5nhnZVTkjCCKS4YV7QXCpaNB4UFALUBNDkn+sQPKTXn+Ya4lLj7m/reFxjHB8OM/yaG2p6vHJIbzv7wE7vBV8Wx4IL2nNNI57LG8l3faAo0x/1fnlD7H8i9T0ugfJIbgBapoNf8PzalwnGLEcDDTE0=
    ContentPropagator: 001191440300708461136T1XGW3
    PropagateID: f5f3ccd3d9bee1d6f76b558277fc099f_fe7618728dc811f196d8525400f8a581
    ReservedCode2: dLqdxuHLRM2AAVKu5Mig/KoBt6xfKHsH0iGmT5nhnZVTkjCCKS4YV7QXCpaNB4UFALUBNDkn+sQPKTXn+Ya4lLj7m/reFxjHB8OM/yaG2p6vHJIbzv7wE7vBV8Wx4IL2nNNI57LG8l3faAo0x/1fnlD7H8i9T0ugfJIbgBapoNf8PzalwnGLEcDDTE0=
---

# HeatIndex

成都银行 (601838) 股票热度指数看板：价格走势与东方财富股吧讨论热度的双轴可视化。

## 概述

- **热度指数 (0–273)**：基于股吧帖子阅读量/回复量，经时间衰减加权 + 对数归一化计算，量化市场关注度
- **价格走势**：腾讯财经前复权日K线，非交易日延续前一交易日收盘价（虚线标注）
- **自动更新**：每日北京时间 00:00 通过 GitHub Actions 自动采集，部署到 GitHub Pages

## 数据来源

| 数据 | 来源 | 说明 |
|------|------|------|
| 日K线 | [腾讯财经 API](http://web.ifzq.gtimg.cn) | 前复权，免费无认证 |
| 帖子热度 | 东方财富股吧 | 爬取近 60 天帖子，按阅读量 ×0.4 + 回复量 ×0.6 加权 |

## 热度指数算法

```
热度 = log1p(Σ 衰减权重 × 帖子热度) / log1p(50000) × 273
衰减权重 = 2^(-距今天数 / 7)     # 半衰期 7 天
```

## 项目结构

```
HeatIndex/
├── index.html            # 前端看板 (MDUI + ECharts)
├── pipeline.py           # 数据采集脚本
├── data/
│   └── dashboard_data.json   # 采集结果
├── requirements.txt      # Python 依赖
├── update.yml            # GitHub Actions 定时任务
└── README.md
```

## 本地运行

```bash
pip install -r requirements.txt
python pipeline.py
```

脚本输出 `data/dashboard_data.json`，在浏览器打开 `index.html` 即可查看。

## 部署

1. Fork 仓库，启用 GitHub Pages（main 分支 /docs 或根目录）
2. 配置 `update.yml` 中的 cron 表达式
3. 推送后 Actions 自动采集并部署
*（内容由AI生成，仅供参考）*
