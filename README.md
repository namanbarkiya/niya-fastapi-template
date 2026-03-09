# Niya FastAPI Template

Production-ready multi-product FastAPI backend with schema-per-product PostgreSQL architecture, JWT auth, billing, org management, and cross-product admin dashboard.

## Tech Stack

- **Python 3.11+** · **FastAPI** · **SQLAlchemy 2.0 async** · **asyncpg**
- **PostgreSQL** (Neon, Railway, Supabase, or local)
- **Alembic** migrations · **Pydantic v2** · **python-jose** JWT · **bcrypt**
- **Razorpay** payments (Stripe-ready abstract interface)

---

## Architecture

One FastAPI monolith serving multiple products. Each product gets its own PostgreSQL schema — no cross-schema SQL joins, ever.

```
shared schema        → users, auth, orgs, billing, notifications
product_alpha schema → resources (template product)
taskboard schema     → projects, tasks
```

Products communicate with shared data only through `app/shared/repos/` — never by importing each other's models.

---

## Quick Start

### 1. Clone & virtual environment

```bash
git clone <repo-url> && cd niya-fastapi-template
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

### 2. Install dependencies

```bash
pip install -r requirements-dev.txt   # includes test/lint tools
# or production only:
pip install -r requirements.txt
```

### 3. Environment variables

```bash
cp .env.example .env
```

Edit `.env` — minimum required:

| Variable | Description |
|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://user:pass@host:5432/db` |
| `JWT_SECRET` | Run `openssl rand -hex 64` |

> The driver prefix is auto-corrected: plain `postgresql://` is accepted and converted to `postgresql+asyncpg://`.

### 4. Create database schemas

Run once in your PostgreSQL instance:

```sql
CREATE SCHEMA IF NOT EXISTS shared;
CREATE SCHEMA IF NOT EXISTS product_alpha;
CREATE SCHEMA IF NOT EXISTS taskboard;
```

### 5. Run migrations

```bash
alembic upgrade head
```

### 6. Start server

```bash
uvicorn app.main:app --reload --port 8000
```

| URL | Description |
|---|---|
| `http://localhost:8000` | Landing page |
| `http://localhost:8000/docs` | Swagger UI |
| `http://localhost:8000/redoc` | ReDoc reference |
| `http://localhost:8000/health` | Health check |

---

## API Overview

All authenticated endpoints (`🔒`) require a JWT access token — either as a cookie (`access_token`) or `Authorization: Bearer <token>` header.

### Auth — `/api/auth`

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Register new user, sends email OTP |
| POST | `/api/auth/login` | Login, returns tokens in HTTP-only cookies |
| POST | `/api/auth/refresh` | Rotate refresh token, issue new access token |
| POST | `/api/auth/logout` | Invalidate current session |
| POST | `/api/auth/logout-all` | Invalidate all sessions |
| POST | `/api/auth/verify-email` | Verify email with OTP |
| POST | `/api/auth/resend-otp` | Resend verification OTP |
| POST | `/api/auth/forgot-password` | Send password reset email |
| POST | `/api/auth/reset-password` | Reset password with token |
| POST | `/api/auth/oauth/{provider}` | OAuth2 login (Google, GitHub, etc.) |

### Users — `/api/users` `🔒`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/users/me` | Get current user with profile |
| PATCH | `/api/users/me` | Update profile fields |
| GET | `/api/users/me/profile` | Get profile |
| PATCH | `/api/users/me/profile` | Update profile |
| GET | `/api/users/me/emails` | List linked emails |
| POST | `/api/users/me/emails` | Add secondary email |
| PATCH | `/api/users/me/password` | Change password |

### Organizations — `/api/orgs` `🔒`

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/orgs` | Create org |
| GET | `/api/orgs` | List orgs the user belongs to |
| GET | `/api/orgs/{org_id}` | Get org details |
| PATCH | `/api/orgs/{org_id}` | Update org (owner/admin only) |
| GET | `/api/orgs/{org_id}/members` | List members with roles |
| POST | `/api/orgs/{org_id}/invites` | Invite member by email |
| POST | `/api/orgs/invites/accept` | Accept invite token |
| DELETE | `/api/orgs/{org_id}/members/{user_id}` | Remove member |
| PATCH | `/api/orgs/{org_id}/members/{user_id}/role` | Change member role |

### Billing — `/api/billing` `🔒`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/billing/plans/{product}` | List plans for a product |
| GET | `/api/billing/subscription/{product}` | Get active subscription |
| POST | `/api/billing/subscribe` | Subscribe to a plan |
| POST | `/api/billing/cancel` | Cancel subscription |
| POST | `/api/billing/change-plan` | Upgrade / downgrade plan |
| GET | `/api/billing/invoices` | List invoices |
| GET | `/api/billing/invoices/{invoice_id}` | Get invoice with line items |
| GET | `/api/billing/payment-methods` | List payment methods |
| POST | `/api/billing/payment-methods` | Add payment method |
| DELETE | `/api/billing/payment-methods/{method_id}` | Remove payment method |
| GET | `/api/billing/transactions` | List transactions |
| POST | `/api/billing/webhook/{provider}` | Payment provider webhook |

### Notifications — `/api/notifications` `🔒`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/notifications?unread_only=true` | List notifications |
| PATCH | `/api/notifications/{id}/read` | Mark one as read |
| POST | `/api/notifications/read-all` | Mark all as read |

### Admin Dashboard — `/api/admin` `🔒`

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/admin/dashboard?org_id={uuid}` | Cross-product aggregate stats |

Omit `org_id` for platform-wide totals. Supply `org_id` for per-member activity breakdown (requires org owner/admin role).

---

### Product Alpha — `/api/alpha` `🔒`

Template product — rename to your actual product.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/alpha/resources` | List your resources |
| POST | `/api/alpha/resources` | Create resource |
| GET | `/api/alpha/resources/{id}` | Get resource |
| PATCH | `/api/alpha/resources/{id}` | Update resource |
| DELETE | `/api/alpha/resources/{id}` | Delete resource |

### Taskboard — `/api/taskboard` `🔒`

**Projects**

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/taskboard/projects?include_archived=false` | List projects |
| POST | `/api/taskboard/projects` | Create project |
| GET | `/api/taskboard/projects/{id}` | Get project |
| PATCH | `/api/taskboard/projects/{id}` | Update project |
| POST | `/api/taskboard/projects/{id}/archive` | Archive project |

**Tasks** (nested under projects)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/taskboard/projects/{project_id}/tasks?status=todo` | List tasks |
| POST | `/api/taskboard/projects/{project_id}/tasks` | Create task |
| GET | `/api/taskboard/projects/{project_id}/tasks/{task_id}` | Get task |
| PATCH | `/api/taskboard/projects/{project_id}/tasks/{task_id}` | Update task |
| DELETE | `/api/taskboard/projects/{project_id}/tasks/{task_id}` | Delete task |

---

## Authentication Flow

```
POST /api/auth/register   →  OTP sent to email
POST /api/auth/verify-email  →  account activated

POST /api/auth/login
  response sets cookies:
    access_token  (HTTP-only, 30 min)
    refresh_token (HTTP-only, 7 days)

Subsequent requests send cookie automatically, or:
  Authorization: Bearer <access_token>

POST /api/auth/refresh   →  new access_token + rotated refresh_token
POST /api/auth/logout    →  cookies cleared, refresh token revoked
```

JWT payload includes a `products` claim — middleware blocks access to any product the user isn't provisioned for.

---

## Project Structure

```
app/
├── main.py                        # App entry, middleware, router mounts
├── core/
│   ├── config.py                  # Pydantic settings (loads .env)
│   ├── database.py                # Async engine + session factory
│   ├── dependencies.py            # get_db, get_current_user, get_product
│   ├── middleware.py              # Logging, product identification, rate limit
│   ├── security.py                # JWT + bcrypt
│   └── exceptions.py             # Custom exceptions + handlers
├── shared/
│   ├── models/                    # SQLAlchemy models (schema = "shared")
│   ├── repos/                     # Repository classes
│   ├── schemas/                   # Pydantic request/response models
│   ├── services/                  # Auth, billing, org, notification, dashboard
│   └── routes/                    # auth, users, orgs, billing, notifications, admin
└── products/
    ├── product_alpha/             # Template product
    │   ├── models/                # schema = "product_alpha"
    │   ├── repos/
    │   ├── schemas/
    │   ├── services/
    │   └── routes/
    └── taskboard/
        ├── models/                # schema = "taskboard"
        ├── repos/
        ├── schemas/
        ├── services/
        └── routes/
migrations/
├── versions/
│   ├── shared/                    # 001_init, 002_auth, 003_billing, 004_utilities
│   ├── product_alpha/             # 001_init_product_alpha
│   └── taskboard/                 # 001_init_taskboard
tests/
├── conftest.py                    # Async fixtures, test DB, get_db override
├── shared/
├── product_alpha/
└── test_product_isolation.py      # AST-based cross-import enforcement
```

---

## Adding a New Product

```bash
mkdir -p app/products/myproduct/{models,repos,schemas,services,routes}
```

1. Models use `__table_args__ = {"schema": "myproduct"}` — `user_id` is a plain `UUID`, no FK to `shared.users`
2. Create Alembic migration: `CREATE SCHEMA IF NOT EXISTS myproduct` + tables
3. Mount router in `main.py`: `app.include_router(router, prefix="/api/myproduct")`
4. Add `"myproduct"` to `PRODUCTS` in `.env`
5. Register models in `app/products/myproduct/models/__init__.py` and import it in `app/main.py` (before `app = FastAPI()`)

**Rule:** never import from another product module.

---

## Running Tests

```bash
export TEST_DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/niya_test

pytest                                    # all tests
pytest -v tests/shared/                  # shared layer only
pytest tests/test_product_isolation.py   # static import checks (no DB needed)
```

---

## Environment Variables Reference

```env
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname

# JWT
JWT_SECRET=<openssl rand -hex 64>
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Cookies
COOKIE_SECURE=false          # set true in production
COOKIE_HTTPONLY=true
COOKIE_SAMESITE=lax

# Email (optional)
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=your@email.com
SMTP_PASSWORD=your_smtp_password
EMAIL_FROM=noreply@example.com
APP_BASE_URL=http://localhost:3000

# Application
APP_NAME=Niya API
DEBUG=true
ENVIRONMENT=development
LOG_LEVEL=INFO

# Rate limiting
RATE_LIMIT_PER_MINUTE=60

# CORS
CORS_ORIGINS=["http://localhost:3000"]

# Payments (Razorpay)
RAZORPAY_KEY_ID=rzp_test_xxx
RAZORPAY_KEY_SECRET=xxx
RAZORPAY_WEBHOOK_SECRET=xxx
DEFAULT_PAYMENT_PROVIDER=razorpay

# Products
PRODUCTS=["alpha","taskboard"]
```

---

## Deployment (Docker)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## License

MIT
