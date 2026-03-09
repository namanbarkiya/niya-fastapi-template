# Adding a New Product — AI Agent Guide

Copy this entire file as a prompt to an AI coding assistant to scaffold a new product from scratch.

---

## Prompt Template

> **Use this as your starting prompt:**
>
> I'm adding a new product called `{PRODUCT_NAME}` to this FastAPI multi-product backend.
> The product identifier (used in URLs and DB schema) is `{PRODUCT_SLUG}` (lowercase, no spaces).
> Follow ADD_PRODUCT.md exactly and create everything in one pass.

---

## What the AI Must Do — Full Checklist

### 1. Register the product slug in config

File: `app/core/config.py`

Add `"{PRODUCT_SLUG}"` to the `products` list:

```python
products: List[str] = ["alpha", "taskboard", "{PRODUCT_SLUG}"]
```

---

### 2. Create the product directory structure

```
app/products/{PRODUCT_SLUG}/
├── __init__.py
├── models/
│   ├── __init__.py
│   └── {entity}.py          # one file per entity
├── repos/
│   ├── __init__.py
│   └── {entity}_repo.py
├── schemas/
│   ├── __init__.py
│   └── {entity}.py
├── services/
│   ├── __init__.py
│   └── {entity}_service.py
└── routes/
    ├── __init__.py
    ├── {entity}.py
    └── router.py
```

All `__init__.py` files are empty.

---

### 3. Write models

File: `app/products/{PRODUCT_SLUG}/models/{entity}.py`

**Rules — never break these:**

- `__table_args__ = {"schema": "{PRODUCT_SLUG}"}` on every model
- Primary key: `id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)`
- Cross-schema references (e.g., user_id): plain `UUID` column, **NO ForeignKey**
- Within-schema references (entity A → entity B in same product): ForeignKey is fine
- All timestamps: `DateTime(timezone=True)` with `server_default=func.now()`

**Template:**

```python
import uuid
from datetime import datetime
from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.core.database import Base

class {Entity}(Base):
    __tablename__ = "{entities}"
    __table_args__ = {"schema": "{PRODUCT_SLUG}"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    # ... your fields ...
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now())
```

Register models in: `app/products/{PRODUCT_SLUG}/models/__init__.py`

```python
from app.products.{PRODUCT_SLUG}.models.{entity} import {Entity}  # noqa: F401
```

---

### 4. Write repositories

File: `app/products/{PRODUCT_SLUG}/repos/{entity}_repo.py`

**Rules:**

- Constructor: `def __init__(self, session: AsyncSession) -> None`
- Return model instances or `None`, never raw rows
- No business logic — pure data access only
- Use `select()`, `session.execute()`, `session.add()`, `await session.flush()`

**Template:**

```python
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.products.{PRODUCT_SLUG}.models.{entity} import {Entity}

class {Entity}Repo:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, entity_id: UUID) -> {Entity} | None:
        result = await self.session.execute(
            select({Entity}).where({Entity}.id == entity_id)
        )
        return result.scalar_one_or_none()

    async def list_by_user(self, user_id: UUID) -> list[{Entity}]:
        result = await self.session.execute(
            select({Entity}).where({Entity}.user_id == user_id)
        )
        return list(result.scalars().all())

    async def create(self, user_id: UUID, **kwargs) -> {Entity}:
        obj = {Entity}(user_id=user_id, **kwargs)
        self.session.add(obj)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def delete(self, entity_id: UUID) -> None:
        obj = await self.get_by_id(entity_id)
        if obj:
            await self.session.delete(obj)
            await self.session.flush()
```

---

### 5. Write schemas

File: `app/products/{PRODUCT_SLUG}/schemas/{entity}.py`

**Rules:**

- Use Pydantic v2 (`model_config = ConfigDict(from_attributes=True)` on response models)
- Request models: only user-settable fields
- Response models: all fields including id, timestamps

**Template:**

```python
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class Create{Entity}Request(BaseModel):
    name: str
    description: str | None = None

class Update{Entity}Request(BaseModel):
    name: str | None = None
    description: str | None = None

class {Entity}Response(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime | None
```

---

### 6. Write services

File: `app/products/{PRODUCT_SLUG}/services/{entity}_service.py`

**Rules:**

- Always inject `UserRepo` (from shared) + product repos
- For cross-schema user access: call `user_repo.get_by_id()` as a **separate query** — NEVER JOIN
- Ownership checks before any mutation: verify `obj.user_id == user_id`
- Raise `NotFoundError` if object doesn't exist
- Raise `AuthorizationError` if ownership mismatch
- Return Pydantic response models (call `.model_validate(obj)`)

**Template:**

```python
from uuid import UUID
from app.core.exceptions import NotFoundError, AuthorizationError
from app.shared.repos.user_repo import UserRepo
from app.products.{PRODUCT_SLUG}.repos.{entity}_repo import {Entity}Repo
from app.products.{PRODUCT_SLUG}.schemas.{entity} import (
    Create{Entity}Request, Update{Entity}Request, {Entity}Response
)

class {Entity}Service:
    def __init__(self, user_repo: UserRepo, {entity}_repo: {Entity}Repo) -> None:
        self.users = user_repo
        self.{entities} = {entity}_repo

    async def list_{entities}(self, user_id: UUID) -> list[{Entity}Response]:
        items = await self.{entities}.list_by_user(user_id)
        return [{Entity}Response.model_validate(i) for i in items]

    async def get_{entity}(self, user_id: UUID, {entity}_id: UUID) -> {Entity}Response:
        obj = await self._get_owned(user_id, {entity}_id)
        return {Entity}Response.model_validate(obj)

    async def create_{entity}(self, user_id: UUID, payload: Create{Entity}Request) -> {Entity}Response:
        user = await self.users.get_by_id(user_id)  # cross-schema: separate query
        if not user:
            raise NotFoundError("User not found")
        obj = await self.{entities}.create(user_id=user_id, **payload.model_dump())
        return {Entity}Response.model_validate(obj)

    async def update_{entity}(self, user_id: UUID, {entity}_id: UUID, payload: Update{Entity}Request) -> {Entity}Response:
        obj = await self._get_owned(user_id, {entity}_id)
        data = payload.model_dump(exclude_unset=True)
        for k, v in data.items():
            setattr(obj, k, v)
        await self.{entities}.session.flush()
        await self.{entities}.session.refresh(obj)
        return {Entity}Response.model_validate(obj)

    async def delete_{entity}(self, user_id: UUID, {entity}_id: UUID) -> dict:
        obj = await self._get_owned(user_id, {entity}_id)
        await self.{entities}.delete(obj.id)
        return {"status": "success", "message": "{Entity} deleted"}

    async def _get_owned(self, user_id: UUID, {entity}_id: UUID):
        obj = await self.{entities}.get_by_id({entity}_id)
        if not obj:
            raise NotFoundError("{Entity} not found")
        if obj.user_id != user_id:
            raise AuthorizationError("You do not have access to this {entity}")
        return obj
```

---

### 7. Write routes

File: `app/products/{PRODUCT_SLUG}/routes/{entity}.py`

**Rules:**

- Routes are thin: parse → call service → return
- Always depend on `get_current_user` and `get_db`
- Build service inside route using both repos sharing the same `db` session

**Template:**

```python
from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.shared.models.user import User
from app.shared.repos.user_repo import UserRepo
from app.products.{PRODUCT_SLUG}.repos.{entity}_repo import {Entity}Repo
from app.products.{PRODUCT_SLUG}.schemas.{entity} import (
    Create{Entity}Request, Update{Entity}Request, {Entity}Response
)
from app.products.{PRODUCT_SLUG}.services.{entity}_service import {Entity}Service

router = APIRouter()

def _svc(db: AsyncSession) -> {Entity}Service:
    return {Entity}Service(UserRepo(db), {Entity}Repo(db))

@router.get("", response_model=list[{Entity}Response])
async def list_{entities}(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _svc(db).list_{entities}(current_user.id)

@router.post("", response_model={Entity}Response, status_code=201)
async def create_{entity}(
    payload: Create{Entity}Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _svc(db).create_{entity}(current_user.id, payload)

@router.get("/{{{entity}_id}}", response_model={Entity}Response)
async def get_{entity}(
    {entity}_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _svc(db).get_{entity}(current_user.id, {entity}_id)

@router.patch("/{{{entity}_id}}", response_model={Entity}Response)
async def update_{entity}(
    {entity}_id: UUID,
    payload: Update{Entity}Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _svc(db).update_{entity}(current_user.id, {entity}_id, payload)

@router.delete("/{{{entity}_id}}")
async def delete_{entity}(
    {entity}_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _svc(db).delete_{entity}(current_user.id, {entity}_id)
```

File: `app/products/{PRODUCT_SLUG}/routes/router.py`

```python
from fastapi import APIRouter
from app.products.{PRODUCT_SLUG}.routes.{entity} import router as {entity}_router

router = APIRouter()
router.include_router({entity}_router, prefix="/{entities}", tags=["{PRODUCT_SLUG}:{entities}"])
```

---

### 8. Register in main.py

Add these two lines in `app/main.py`:

```python
# At the top with other model imports:
import app.products.{PRODUCT_SLUG}.models  # noqa: F401

# With other router imports:
from app.products.{PRODUCT_SLUG}.routes.router import router as {PRODUCT_SLUG}_router

# With other app.include_router calls:
app.include_router({PRODUCT_SLUG}_router, prefix="/api/{PRODUCT_SLUG}", tags=["{PRODUCT_SLUG}"])
```

---

### 9. Create Alembic migration

File: `migrations/versions/{PRODUCT_SLUG}/001_initial.py`

```python
"""
{PRODUCT_NAME} — initial schema

Revision ID: {PRODUCT_SLUG}_001
Revises: (set to last shared migration ID, e.g. "005_product_clients")
Create Date: {TODAY}
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "{PRODUCT_SLUG}_001"
down_revision: Union[str, None] = "005_product_clients"  # update to latest
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS {PRODUCT_SLUG}")

    op.create_table(
        "{entities}",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        schema="{PRODUCT_SLUG}",
    )


def downgrade() -> None:
    op.drop_table("{entities}", schema="{PRODUCT_SLUG}")
    op.execute("DROP SCHEMA IF EXISTS {PRODUCT_SLUG} CASCADE")
```

---

### 10. Seed a client key

After running `alembic upgrade head`, seed the new product's client key:

```bash
python scripts/seed_product_clients.py
```

This generates `pk_{PRODUCT_SLUG}_{random}` and prints it. Add it as `X-Product-Client-Key` in Postman and to the frontend `.env`.

**Safe to run on a live system** — the script skips any product that already has an active key. Only the new product gets a key generated. Existing keys are never touched unless you explicitly pass `--force`.

---

## Constraints the AI must never violate

| Rule              | Correct                                         | Wrong                           |
| ----------------- | ----------------------------------------------- | ------------------------------- |
| Schema            | `__table_args__ = {"schema": "{PRODUCT_SLUG}"}` | No schema or wrong schema       |
| Cross-schema ref  | Plain `UUID` column                             | `ForeignKey("shared.users.id")` |
| Cross-schema data | Two separate queries                            | SQL JOIN across schemas         |
| Product isolation | Import only from `app/core/` and `app/shared/`  | Import from another product     |
| Primary keys      | UUID only                                       | Serial integer                  |
| Timestamps        | `DateTime(timezone=True)`                       | `DateTime()` without tz         |
| Business logic    | In service layer                                | In routes or repos              |

---

## Quick sanity checklist before finishing

- [ ] `products` list in `config.py` includes the new slug
- [ ] Every model has `__table_args__ = {"schema": "..."}` with the correct slug
- [ ] No `ForeignKey` pointing to `shared.*` tables
- [ ] `main.py` has both the model import and `app.include_router` call
- [ ] Migration creates the schema before the tables
- [ ] `seed_product_clients.py` has been run and key is saved
- [ ] Routes depend on `get_current_user` and `get_db`
- [ ] Services receive repos via constructor, not via imports
