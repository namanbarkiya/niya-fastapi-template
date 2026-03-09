# Project: Multi-Product FastAPI Backend

## Architecture Overview

This is a **single FastAPI monolith** serving multiple products. Each product has its own Next.js frontend. The backend and database are shared across all products.

### Core Principles (NEVER violate these)

1. **Schema-per-product in Postgres** — each product gets its own DB schema. Shared resources (auth, billing, orgs) live in a `shared` schema.
2. **No cross-schema joins** — NEVER write a SQL query that JOINs tables across schemas. Always use two separate queries through the repository layer.
3. **UUIDs for all primary keys** — every table uses `UUID` as the primary key. No serial integers. This makes future database extraction portable.
4. **Repository layer abstraction** — product modules access shared data (users, billing) ONLY through `app/shared/repos/`. Never import shared models directly into product modules.
5. **Product modules never import from each other** — `product_alpha` can import from `app/core/` and `app/shared/`, but NEVER from `product_beta` or any other product.
6. **All timestamps are UTC** — use `TIMESTAMPTZ` in Postgres and `datetime.utcnow()` in Python.

---

## Directory Structure

```
app/
├── main.py                    # FastAPI app, mounts product routers
├── core/                      # Shared infrastructure (not domain logic)
│   ├── config.py              # Settings via pydantic-settings, loads .env
│   ├── database.py            # Engine, session factory, schema routing
│   ├── dependencies.py        # FastAPI dependency injection (get_db, get_current_user)
│   ├── middleware.py           # Product identification, request logging
│   ├── security.py            # JWT creation/validation, password hashing
│   └── exceptions.py          # Custom exception classes + handlers
├── shared/                    # Shared domain — auth, billing, orgs
│   ├── models/                # SQLAlchemy models (schema = "shared")
│   │   ├── user.py            # User, UserProfile, UserEmail
│   │   ├── auth.py            # AuthSession, AuthProvider, EmailVerificationToken
│   │   ├── org.py             # Organization, OrgMembership, OrgInvite
│   │   ├── product_access.py  # ProductAccess
│   │   ├── customer.py        # Customer
│   │   ├── plan.py            # Plan
│   │   ├── subscription.py    # Subscription
│   │   ├── payment.py         # PaymentMethod, Transaction
│   │   ├── invoice.py         # Invoice, InvoiceItem
│   │   ├── provider_link.py   # ProviderLink (maps internal IDs to Razorpay/Stripe IDs)
│   │   ├── webhook_event.py   # WebhookEvent
│   │   ├── notification.py    # Notification
│   │   ├── api_key.py         # ApiKey
│   │   ├── feature_flag.py    # FeatureFlag
│   │   └── audit_log.py       # AuditLog
│   ├── repos/                 # Repository classes — THE ONLY way products access shared data
│   │   ├── user_repo.py       # users + profiles + emails
│   │   ├── auth_repo.py       # sessions + providers + verification tokens
│   │   ├── org_repo.py        # orgs + memberships + invites
│   │   ├── product_access_repo.py
│   │   ├── customer_repo.py
│   │   ├── subscription_repo.py  # subscriptions + plans
│   │   ├── payment_repo.py       # payment methods + transactions
│   │   ├── invoice_repo.py       # invoices + items
│   │   ├── provider_link_repo.py # lookup/create provider IDs
│   │   ├── webhook_repo.py       # webhook event dedup + processing
│   │   ├── notification_repo.py
│   │   ├── api_key_repo.py
│   │   ├── feature_flag_repo.py
│   │   └── audit_log_repo.py
│   ├── schemas/               # Pydantic request/response models
│   │   ├── user.py
│   │   ├── auth.py
│   │   ├── org.py
│   │   ├── billing.py         # customer, subscription, plan schemas
│   │   ├── payment.py
│   │   └── invoice.py
│   ├── services/              # Business logic for shared domain
│   │   ├── auth_service.py
│   │   ├── billing_service.py
│   │   ├── payment_provider.py    # Abstract PaymentProvider interface
│   │   ├── razorpay_provider.py   # Razorpay implementation (primary)
│   │   ├── stripe_provider.py     # Stripe implementation (add when needed)
│   │   ├── org_service.py
│   │   └── notification_service.py
│   └── routes/                # Auth endpoints, billing webhooks, user mgmt
│       ├── auth.py
│       ├── users.py
│       ├── orgs.py
│       ├── billing.py
│       └── notifications.py
├── products/
│   ├── product_alpha/         # Self-contained product module
│   │   ├── models/            # SQLAlchemy models (schema = "product_alpha")
│   │   ├── repos/
│   │   ├── schemas/
│   │   ├── services/
│   │   └── routes/
│   ├── product_beta/
│   │   └── ... (same structure)
│   └── product_gamma/
│       └── ... (same structure)
migrations/                    # Alembic
│   ├── env.py
│   ├── versions/
│   │   ├── shared/            # Shared schema migrations
│   │   ├── product_alpha/     # Product-specific migrations
│   │   └── product_beta/
│   └── alembic.ini
tests/
│   ├── shared/
│   ├── product_alpha/
│   └── product_beta/
```

---

## Database Conventions

### Schema Setup

Every product schema must be created before running migrations:

```sql
CREATE SCHEMA IF NOT EXISTS shared;
CREATE SCHEMA IF NOT EXISTS product_alpha;
CREATE SCHEMA IF NOT EXISTS product_beta;
```

### SQLAlchemy Model Convention

All models use a schema-aware base:

```python
# shared model example
class User(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": "shared"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

# product model example
class AlphaOrder(Base):
    __tablename__ = "orders"
    __table_args__ = {"schema": "product_alpha"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False)  # NO ForeignKey to shared.users
    ...
```

**CRITICAL**: Product models reference `user_id` as a plain UUID column, NOT as a ForeignKey to `shared.users`. This is intentional — it keeps schemas decoupled for future extraction.

### Repository Pattern

```python
# app/shared/repos/user_repo.py
class UserRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, user_id: UUID) -> User | None:
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        ...

    async def create(self, email: str, password_hash: str) -> User:
        ...
```

Product services receive repos via dependency injection:

```python
# app/products/product_alpha/services/order_service.py
class OrderService:
    def __init__(self, user_repo: UserRepo, order_repo: OrderRepo):
        self.users = user_repo
        self.orders = order_repo

    async def create_order(self, user_id: UUID, data: CreateOrder):
        user = await self.users.get_by_id(user_id)  # separate query, no JOIN
        if not user:
            raise UserNotFoundError(user_id)
        order = await self.orders.create(user_id=user_id, **data.dict())
        return order
```

---

## Routing Convention

Products are mounted with a prefix in `main.py`:

```python
app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(billing_router, prefix="/api/billing", tags=["billing"])
app.include_router(alpha_router, prefix="/api/alpha", tags=["product_alpha"])
app.include_router(beta_router, prefix="/api/beta", tags=["product_beta"])
```

Each product router is self-contained:

```python
# app/products/product_alpha/routes/orders.py
router = APIRouter()

@router.post("/orders")
async def create_order(
    data: CreateOrderRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_repo = UserRepo(db)
    order_repo = OrderRepo(db)
    service = OrderService(user_repo, order_repo)
    return await service.create_order(current_user.id, data)
```

---

## Auth Convention

- JWT-based auth with access + refresh tokens.
- JWTs include a `products` claim: `["alpha", "beta"]` — which products the user has access to.
- Middleware or dependency checks this claim before allowing access to a product router.
- Password hashing: bcrypt via `passlib`.
- Token storage: `shared.sessions` table for refresh tokens only. Access tokens are stateless.

---

## Billing Convention

- `shared.billing_accounts` table has a `product` column (`VARCHAR`) to distinguish which product the billing is for.
- Each product queries billing filtered by its own product identifier.
- Billing status values: `active`, `trialing`, `past_due`, `canceled`, `inactive`.

---

## Adding a New Product

When adding a new product, follow these steps exactly:

1. Create `app/products/product_name/` with subdirectories: `models/`, `repos/`, `schemas/`, `services/`, `routes/`.
2. All models use `__table_args__ = {"schema": "product_name"}`.
3. Create an Alembic migration to create the schema: `CREATE SCHEMA IF NOT EXISTS product_name;`
4. Mount the router in `main.py` with prefix `/api/product_name`.
5. Add the product identifier to the `PRODUCTS` list in `app/core/config.py`.
6. **Never import from other product modules.**

---

## Migration Strategy (for future extraction)

When a product is ready to be extracted:

1. `pg_dump --schema=product_name` → new Neon instance.
2. Copy the `app/products/product_name/` directory into a new FastAPI project.
3. Copy `app/core/` and `app/shared/repos/` into the new project.
4. Configure two DB connections: one to the original Neon (for shared schema), one to the new instance (for product data).
5. Drop the product schema from the original database.

The shared schema **stays in the original Neon instance forever**. Extracted products connect back to it.

---

## Tech Stack

- **Python 3.11+**
- **FastAPI** with async
- **SQLAlchemy 2.0** (async, mapped_column style preferred)
- **Alembic** for migrations
- **Pydantic v2** for schemas
- **PostgreSQL** on Neon or Supabase
- **asyncpg** as the DB driver
- **passlib[bcrypt]** for password hashing
- **python-jose[cryptography]** for JWT
- **Pytest** + **httpx** for testing

---

## Code Style

- Use `async/await` everywhere — no sync DB calls.
- Type hints on all function signatures.
- Pydantic models for all request/response bodies.
- Repository methods return model instances or `None`, never raw rows.
- Services contain business logic; routes are thin (parse request → call service → return response).
- Use `Depends()` for all dependency injection.

---

## Testing

- Each product has its own test directory.
- Use a test database with schemas created in fixtures.
- Never share test state across products.
- Test services with mocked repos for unit tests.
- Test routes with `httpx.AsyncClient` for integration tests.
