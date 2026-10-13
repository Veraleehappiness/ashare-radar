# AShare Radar — 在线行情数据更新

此仓库用于 [AShare Radar 在线网页](https://playful-kashata-64f33f.netlify.app/) 的免费行情采集。

## 第一次启用
1. 打开仓库 **Actions → AShare Radar market refresh**。
2. 点击 **Run workflow → Run workflow**。
3. 等任务显示绿色成功后，检查：
   https://raw.githubusercontent.com/Veraleehappiness/ashare-radar/data/market.json
4. 在 Netlify 网站的 **行情/数据质量** 页面刷新查看。

## 自动运行
工作流计划在工作日北京时间 **16:45、19:20** 更新。GitHub 任务调度可能延迟或漏执行；法定假期可能空跑。本任务不是盘中实时行情。

## 安全与可靠性
- 仅公开第三方市场行情，不上传个人持仓、模拟账户、API Key、ChatGPT 账户信息。
- 未取得有效全市场行情及至少一只候选股历史K线时，任务失败，不以演示价格替代真实价格。
- `data` 分支由 GitHub Actions 自动生成并包含市场数据；如果不存在，说明尚未成功运行。
- 免费行情接口可能在 GitHub 云端受限，需要通过 Actions 日志检查并修复。
- 全市场快照初筛，最多 30 只股票进一步读取历史日 K 线；并非全市场逐股历史回测。
- 本版本仅提供研究用途的数据和技术信号，没有真实交易、自动盈利承诺或可信的完整历史回测。
- 若推送报错 `Permission to ... denied`，在 **Settings → Actions → General → Workflow permissions** 核实写权限策略。

## 项目结构
- `scripts/build_data.py`：实时请求公开行情、质控、有限候选日线验证，输出 schema 2 JSON。
- `.github/workflows/market-refresh.yml`：定时采集，成功后发布 `data` 分支。
- `requirements-data.txt`：Python 依赖。

## 网页接入
已发布的 Netlify V0.3 网页配置中应有：
`https://raw.githubusercontent.com/Veraleehappiness/ashare-radar/data/market.json`

**请注意：当前 GitHub 仓库只用于数据自动更新，没有接管既有 Netlify 网站的前端发布。**

## V0.4 研究模块（AlphaSift + AKQuant）

- 新增 `scripts/enrich_research.py`，**真正调用** [AlphaSift](https://github.com/ZhuLinsen/alphasift) 的 `screen("dual_low", market="cn", use_llm=False)`，记录独立的双低策略筛选结果、来源和降级情况。
- AlphaSift 固定官方仓库 commit `7639195e6176f4af37086c282834a7c09dc3e4a3`；其数据来源可能不同于本项目的 AKShare 快照。如无法运行，则 `alphasift.status` 标为 `failed` 或 `timeout`。
- 通过 [AKQuant](https://github.com/akfamily/akquant) 对固定的京东方 A（000725）和 TCL 科技（000100）进行 MA20/MA60 策略的**独立真实历史样本回测**。包含 T+1、次日开盘、100股整手和交易费率。仅在成功时填充 `backtests` 和 `research_backtests.samples`。
- 用两个独立子进程运行研究，超时不会把虚构绩效写入 `market.json`。按需降级，不覆盖成功生成的真实行情字段。
- **不是全市场逐只股票历史回测**，也不覆盖历史退市股票、除权送转/股息、全部涨跌停流动性限制与所有交易滑点情形。禁止将结果当成实盘盈利证明。
- V0.4 网页升级包需要在 Netlify 原项目的 **Deploys** 中手动部署，才能显示新增的 AlphaSift 区域和专业回测标识；GitHub `data` 分支的刷新不等于网页自动更新。
- 运行验证：`python -m unittest discover -s tests -p 'test_research.py' -v`；GitHub Actions 首次完成后检查 `market.json` 的 `alphasift.status`、`research_backtests.status` 和 `backtests`。


## V0.5 前瞻信号追踪（无需付费 AI）

新增 \`scripts/track_signals.py\` 和 \`tests/test_tracker.py\`。

- 使用当前已完成日 K 线的一致交易日期，锁定信号记录日；缺少有效日期、日期不一致、非交易日、停牌/零成交额时不补造结果。
- 分别记录自定义选股 Top 10 和 AlphaSift Top 10 的信号、来源、价格及日期；同一个交易日重复刷新不重复入账。
- 随后收集真实 **1 / 5 / 10 / 20 次成功采集的收盘快照**，计算样本涨跌幅、正收益比例和样本数。**这些数字并不严格等于 N 个交易日**，GitHub 漏运行也不会假装成交。
- 数据在公共 \`data/signal_ledger.json\` 分支文件中保存，仅包括公开股票行情及公开策略信号；不保存你的持仓或交易账户。
- 最多保留最近 2,500 条记录，出现截断会明确披露。使用不复权价格、不含交易费/滑点/分红/复权调整或历史退市偏差，**不能等同于量化回测的真实盈利收益**。
- \`market.json\` 新增 \`signal_tracking\`，在数据累积之后才会出现真实成熟样本表现；初期成熟样本为零是正常的。

数据文件：
- [当前市场行情 JSON](https://raw.githubusercontent.com/Veraleehappiness/ashare-radar/data/market.json)
- [前瞻信号追踪 JSON](https://raw.githubusercontent.com/Veraleehappiness/ashare-radar/data/signal_ledger.json)（第一次新工作流成功后出现）

> Netlify 的既有网页前端若没有适配 \`signal_tracking\`，不会自动显示该新模块；GitHub 数据端已经可记录，网页仍需单独升级。


## 量化策略实验库（研究版）

代码：[`scripts/strategy_rules.py`](scripts/strategy_rules.py)；测试：[`tests/test_strategy_rules.py`](tests/test_strategy_rules.py)。

已经编码的 4 套策略：`bottom_reversal_v1`（底部反转）、`volume_breakout_v1`（放量突破）、`trend_pullback_v1`（趋势回踩）、`short_rebound_v1`（短期反弹）。另外 3 套行业轮动、质量价值、低波动等待相应历史数据；不输出伪造信号。

行情文件 `data/market.json` 新增 `strategy_library` 字段：`rules` 为完整定义，`signals` 仅为真实触发记录，`evaluated_stocks` 为实际历史日线分析的股票数量。

注意：这只是对当前基础初筛的最多 30 只股票追加规则评估，并非全市场回测。所有阈值为待检验假设，不是已验证正收益的买卖策略。信号是收盘后计算，最早在后续可成交交易时点模拟。必须在考虑 T+1、涨跌停、停牌、费用、滑点、复权和退市样本后进行样本外净收益验证。

GitHub `site/` 已增加「量化策略库」页面和移动端入口。静态站部署到 Netlify 前，该功能不会自动出现在生产网站。