# AShare Radar — Netlify / GitHub 一次性连接指南

原在线网址：https://playful-kashata-64f33f.netlify.app/

## 当前建设状态

- GitHub 的 `data` 分支：自动生成 `market.json`、`signal_ledger.json`，**已经有过成功运行记录**。
- GitHub 的 `main` 分支：采集、选股、回测及网页导入配置已提交。
- 既有 Netlify 网站：此前是手动拖放部署，尚未确认已连接 GitHub。
- 本仓库设置为公开：**仅允许公开市场行情和静态网页代码**，绝对不能上传个人持仓、API Key、密码、验证码。

## 第一步：将现有在线网页纳入 GitHub（只做一次）

打开 [GitHub Actions](https://github.com/Veraleehappiness/ashare-radar/actions/workflows/import-site-source.yml)。

选择 `Run workflow` → branch `main` → `Run workflow`。

绿色成功后，仓库会自动出现：

```text
site/
  index.html
  app.js
  style.css
  config.json
  _redirects
  data/market.json
```

工作流仅从已经公开的网站 `playful-kashata-64f33f.netlify.app` 获取网页静态资产，**不是私有数据导出**。
它导入的是当时在线网站版本。如果希望导入 V0.5，请先确认在线网站已经更新到 V0.5；不能假设最新 ZIP 已经发布。

若显示 `Import failed`，先确认 Netlify 原网站能在 Chrome 无痕模式下公开访问；如果网站要求登录，导入无法直接执行。不要提交 Netlify API Token 到公开仓库。

## 第二步：把原有 Netlify 网站与 GitHub 仓库连接（只做一次）

这一步必须由 Netlify 账户所有者授权，现有 GitHub 连接**不等于** Netlify 已授权。

1. 打开 [Netlify 控制台](https://app.netlify.com/)。
2. 选择当前网站 `playful-kashata-64f33f`，**不要新建网站**。
3. 进入 `Project configuration → Developer settings → Continuous deployment → Repository`。
4. 选择 `Link repository`，授权 GitHub，选择 `Veraleehappiness/ashare-radar` 和 `main` 分支。
5. 根目录的 `netlify.toml` 已设置：发布目录 `site`、不执行 Hugo、仅在网页文件改变时构建。若 UI 要求手动填：Base directory 留空，Build command 填 `echo Static AShare Radar site`，Publish directory 填 `site`。
6. 打开 `Deploys`，确认新的 Git 发布状态 `Published`，检查旧网址仍有效。

官方文档：https://docs.netlify.com/build/git-workflows/repo-permissions-linking/

## 之后如何更新

- 修改 GitHub `main/site/` 下的网页文件并提交，会自动触发 Netlify 发布，**不必再拖 ZIP**。
- `data` 分支行情更新不会重新部署静态网站；网页浏览器直接读取最新公开 JSON。
- 修改 Python 采集或回测代码，不应触发无用的 Netlify 构建（由根目录 `netlify.toml` 的 ignore 命令控制）。
- 网站上的“我的自选”“模拟交易”仍保存在**当前浏览器本地**，不是跨设备同步。不要把持仓和个人交易导入公共 `data` 分支。
- 无论哪种托管，公开免费行情都有接口和延迟限制；不是交易所直连、也非保证盈利工具。

## 如果要让 V0.5 直接进入 GitHub

在执行第一步**之前**，可以先把 [V0.5 Netlify ZIP](https://chatgpt.com/) 所包含的网页文件手动发布到原 Netlify 网站，再运行导入工作流；由此 GitHub 保存的就是已发布 V0.5。这里的链接仅是 ChatGPT 入口，下载包应从本次对话提供的附件取得，而不是复制仓库外的未知源码。
