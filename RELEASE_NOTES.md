# Loyalyn v1.0.0

This release replaces the original visual scaffold with an operational foundation:

- Secure JWT owner login and first-start bootstrap administrator.
- Multi-brand, branch, customer, loyalty program, transaction, notification, wallet and audit database models.
- Customer points, stamps, visits, automatic tiers, rewards, redemption and idempotency protection.
- Broadcast and individual notification records with a generic delivery webhook bridge.
- Responsive Arabic administration interface connected to the live API.
- Docker health checks, restart policies, local-only exposed application ports and deployment validation script.
- Corrected frontend Docker build, including an actual public directory and build-time API URL.

Native APNs/FCM, Apple `.pkpass` signing, SMS and email require provider credentials and certificates and are therefore connected through secure configuration rather than embedded secrets.
