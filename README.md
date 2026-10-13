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
