# TOOLS.md — Email Agent 工具配置

## 工具权限（OpenClaw 原生配置）

| 工具 | 状态 | 说明 |
|------|------|------|
| `exec` | ✅ allowlist | 仅允许运行白名单内的命令 |
| `fs` | ✅ workspaceOnly | 文件访问限于本 workspace 目录 |
| `web.search` | ❌ 禁用 | 邮件 agent 不需要 web 搜索 |
| `web.fetch` | ❌ 禁用 | 邮件 agent 不需要抓取网页 |

## Exec Allowlist（白名单命令）

```bash
python3 /home/steven/clawd-email/scripts/email_ops.py <命令> [参数]
python  /home/steven/clawd-email/scripts/email_ops.py <命令> [参数]
```

任何其他 exec 调用都会被 OpenClaw 拒绝。

## 工具库：email_ops.py

路径：`/home/steven/clawd-email/scripts/email_ops.py`
凭据：自动从 `scripts/.env` 加载（EMAIL_ADDRESS、EMAIL_APP_PASSWORD 等）

### 可用命令

```bash
# 列出邮件（默认收件箱最新10封）
python3 scripts/email_ops.py list [--limit N] [--folder INBOX]

# 搜索邮件
python3 scripts/email_ops.py search "关键词"

# 发送邮件
python3 scripts/email_ops.py send --to addr@example.com --subject "主题" --body "正文"

# 批量移动邮件（IMAP UID COPY+DELETE，一次完成）
python3 scripts/email_ops.py move --search "关键词" --folder "目标文件夹"

# 标记邮件状态
python3 scripts/email_ops.py flag --uid 12345 --flag seen|unseen
```

## Workspace 隔离

- **cwd**：Codex proxy 启动时锁定到 `/home/steven/clawd-email/`
- **fs**：OpenClaw 只允许读写本目录内的文件
- **与 stock agent 完全隔离**：两个 agent 的 session、记忆、工具互不可见
