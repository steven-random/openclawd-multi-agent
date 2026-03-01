# openclawd-multi-agent

A production-grade, per-channel Slack multi-agent system built entirely on [OpenClaw](https://openclaw.dev) native capabilities — no custom routing code, no glue layer.

Each Slack channel gets its own isolated AI agent with independent long-term memory, running [OpenAI Codex](https://openai.com/codex) as the model via a local proxy bridge.

```
#email-agent  ──→  Email Agent  ──→  Yahoo Mail IMAP/SMTP
#stock-agent  ──→  Stock Agent  ──→  Web Search + Analysis
     ↕                  ↕
  OpenClaw          codex-proxy
  Gateway            (:9999)
  (:18789)              ↕
                    codex exec CLI
```

---

## Features

- **Per-channel agent isolation** — each Slack channel routes to a dedicated agent with its own workspace, sessions, and memory SQLite database
- **Zero cross-channel leakage** — routing layer (bindings), state layer (sessions dir), and memory layer (per-agent SQLite) are all physically isolated
- **Long-term memory** — local GGUF embedding model (embeddinggemma-300m) for offline vector search; no external embedding API required
- **OpenAI Codex via ChatGPT Plus** — `codex exec` CLI bridged through a local FastAPI proxy; free-tier inference for tool-using agents
- **Email operations** — full IMAP/SMTP agent: list, search, send, move, flag via `email_ops.py`
- **Stock analysis** — real-time web search + LLM reasoning for US market analysis
- **systemd-managed** — both services run as user systemd units, auto-restart on failure
- **Streaming support** — codex-proxy returns SSE (`text/event-stream`) to OpenClaw's streaming consumer

---

## Architecture

```
Slack Workspace (single Bot, Socket Mode)
│
├── #email-agent (C0AJ5MMPWQH)
│       │  binding: peer.kind=channel, id=C0AJ5MMPWQH
│       ↓
│   Agent "email"
│   workspace:  ~/clawd-email/
│   memory:     ~/.openclaw/memory/email.sqlite
│   model:      codex/gpt-5.3-codex
│   tools:      fs(workspaceOnly) + exec(allowlist: email_ops.py)
│
└── #stock-agent (C0AHSQ39YGJ)
        │  binding: peer.kind=channel, id=C0AHSQ39YGJ
        ↓
    Agent "stock"
    workspace:  ~/clawd-stock/
    memory:     ~/.openclaw/memory/stock.sqlite
    model:      codex/gpt-5.3-codex
    tools:      fs(workspaceOnly) + web.search + web.fetch
```

### Memory Isolation

Memory is isolated at three independent layers:

| Layer | Mechanism | Effect |
|-------|-----------|--------|
| **Routing** | `bindings[].match.peer.kind="channel" + id` | Messages only reach the bound agent |
| **State** | Per-agent `agentId` → separate sessions directory | No session history sharing |
| **Memory** | Per-agent `~/.openclaw/memory/<agentId>.sqlite` | Vector search only runs on the agent's own SQLite |

### codex-proxy

`codex-proxy` is a FastAPI server that bridges OpenClaw's OpenAI-compatible API calls to the `codex exec` CLI:

- Listens on `http://127.0.0.1:9999`
- Supports both `stream=false` (JSON) and `stream=true` (SSE) modes
- Detects agent identity from system message keywords to lock `cwd` to the correct workspace
- Strips `codex` CLI noise lines from output

---

## Requirements

| Component | Version | Notes |
|-----------|---------|-------|
| [OpenClaw](https://openclaw.dev) | 2026.2.26+ | `npm install -g openclaw` |
| [@openai/codex](https://www.npmjs.com/package/@openai/codex) | 0.106.0+ | `npm install -g @openai/codex` |
| Python | 3.10+ | For codex-proxy and email_ops |
| Node.js | 20+ | For OpenClaw gateway |
| Slack App | Socket Mode enabled | Bot + App token required |
| ChatGPT Plus | Active subscription | Used by `codex exec` CLI |

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/openclawd-multi-agent.git
cd openclawd-multi-agent
```

### 2. Install OpenClaw and Codex

```bash
npm install -g openclaw @openai/codex
```

### 3. Set up codex-proxy

```bash
cd codex-proxy
pip install -r requirements.txt
# Test it
python proxy.py &
curl http://127.0.0.1:9999/v1/models
```

### 4. Set up agent workspaces

```bash
# Email agent
mkdir ~/clawd-email
cp -r agents/email/* ~/clawd-email/
cp agents/email/scripts/.env.example ~/clawd-email/scripts/.env
# Edit ~/.env with your email credentials
nano ~/clawd-email/scripts/.env

# Stock agent
mkdir ~/clawd-stock
cp -r agents/stock/* ~/clawd-stock/
```

### 5. Configure OpenClaw

```bash
mkdir -p ~/.openclaw
cp config/openclaw.json.example ~/.openclaw/openclaw.json
# Edit with your Slack tokens and channel IDs
nano ~/.openclaw/openclaw.json
```

### 6. Install systemd services

```bash
mkdir -p ~/.config/systemd/user

# codex-proxy
sed "s/YOUR_USER/$USER/g" codex-proxy/codex-proxy.service.example \
  > ~/.config/systemd/user/codex-proxy.service

# OpenClaw gateway (update OPENCLAW_GATEWAY_TOKEN)
cp systemd/openclaw-gateway.service.example ~/.config/systemd/user/openclaw-gateway.service
nano ~/.config/systemd/user/openclaw-gateway.service

systemctl --user daemon-reload
systemctl --user enable --now codex-proxy
systemctl --user enable --now openclaw-gateway
```

### 7. Verify

```bash
openclaw doctor
openclaw agents list --bindings
openclaw channels status --probe
```

---

## Environment Variables

All secrets live in two files. **Neither should ever be committed to git.**

### `~/.openclaw/openclaw.json`

| Key path | Description |
|----------|-------------|
| `channels.slack.botToken` | Slack Bot Token (`xoxb-...`) |
| `channels.slack.appToken` | Slack App Token (`xapp-...`) — requires Socket Mode |
| `tools.web.search.apiKey` | Web search API key (optional, for stock agent) |
| `gateway.auth.token` | Local gateway API token (generate with `openssl rand -hex 24`) |

### `~/clawd-email/scripts/.env`

| Variable | Description |
|----------|-------------|
| `EMAIL_ADDRESS` | Yahoo Mail address |
| `EMAIL_APP_PASSWORD` | Yahoo App Password (not your login password) |
| `IMAP_HOST` | IMAP server (default: `imap.mail.yahoo.com`) |
| `IMAP_PORT` | IMAP port (default: `993`) |
| `SMTP_HOST` | SMTP server (default: `smtp.mail.yahoo.com`) |
| `SMTP_PORT` | SMTP port (default: `587`) |

> **Yahoo App Password**: Log in to Yahoo Account Security → Generate app password → Select "Other app"

---

## Slack App Setup

1. Create a Slack app at [api.slack.com/apps](https://api.slack.com/apps)
2. Enable **Socket Mode** and generate an App-level token (`xapp-...`) with `connections:write` scope
3. Add Bot Token scopes: `chat:write`, `channels:read`, `groups:read`, `reactions:write`
4. Install the app to your workspace and copy the Bot Token (`xoxb-...`)
5. Invite the bot to each channel: `/invite @YourBotName`
6. Get channel IDs from channel URLs or `slack channels list` CLI

---

## Usage Examples

### Email Agent (`#email-agent`)

```
You: 列出最新5封邮件
Bot: 📬 INBOX 最新 5 封邮件:
     [12345] 账单提醒 | From: billing@example.com | Date: ...
     ...

You: 把所有验证码邮件移到 "Verification" 文件夹
Bot: ✅ 已将 23 封邮件移动到 Verification

You: 发邮件给 friend@example.com，主题：你好，正文：周末有空吗
Bot: ✅ 已发送邮件给 friend@example.com，主题：你好
```

### Stock Agent (`#stock-agent`)

```
You: NVDA 最新财报分析
Bot: 📊 NVIDIA Q4 FY2025 财报分析
     营收: $39.3B (+78% YoY)，超预期 $37.6B
     ...

You: 你知道我在 #email-agent 里说的幸运数字吗？
Bot: 我没有关于你幸运数字的记录。（跨 channel 记忆完全隔离）
```

### Verifying Memory Isolation

```bash
# In #email-agent:
#   "请记住：我的幸运数字是 42"
# In #stock-agent:
#   "我的幸运数字是多少？"
# Expected: stock agent replies "不知道" or "没有相关记忆"

# Check sqlite files are separate:
ls -la ~/.openclaw/memory/
# email.sqlite   stock.sqlite   ← physically isolated
```

---

## Deployment

### Local (systemd)

```bash
# Start all services
systemctl --user start codex-proxy openclaw-gateway

# Check status
systemctl --user status codex-proxy openclaw-gateway

# View live logs
journalctl --user -u openclaw-gateway -f
journalctl --user -u codex-proxy -f

# Reload config without dropping Slack connection
openclaw gateway restart
```

### Adding a New Channel Agent

1. **Get the Slack channel ID** (from channel URL or settings, starts with `C`)
2. **Create workspace directory**
   ```bash
   mkdir ~/clawd-myagent
   cp -r agents/email/* ~/clawd-myagent/
   # Edit AGENTS.md to define the new agent's role
   ```
3. **Edit `~/.openclaw/openclaw.json`** — add three entries:
   ```json
   // agents.list[]
   { "id": "myagent", "workspace": "/home/USER/clawd-myagent",
     "model": { "primary": "codex/gpt-5.3-codex" },
     "tools": { "fs": { "workspaceOnly": true }, "exec": { "security": "deny" } } }

   // bindings[]
   { "agentId": "myagent", "match": { "channel": "slack",
     "peer": { "kind": "channel", "id": "CNEWCHANNEL" } } }

   // channels.slack.channels
   "CNEWCHANNEL": { "requireMention": false }
   ```
4. **Reload and invite bot**
   ```bash
   openclaw gateway restart
   # In Slack: /invite @YourBotName in the new channel
   ```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Slack bot doesn't reply | Socket Mode disconnected | `openclaw channels status --probe`; check app token |
| Bot replies empty content | codex-proxy not returning SSE | Check `stream=true` handling in `proxy.py`; verify `journalctl --user -u codex-proxy -f` |
| `404` from codex-proxy | Wrong endpoint path | OpenClaw uses `/chat/completions`; proxy listens on both `/v1/chat/completions` and `/chat/completions` |
| OpenAI call fails | ChatGPT Plus session expired | Re-authenticate: `codex auth login` |
| Memory not persisting | sqlite missing or wrong path | `openclaw memory status`; check `~/.openclaw/memory/<agentId>.sqlite` exists |
| Agent replies to wrong channel | Binding misconfigured | `openclaw agents list --bindings`; verify channel IDs |
| `groupPolicy` open (security) | Old config | Set `channels.slack.groupPolicy: "allowlist"` |
| 30s response latency | `codex exec` CLI startup overhead | See Performance section below |

### Performance: ~30s Latency

The latency comes from `codex exec` spawning a new process per request:

1. CLI startup + WebSocket handshake to ChatGPT (~3-5s)
2. Auth token refresh (~2s if needed)
3. Prompt processing + model inference (~15-25s depending on response length)
4. Process cleanup

**Mitigation options** (in order of impact):

| Option | Impact | Complexity |
|--------|--------|------------|
| Switch to OpenAI API directly | High — removes CLI overhead | Medium |
| Stream codex stdout in real-time | Medium — user sees partial output sooner | Low |
| Pre-warm process pool | Medium — reduces startup cost | Medium |
| Shorter system prompts | Low | Low |

---

## Project Structure

```
openclawd-multi-agent/
├── README.md
├── .gitignore
│
├── codex-proxy/                  # FastAPI bridge: OpenAI API → codex exec CLI
│   ├── proxy.py                  # Main server (stream + non-stream)
│   ├── requirements.txt          # fastapi, uvicorn
│   └── codex-proxy.service.example
│
├── agents/
│   ├── email/                    # Email agent workspace template
│   │   ├── AGENTS.md             # Role definition and tool commands
│   │   ├── SOUL.md               # Agent personality and behavior
│   │   ├── TOOLS.md              # Tool permissions reference
│   │   ├── HEARTBEAT.md          # Scheduled check-in instructions
│   │   ├── BOOTSTRAP.md          # First-run initialization guide
│   │   ├── IDENTITY.md           # Agent identity (fill in on first run)
│   │   ├── USER.md               # User profile (fill in on first run)
│   │   └── scripts/
│   │       ├── email_ops.py      # Yahoo Mail IMAP/SMTP CLI tool
│   │       └── .env.example      # Credentials template
│   │
│   └── stock/                    # Stock analyst workspace template
│       ├── AGENTS.md
│       ├── SOUL.md
│       ├── TOOLS.md
│       ├── HEARTBEAT.md
│       ├── IDENTITY.md
│       └── USER.md
│
├── config/
│   └── openclaw.json.example     # Full OpenClaw config template (no secrets)
│
└── systemd/
    ├── openclaw-gateway.service.example
    └── codex-proxy.service.example
```

---

## License

MIT
