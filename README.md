# Loyalyn 1.0
Production-oriented multi-brand loyalty platform.

## Included
- Owner authentication and role-ready backend
- Multi-brand and branch data model
- Customer registration and searchable customer list
- Points, stamps, visits, tiers and rewards
- Idempotent loyalty transactions
- Individual/broadcast in-app notifications
- Webhook bridge for Push/SMS/Email providers
- Apple Wallet configuration and design storage
- Audit log model
- Responsive Arabic dashboard
- PostgreSQL + Docker Compose health checks

## Deploy
1. Copy `.env.example` to `.env` and replace every placeholder.
2. Run `docker compose up -d --build`.
3. Check `docker compose ps` and `curl http://127.0.0.1:8000/api/health`.
4. Put Nginx/Caddy in front of ports 3000 and 8000 with HTTPS.

The bootstrap owner is created on first API startup using the environment variables. Change the password value before first deployment.

## Notifications
In-app notifications work immediately. To deliver native push, SMS or email, configure `NOTIFICATION_WEBHOOK_URL` to a secure endpoint for your chosen provider. Loyalyn posts the audience, title and body there.

## Apple Wallet
Configuration storage is included. Real `.pkpass` signing needs an Apple Pass Type ID certificate and a signing service; certificates should be encrypted at rest and never committed to Git.
