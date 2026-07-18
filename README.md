# Loyalyn

Loyalyn is a mobile-first, multi-brand loyalty platform designed for restaurants, cafés, retail brands, and service businesses.

## Core capabilities

- Multi-brand and multi-branch architecture
- Customer registration and unique QR membership cards
- Employee scanner workflow for earning and redeeming rewards
- Flexible stamp and visit-based loyalty programs
- Customer, employee, branch, and transaction management
- Immutable audit trail for sensitive actions
- Mobile-first administration and employee interfaces
- Apple Wallet certificate vault and activation workflow
- Configurable Wallet pass design with version history
- Web membership card fallback before Apple Wallet activation

## Architecture

- Frontend: Next.js + TypeScript + Tailwind CSS
- Backend: FastAPI + SQLAlchemy
- Database: PostgreSQL
- Deployment: Docker Compose + Caddy-compatible reverse proxy

## Quick start

1. Copy environment variables:

   ```bash
   cp .env.example .env
   ```

2. Start the stack:

   ```bash
   docker compose up --build
   ```

3. Open:

   - Frontend: http://localhost:3000
   - API docs: http://localhost:8000/docs
   - Health: http://localhost:8000/api/health

## Important Apple Wallet note

The Apple Wallet setup screen is implemented as a secure configuration workflow. A valid Apple Pass Type ID certificate is still required before real `.pkpass` issuance can be enabled. Certificate secrets must be encrypted at rest using `APP_ENCRYPTION_KEY` and never exposed to employee roles.
