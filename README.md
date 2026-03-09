# Telegram VPN Bot (s-ui / Hysteria2)

Production-grade Telegram bot for VPN sales with trial/subscription lifecycle, payment webhooks, and multi-server s-ui support.

## Stack
- Python 3.12+
- aiogram 3
- FastAPI
- PostgreSQL + SQLAlchemy 2 + Alembic
- APScheduler
- httpx
- Docker + Nginx + Certbot

## Quick start (local/staging style)
1. Copy `.env.example` to `.env.staging` and fill values.
2. Run `docker compose -f docker-compose.staging.yml up -d --build`.
3. Check health: `curl -k https://staging.sokolrock.org:8443/health`.

Detailed runbook is in `docs/RUNBOOK.md`.
