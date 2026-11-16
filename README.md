# Splitter — Backend API

Backend for **Splitter**, a group expense-sharing application built with **Python, Django REST Framework, and PostgreSQL**. The React client lives in the [frontend repository](https://github.com/amanzx-git/expense-splitter-frontend).

> **Status:** Active development. Production deployment is planned; a public production URL is not yet documented. The technical repository name remains `expense-splitter-backend`.

## Start here

**Recruiter / reviewer?** Read the [engineering case study](docs/PROJECT_CASE_STUDY.md) for the architecture, financial correctness, concurrency strategy, user journey, and technology decisions. For the UI, see the [React frontend](https://github.com/amanzx-git/expense-splitter-frontend).

**Explore:** [Engineering case study](docs/PROJECT_CASE_STUDY.md) · [Deployment readiness checklist](docs/DEPLOYMENT_CHECKLIST.md) · [Frontend](https://github.com/amanzx-git/expense-splitter-frontend)

## What it does

- **Accounts:** email registration and verification, session authentication, password reset, and profile management.
- **Groups:** group creation, memberships, invitations, and member management.
- **Expenses:** create, edit, and soft-delete group expenses; select participants, split equally, and comment on expenses.
- **Balances:** view unsettled group balances and settlement blockers.
- **Settlements:** generate deterministic settlement transactions from eligible expenses; preserve frozen settlement history.
- **Payments:** payer reports a payment and receiver confirms receipt; the application records status but **does not transfer money**.
- **Notifications:** recipient-specific alerts for invitations, expenses, settlements, and payment events.
- **Administration:** internal Django Admin for authorized staff, with protections around financial records.

## Engineering highlights

- **Exact money calculations:** INR amounts are handled in integer paise rather than binary floating-point. Remainders are assigned deterministically using participant UUID order.
- **Database integrity:** PostgreSQL transactions and consistent group-first row locking protect concurrent financial and membership operations.
- **Authorization:** access controls enforce group membership, administrator privileges, and payer/receiver-only payment transitions.
- **Session security:** cookie-based authentication and CSRF protections; email verification is required for login.
- **Testing:** Django/DRF tests cover authentication, permissions, financial rules, concurrency, and other critical workflows.

## Stack

Python · Django 5 · Django REST Framework · PostgreSQL · psycopg · django-cors-headers · Pillow

## Local development

Prerequisites: Python, PostgreSQL, and a PostgreSQL database/user configured with the appropriate privileges.

```bash
git clone https://github.com/amanzx-git/expense-splitter-backend.git
cd expense-splitter-backend
python -m venv .venv
```

Activate the virtual environment:

```bash
# Linux/macOS
source .venv/bin/activate

# Windows PowerShell
# .venv\Scripts\Activate.ps1
```

Install the dependencies:

```bash
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and configure `DJANGO_SECRET_KEY`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, and `DB_PORT`. Never commit your real `.env` or credentials.

```bash
python manage.py migrate
python manage.py runserver
```

The development API runs at `http://127.0.0.1:8000/` by default. To execute the test suite:

```bash
python manage.py test
```

For the full client experience, run the [Splitter frontend](https://github.com/amanzx-git/expense-splitter-frontend) separately.

## Architecture

```text
React frontend
    |
    | REST/JSON + session cookies + CSRF
    v
Django REST Framework
    |
    | ORM / atomic transactions / row locks
    v
PostgreSQL
```

The product-facing name is **Splitter**. Existing API paths and internal Django app/model names retain their original contract-defined names.

## Deployment note

Production configuration must be completed and verified before public launch: HTTPS, secure cookies, trusted origins, HSTS, real email delivery, restricted database access, backups, and correct host/CORS/CSRF settings. This README does **not** claim an existing AWS deployment or automated deployment pipeline.

## License

MIT License — © 2026 Aman Yadav. See [LICENSE](LICENSE).
