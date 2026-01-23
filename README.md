# 🖥️ VM2 Infrastructure — Full System Backup

> **Complete backup of Oracle Cloud VM2 infrastructure for disaster recovery**

[![Oracle Cloud](https://img.shields.io/badge/Oracle_Cloud-Free_Tier-f80000?style=for-the-badge&logo=oracle&logoColor=white)]()
[![Services](https://img.shields.io/badge/Services-10+-blue?style=for-the-badge)]()
[![Status](https://img.shields.io/badge/Status-Production-success?style=for-the-badge)]()

---

## 📊 System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    VM2 INFRASTRUCTURE                       │
│                    Oracle Cloud Free Tier                   │
├─────────────────────────────────────────────────────────────┤
│  CPU: 1 OCPU (ARM)  │  RAM: 1GB  │  Disk: 45GB             │
│  Role: Hub Server   │  Manager: PM2 + systemd              │
└─────────────────────────────────────────────────────────────┘
```

This VM serves as the **hub** for the AGI system, hosting critical APIs and bridging communication between components.

---

## 🚀 Services

### PM2 Managed Services

| Service | Port | Description | Status |
|---------|------|-------------|--------|
| **jarvis-bot** | — | Telegram AI Assistant | ✅ Active |
| **mcp-hub-storage** | 3456 | MCP Hub data storage | ✅ Active |
| **transcriber** | 5000 | TikTok/YouTube transcription | ✅ Active |
| **oracle-agent** | 5001 | VM Management API | ✅ Active |
| **todo-api** | 3457 | Task Management API | ✅ Active |
| **gemini-image** | 5002 | Image Generation (Gemini) | ✅ Active |
| **veo-video** | 5003 | Video Generation | ✅ Active |
| **emilia-voice** | 5004 | Voice Synthesis | ✅ Active |

### Systemd Services

| Service | Description |
|---------|-------------|
| **agi-agent-web** | AGI Dashboard |
| **claude-mailbox** | Telegram message queue |
| **auto-deployer** | Hourly GitHub sync |
| **agi-tunnel** | Cloudflare tunnel |

---

## 📁 Repository Structure

```
vm2-infrastructure/
├── services/
│   ├── jarvis-bot/          # Telegram AI Bot
│   ├── tiktok-transcriber/  # Video transcription
│   ├── agent-memory/        # AI Memory System
│   ├── gemini-image-api/    # Image generation
│   ├── veo-video-api/       # Video generation
│   ├── oracle-agent-api.js  # Main API server
│   ├── todo-api.js          # Tasks API
│   └── vm_agent.py          # VM management agent
├── systemd/                 # Service unit files
├── configs/                 # nginx, cron configs
├── databases/               # SQLite backups
│   ├── memory.db           # Knowledge base
│   ├── mailbox.db          # Message queue
│   └── changes.db          # Changelog
└── pm2/
    └── dump.pm2            # PM2 process snapshot
```

---

## 🔄 Disaster Recovery

### Quick Restore (5 minutes)

```bash
# 1. Clone this repository
git clone https://github.com/tikserziku/vm2-infrastructure.git
cd vm2-infrastructure

# 2. Restore PM2 services
pm2 resurrect

# 3. Restore systemd services
sudo cp systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now agi-agent-web claude-mailbox

# 4. Restore databases
cp databases/*.db ~/
```

### Full Recovery Guide

See [RECOVERY.md](RECOVERY.md) for detailed step-by-step instructions.

---

## 🏗️ Architecture Role

```
┌─────────────────────────────────────────────────────────────┐
│                      AGI SYSTEM                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   VM1 (Main - 47+ services)                                │
│        │                                                    │
│        │ SSH + HTTP API                                     │
│        ▼                                                    │
│   ┌─────────────────────────────────────┐                  │
│   │   VM2 (Hub) ← THIS REPOSITORY       │                  │
│   │   • Bridge between components       │                  │
│   │   • External API gateway            │                  │
│   │   • Media processing               │                  │
│   │   • Telegram bot hosting           │                  │
│   └─────────────────────────────────────┘                  │
│        │                                                    │
│        │ HTTPS                                              │
│        ▼                                                    │
│   MCP Hub (fly.dev)                                        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 📊 Statistics

| Metric | Value |
|--------|-------|
| PM2 Services | 8 |
| Systemd Units | 4 |
| Databases | 4 |
| Total Backup Size | ~50MB |
| Recovery Time | <5 min |

---

## 🔗 Related Repositories

- [agi-progress](https://github.com/tikserziku/agi-progress) — Main AGI system
- [oracle-vm-agent](https://github.com/tikserziku/oracle-vm-agent) — VM1 management
- [claude-agent-orchestrator](https://github.com/tikserziku/claude-agent-orchestrator) — Agent coordination

---

## 📝 Backup Schedule

- **Automatic**: Daily at 03:00 UTC via `auto-deployer`
- **Manual**: Run `./backup.sh` to create snapshot

---

*Infrastructure managed by Claude AI — Part of VISAGINAS360 AGI Project*
