# Security policy

## Reporting a vulnerability

Please do not open a public issue for a suspected vulnerability. Use GitHub's private vulnerability reporting for this repository when available, or contact the repository owner privately through their GitHub profile.

Include the affected version or commit, reproduction steps, expected impact, and any suggested mitigation. Do not include real provider credentials or other users' data.

## Supported version

Security fixes target the latest commit on `main`.

## Deployment checklist

- Store provider credentials in a secret manager or protected environment variables.
- Set `DELIBRA_API_KEY` on any internet-accessible deployment.
- Restrict `DELIBRA_CORS_ORIGINS` to exact trusted origins.
- Terminate TLS at a trusted reverse proxy and forward only known proxy headers.
- Back up the persistent data volume and restrict filesystem permissions.
- Place distributed deployments behind a shared rate limiter and durable job queue.
- Review model outputs before using them for high-stakes decisions.
