# Splitter — Production Readiness Checklist

This is a **plan**, not evidence that Splitter has been deployed. Check an item only after verifying it in the real environment.

## Application and security

- [ ] Configure Django with `DEBUG=False` and explicit allowed hosts.
- [ ] Store Django secret key, database credentials, SMTP credentials, and other secrets outside Git.
- [ ] Configure HTTPS, secure session/CSRF cookies, trusted CSRF origins, CORS, and HSTS appropriately.
- [ ] Use real SMTP for verification/password reset; prevent user enumeration through mail errors.
- [ ] Configure non-root processes, least-privilege database credentials, and restricted inbound database access.
- [ ] Review image uploads, error responses, logging redaction, and database migrations.
- [ ] Verify critical flows in a real browser: register → verify → group → expense → settlement → payment confirmation.
- [ ] Verify Quick Split remains usable during a backend outage.

## Infrastructure and operations

- [ ] Choose the simplest deployment architecture that fits the budget.
- [ ] Containerize the Django backend if using Docker; pin compatible dependencies.
- [ ] Define a repeatable production start command and health checks.
- [ ] Configure a secure PostgreSQL backup and test a restore.
- [ ] Set budget alerts and monitor infrastructure charges.
- [ ] Collect application logs, errors, and basic resource/uptime signals.
- [ ] Define an incident rollback and redeployment procedure.
- [ ] Add a production domain and verify TLS certificate renewal.

## CI/CD and quality

- [ ] Run backend and frontend tests automatically on pull requests.
- [ ] Run lint/build checks without exposing credentials.
- [ ] Configure deployment credentials with least privilege.
- [ ] Add a controlled deployment process and document rollback.
- [ ] Verify the deployed commit, health checks, and a smoke-test user journey.

## Portfolio evidence (only after verification)

- [ ] Add a working **Live Demo** URL to both README files.
- [ ] Add authentic app screenshots (no mock screenshots represented as live functionality).
- [ ] Add a diagram that matches the actual cloud infrastructure.
- [ ] Document hosting, CI/CD, monitoring, and costs accurately.
- [ ] Add one concise deployment bullet to the resume using only verified achievements.

See [engineering case study](PROJECT_CASE_STUDY.md) and the [frontend repository](https://github.com/amanzx-git/expense-splitter-frontend).

**Important:** Splitter logs reported/confirmed UPI payments; it does not process money or verify bank transfer completion.
