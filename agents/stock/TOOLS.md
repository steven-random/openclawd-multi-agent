# TOOLS.md — Stock Analyst 工具配置

## 工具权限（OpenClaw 原生配置）

| 工具 | 状态 | 说明 |
|------|------|------|
| `exec` | ❌ deny | Stock agent 不执行本地命令 |
| `fs` | ✅ workspaceOnly | 文件访问限于本 workspace 目录 |
| `web.search` | ✅ 启用 | 查询实时股价、财报、新闻 |
| `web.fetch` | ✅ 启用 | 抓取具体页面内容 |

## 工具库：Web Search

Stock agent 的主要工具是 web search，直接内置于 OpenClaw。

推荐用法：
- 查股价：`search("AAPL stock price today")`
- 查财报：`search("NVDA Q4 2025 earnings")`
- 查新闻：`search("Tesla news March 2026")`
- 查宏观：`search("US CPI February 2026")`

## Workspace 隔离

- **cwd**：Codex proxy 启动时锁定到 `/home/steven/clawd-stock/`
- **fs**：OpenClaw 只允许读写本目录内的文件
- **exec 完全禁用**：不能运行任何本地命令（不能访问 email_ops.py 等）
- **与 email agent 完全隔离**：两个 agent 的 session、记忆、工具互不可见
