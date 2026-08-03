# HeatIndex

广发纳指ETF热度指数看板 — 基于东方财富股吧讨论数据，量化市场情绪，动态可视化呈现。

在线地址：[caob23.github.io/HeatIndex](https://caob23.github.io/HeatIndex/)

---

## 许可证 · License

本项目采用 **GNU Affero General Public License v3.0 (AGPL-3.0)**。

- **个人 / 学术 / 非商业用途**：完全免费，在遵守 AGPL-3.0 的前提下自由使用、修改、分发。
- **企业 / 商业用途**：AGPL-3.0 要求通过网络使用本软件也构成"分发"，必须公开衍生代码。若企业在闭源产品中嵌入、基于本项目构建 SaaS 服务而不愿开源，**需要联系作者获取商业许可**（另行协商授权条款）。

> 商业许可咨询：请通过 GitHub Issues 联系。

完整许可证文本见 [LICENSE](LICENSE) 文件（AGPL-3.0）。

---

## 热度指数算法

```
帖子热度 = read_count × 0.4 + reply_count × 0.6
衰减权重 = 2^(-距今天数 / 7)          （半衰期 7 天）
原始得分 = Σ(帖子热度 × 衰减权重)
归一化分母 = log1p(历史最大原始得分 × 1.5)
热度指数 = log1p(原始得分) / 归一化分母 × 100
```

六档划分：冰点(0-25) → 微弱(25-37) → 基础活跃(37-50) → 中等热度(50-75) → 高热度(75-100) → 爆款顶流(≥100)

---

## 功能介绍

- **五条折线**：热度指数 / 收盘价 / 成交量 / 日涨跌 / 对数收盘价，右侧 Y 轴独立缩放
- **六档热度色条**：冰点 → 爆款顶流，一目了然
- **今日行情卡片**：当日盘中显示开盘价、最新价、成交量、热度指数
- **非交易日虚线连接**：周末/节假日价格线以 markLine 虚线跨越，避免断档
- **更新频率**：每交易日 2 次（北京时间 4:00 / 16:00），盘前+盘后

---

## 快速开始（换标的 Fork 用户）

### 1. Fork 仓库

点击右上角 Fork，复制到你自己的账号。

### 2. 启用 GitHub Pages

Settings → Pages → Source 选择 **GitHub Actions**。

### 3. 编辑配置

编辑 `data/stocks.json` 修改标的，编辑 `data/heat_config.json` 调整热度参数。

### 4. 手动触发

Actions → Daily Update → Run workflow → 等待部署完成。

---

## 本地运行

```bash
pip install -r requirements.txt
python pipeline.py
```

浏览器打开 `index.html` 即可。

---

## 技术栈

| 层 | 技术 |
|----|------|
| 数据采集 | Python · 东方财富股吧 · 腾讯财经日K线 |
| 定时任务 | GitHub Actions（每交易日两次：北京 4:00 / 16:00） |
| 前端 | MDUI · ECharts 5 · 纯静态 |
| 部署 | GitHub Pages (Actions 自动部署) |
