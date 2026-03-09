# Shared Schema — Complete Design

## Overview

The `shared` schema is the single source of truth for identity, profiles, organizations,
authentication, billing, subscriptions, payments, and product access across all products.
It will never be extracted — it stays in the original Neon instance forever and every
product (monolith or extracted) connects to it.

This schema must be **product-agnostic**. It knows products exist (via identifiers), but
knows nothing about what any product does. Product-specific domain logic always lives in
product schemas.

---

## Entity Relationship Summary

```
users
 ├── user_profiles         (1:1 — public-facing profile)
 ├── user_emails            (1:many — multiple verified emails)
 ├── auth_sessions          (1:many — active login sessions)
 ├── auth_providers         (1:many — Google, GitHub OAuth links)
 ├── org_memberships        (many:many with orgs)
 ├── product_access         (1:many — which products user can access)
 ├── customers              (1:1 — billing identity)
 │    ├── subscriptions     (1:many — per-product subscriptions)
 │    ├── payment_methods   (1:many — cards, UPI, netbanking, wallets)
 │    ├── invoices          (1:many)
 │    │    └── invoice_items (1:many)
 │    └── transactions      (1:many — every money movement)
 ├── notifications          (1:many — cross-product notifications)
 └── api_keys               (1:many — per-product API keys)

organizations
 ├── org_memberships        (1:many)
 ├── org_invites            (1:many)
 └── customers              (1:1 — org-level billing)

provider_links              (adapter — maps internal UUIDs to Razorpay/Stripe/etc. IDs)
webhook_events              (idempotent webhook processing log)
feature_flags               (standalone — product-level feature gating)
audit_logs                  (standalone — cross-product audit trail)
```

---

## Tables

### 1. IDENTITY & PROFILES

#### users
The core identity table. Minimal — just auth-critical fields.

```sql
CREATE TABLE shared.users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           TEXT UNIQUE NOT NULL,              -- primary login email
    password_hash   TEXT,                               -- NULL if OAuth-only user
    is_active       BOOLEAN NOT NULL DEFAULT true,
    is_superadmin   BOOLEAN NOT NULL DEFAULT false,     -- platform-level admin
    email_verified  BOOLEAN NOT NULL DEFAULT false,
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_users_email ON shared.users(email);
```

#### user_profiles
Public-facing profile info. Separated from users so products can read profile
data without touching auth-sensitive fields.

```sql
CREATE TABLE shared.user_profiles (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL UNIQUE REFERENCES shared.users(id) ON DELETE CASCADE,
    display_name    TEXT,
    avatar_url      TEXT,
    bio             TEXT,
    website         TEXT,
    timezone        TEXT DEFAULT 'UTC',
    locale          TEXT DEFAULT 'en',
    metadata        JSONB NOT NULL DEFAULT '{}',        -- flexible extra fields
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

#### user_emails
Supports multiple email addresses per user (primary, secondary, work email).
Useful when a user joins different products with different emails and you want
to merge or verify ownership.

```sql
CREATE TABLE shared.user_emails (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES shared.users(id) ON DELETE CASCADE,
    email           TEXT NOT NULL UNIQUE,
    is_primary      BOOLEAN NOT NULL DEFAULT false,
    is_verified     BOOLEAN NOT NULL DEFAULT false,
    verified_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT one_primary_per_user UNIQUE (user_id, is_primary)
);

CREATE INDEX idx_user_emails_user ON shared.user_emails(user_id);
```

---

### 2. AUTHENTICATION

#### auth_sessions
Active login sessions. Tracks refresh tokens so you can revoke per-device.

```sql
CREATE TABLE shared.auth_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES shared.users(id) ON DELETE CASCADE,
    token_hash      TEXT NOT NULL,                      -- hashed refresh token
    device_info     TEXT,                                -- "Chrome on macOS", etc.
    ip_address      INET,
    expires_at      TIMESTAMPTZ NOT NULL,
    last_used_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_auth_sessions_user ON shared.auth_sessions(user_id);
CREATE INDEX idx_auth_sessions_expires ON shared.auth_sessions(expires_at);
```

#### auth_providers
OAuth / social login links. A user can have multiple providers (Google + GitHub).

```sql
CREATE TABLE shared.auth_providers (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES shared.users(id) ON DELETE CASCADE,
    provider        TEXT NOT NULL,                      -- 'google', 'github', 'apple'
    provider_uid    TEXT NOT NULL,                      -- provider's user ID
    provider_email  TEXT,
    provider_data   JSONB NOT NULL DEFAULT '{}',        -- tokens, scopes, raw profile
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT unique_provider_uid UNIQUE (provider, provider_uid),
    CONSTRAINT unique_user_provider UNIQUE (user_id, provider)
);
```

#### email_verification_tokens
Short-lived tokens for email verification, password reset, magic links.

```sql
CREATE TABLE shared.email_verification_tokens (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES shared.users(id) ON DELETE CASCADE,
    token_hash      TEXT NOT NULL UNIQUE,
    token_type      TEXT NOT NULL,                      -- 'email_verify', 'password_reset', 'magic_link'
    email           TEXT NOT NULL,                      -- which email this is for
    expires_at      TIMESTAMPTZ NOT NULL,
    used_at         TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_verification_token ON shared.email_verification_tokens(token_hash);
```

---

### 3. ORGANIZATIONS & TEAMS

#### organizations

```sql
CREATE TABLE shared.organizations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL,
    slug            TEXT UNIQUE NOT NULL,               -- URL-friendly identifier
    logo_url        TEXT,
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_by      UUID REFERENCES shared.users(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_organizations_slug ON shared.organizations(slug);
```

#### org_memberships
Many-to-many between users and organizations with roles.

```sql
CREATE TABLE shared.org_memberships (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES shared.organizations(id) ON DELETE CASCADE,
    user_id         UUID NOT NULL REFERENCES shared.users(id) ON DELETE CASCADE,
    role            TEXT NOT NULL DEFAULT 'member',     -- 'owner', 'admin', 'member', 'viewer'
    joined_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    invited_by      UUID REFERENCES shared.users(id) ON DELETE SET NULL,

    CONSTRAINT unique_org_user UNIQUE (org_id, user_id)
);

CREATE INDEX idx_org_memberships_user ON shared.org_memberships(user_id);
CREATE INDEX idx_org_memberships_org ON shared.org_memberships(org_id);
```

#### org_invites
Pending invitations to join an organization.

```sql
CREATE TABLE shared.org_invites (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES shared.organizations(id) ON DELETE CASCADE,
    email           TEXT NOT NULL,
    role            TEXT NOT NULL DEFAULT 'member',
    token_hash      TEXT NOT NULL UNIQUE,
    invited_by      UUID NOT NULL REFERENCES shared.users(id) ON DELETE CASCADE,
    status          TEXT NOT NULL DEFAULT 'pending',    -- 'pending', 'accepted', 'expired', 'revoked'
    expires_at      TIMESTAMPTZ NOT NULL,
    accepted_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_org_invites_email ON shared.org_invites(email);
CREATE INDEX idx_org_invites_org ON shared.org_invites(org_id);
```

---

### 4. PRODUCT ACCESS

#### product_access
Which products a user (or org) has access to. This is what the JWT `products` claim is built from.

```sql
CREATE TABLE shared.product_access (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES shared.users(id) ON DELETE CASCADE,
    org_id          UUID REFERENCES shared.organizations(id) ON DELETE CASCADE,  -- NULL = personal access
    product         TEXT NOT NULL,                      -- 'alpha', 'beta', 'gamma'
    role            TEXT NOT NULL DEFAULT 'user',       -- 'user', 'admin', 'owner' (product-level role)
    granted_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    granted_by      UUID REFERENCES shared.users(id) ON DELETE SET NULL,
    expires_at      TIMESTAMPTZ,                       -- NULL = never expires (trial could set this)

    CONSTRAINT unique_user_product UNIQUE (user_id, product, org_id)
);

CREATE INDEX idx_product_access_user ON shared.product_access(user_id);
CREATE INDEX idx_product_access_product ON shared.product_access(product);
```

---

### 5. BILLING & PAYMENTS

The billing model is **payment-provider-agnostic**. Your tables store your own billing
state as the source of truth. Provider-specific IDs are stored in a separate
`provider_links` table so you can use Razorpay for one product, Stripe for another,
or switch providers without touching core billing tables.

**Primary provider: Razorpay.** Stripe or others can be added per-product.

#### customers
Billing identity. Can be a user (personal) or an org (team billing).
Exactly one customer per billing entity.

```sql
CREATE TABLE shared.customers (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID UNIQUE REFERENCES shared.users(id) ON DELETE SET NULL,     -- personal billing
    org_id          UUID UNIQUE REFERENCES shared.organizations(id) ON DELETE SET NULL, -- org billing
    email           TEXT NOT NULL,                      -- billing email (may differ from login)
    name            TEXT,                                -- billing name
    phone           TEXT,                                -- important for Razorpay (UPI/phone-based flows)
    currency        TEXT NOT NULL DEFAULT 'inr',        -- 'inr', 'usd', 'eur' — default INR for Razorpay
    tax_id          TEXT,                                -- GSTIN for India, VAT for EU, etc.
    billing_address JSONB,                              -- {line1, line2, city, state, postal_code, country}
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT customer_has_owner CHECK (user_id IS NOT NULL OR org_id IS NOT NULL)
);
```

#### provider_links
Maps your internal entities to external provider IDs. This is the ONLY place
provider-specific IDs live. When you add Stripe for a product, you add rows here —
no schema migration needed.

```sql
CREATE TABLE shared.provider_links (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type     TEXT NOT NULL,
        -- 'customer', 'subscription', 'plan', 'payment_method', 'invoice', 'transaction'
    entity_id       UUID NOT NULL,                      -- FK to our internal table (not enforced, polymorphic)
    provider        TEXT NOT NULL,                      -- 'razorpay', 'stripe', 'paypal', 'lemonsqueezy'
    provider_id     TEXT NOT NULL,                      -- the provider's ID for this entity
    provider_data   JSONB NOT NULL DEFAULT '{}',        -- any extra provider-specific data
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT unique_entity_provider UNIQUE (entity_type, entity_id, provider),
    CONSTRAINT unique_provider_id UNIQUE (provider, provider_id)
);

CREATE INDEX idx_provider_links_entity ON shared.provider_links(entity_type, entity_id);
CREATE INDEX idx_provider_links_provider_id ON shared.provider_links(provider, provider_id);
```

Usage examples:
```
-- Razorpay customer
entity_type='customer', entity_id=<customer_uuid>, provider='razorpay', provider_id='cust_Kj3hF8...'

-- Stripe customer (same internal customer, different product uses Stripe)
entity_type='customer', entity_id=<customer_uuid>, provider='stripe', provider_id='cus_Nk4g...'

-- Razorpay subscription
entity_type='subscription', entity_id=<sub_uuid>, provider='razorpay', provider_id='sub_Lm9p...'

-- Razorpay plan mapped to our plan
entity_type='plan', entity_id=<plan_uuid>, provider='razorpay', provider_id='plan_Ab2c...'
```

#### plans
Product plans / tiers. Defines what each plan offers. Provider-agnostic.

```sql
CREATE TABLE shared.plans (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product         TEXT NOT NULL,                      -- 'alpha', 'beta'
    name            TEXT NOT NULL,                      -- 'Free', 'Pro', 'Enterprise'
    slug            TEXT NOT NULL,                      -- 'alpha-pro', 'beta-free'
    description     TEXT,
    is_active       BOOLEAN NOT NULL DEFAULT true,
    price_monthly   INTEGER NOT NULL DEFAULT 0,         -- in smallest currency unit (paise for INR, cents for USD)
    price_yearly    INTEGER NOT NULL DEFAULT 0,
    currency        TEXT NOT NULL DEFAULT 'inr',
    trial_days      INTEGER NOT NULL DEFAULT 0,
    features        JSONB NOT NULL DEFAULT '{}',        -- {"max_projects": 10, "storage_gb": 5}
    limits          JSONB NOT NULL DEFAULT '{}',        -- {"api_calls_per_month": 10000}
    sort_order      INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT unique_plan_slug UNIQUE (slug)
);

CREATE INDEX idx_plans_product ON shared.plans(product);
```

Note: Provider-specific plan IDs (Razorpay plan_id, Stripe price_id) are stored
in `provider_links`, NOT in this table. To look up the Razorpay plan ID:
```sql
SELECT provider_id FROM shared.provider_links
WHERE entity_type = 'plan' AND entity_id = <plan_uuid> AND provider = 'razorpay';
```
```

#### subscriptions
Active subscriptions. One per customer per product. Provider-agnostic —
maps to Razorpay Subscriptions or Stripe Subscriptions equally.

```sql
CREATE TABLE shared.subscriptions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id     UUID NOT NULL REFERENCES shared.customers(id) ON DELETE CASCADE,
    plan_id         UUID NOT NULL REFERENCES shared.plans(id),
    product         TEXT NOT NULL,                      -- denormalized for fast queries
    status          TEXT NOT NULL DEFAULT 'created',
        -- 'created', 'authenticated', 'active', 'trialing', 'past_due',
        -- 'halted', 'paused', 'canceled', 'completed', 'expired'
        -- (covers both Razorpay and Stripe lifecycle states)
    billing_cycle   TEXT NOT NULL DEFAULT 'monthly',    -- 'monthly', 'yearly', 'lifetime', 'one_time'
    quantity        INTEGER NOT NULL DEFAULT 1,          -- seats / units
    trial_start     TIMESTAMPTZ,
    trial_end       TIMESTAMPTZ,
    current_period_start TIMESTAMPTZ,
    current_period_end   TIMESTAMPTZ,
    cancel_at       TIMESTAMPTZ,                        -- scheduled cancellation
    canceled_at     TIMESTAMPTZ,                        -- when user initiated cancel
    ended_at        TIMESTAMPTZ,                        -- when sub actually ended
    payment_method  TEXT,                                -- 'card', 'upi', 'netbanking', 'wallet', 'emandate'
    auth_attempts   INTEGER NOT NULL DEFAULT 0,          -- Razorpay: track auth retries
    total_count     INTEGER,                             -- Razorpay: total billing cycles (NULL = infinite)
    paid_count      INTEGER NOT NULL DEFAULT 0,          -- how many cycles paid so far
    remaining_count INTEGER,                             -- NULL = infinite
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT unique_customer_product UNIQUE (customer_id, product)
);

CREATE INDEX idx_subscriptions_customer ON shared.subscriptions(customer_id);
CREATE INDEX idx_subscriptions_product ON shared.subscriptions(product);
CREATE INDEX idx_subscriptions_status ON shared.subscriptions(status);
```

Note: Razorpay subscription_id / Stripe subscription_id are in `provider_links`.
```

#### payment_methods
Stored payment methods for a customer. Covers cards, UPI, netbanking, wallets, emandate.

```sql
CREATE TABLE shared.payment_methods (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id     UUID NOT NULL REFERENCES shared.customers(id) ON DELETE CASCADE,
    type            TEXT NOT NULL,
        -- 'card', 'upi', 'netbanking', 'wallet', 'emandate', 'bank_transfer', 'paypal'
    is_default      BOOLEAN NOT NULL DEFAULT false,
    -- card fields (NULL for non-card methods)
    last_four       TEXT,
    brand           TEXT,                                -- 'visa', 'mastercard', 'amex', 'rupay'
    card_network    TEXT,                                -- Razorpay: 'Visa', 'MasterCard', 'RuPay'
    card_type       TEXT,                                -- 'credit', 'debit', 'prepaid'
    exp_month       INTEGER,
    exp_year        INTEGER,
    issuer          TEXT,                                -- issuing bank name
    -- UPI fields (NULL for non-UPI methods)
    upi_id          TEXT,                                -- e.g., 'user@upi'
    -- wallet fields
    wallet_name     TEXT,                                -- 'paytm', 'phonepe', 'amazonpay'
    -- netbanking fields
    bank_name       TEXT,
    bank_code       TEXT,                                -- IFSC or bank identifier
    -- general
    billing_details JSONB,                              -- name, address on payment method
    token_data      JSONB,                              -- Razorpay token / Stripe payment method details
    is_active       BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_payment_methods_customer ON shared.payment_methods(customer_id);
```

Note: Provider-specific token IDs (Razorpay token_id, Stripe pm_id) are in `provider_links`.
```

#### invoices
Generated invoices — one per billing cycle per subscription. Provider-agnostic.

```sql
CREATE TABLE shared.invoices (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id     UUID NOT NULL REFERENCES shared.customers(id) ON DELETE CASCADE,
    subscription_id UUID REFERENCES shared.subscriptions(id) ON DELETE SET NULL,
    invoice_number  TEXT UNIQUE NOT NULL,                -- 'INV-2025-00001'
    status          TEXT NOT NULL DEFAULT 'draft',
        -- 'draft', 'issued', 'paid', 'partially_paid', 'void', 'expired', 'cancelled'
        -- (covers both Razorpay Invoice statuses and Stripe statuses)
    currency        TEXT NOT NULL DEFAULT 'inr',
    subtotal        INTEGER NOT NULL DEFAULT 0,         -- in smallest currency unit (paise/cents)
    tax             INTEGER NOT NULL DEFAULT 0,
    tax_details     JSONB NOT NULL DEFAULT '{}',        -- {cgst, sgst, igst} for Indian GST breakdown
    total           INTEGER NOT NULL DEFAULT 0,
    amount_paid     INTEGER NOT NULL DEFAULT 0,
    amount_due      INTEGER NOT NULL DEFAULT 0,
    period_start    TIMESTAMPTZ,
    period_end      TIMESTAMPTZ,
    due_date        TIMESTAMPTZ,
    paid_at         TIMESTAMPTZ,
    short_url       TEXT,                               -- Razorpay: hosted invoice payment link
    pdf_url         TEXT,
    notes           TEXT,
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_invoices_customer ON shared.invoices(customer_id);
CREATE INDEX idx_invoices_subscription ON shared.invoices(subscription_id);
CREATE INDEX idx_invoices_status ON shared.invoices(status);
```

Note: Razorpay invoice_id / Stripe invoice_id are in `provider_links`.
```

#### invoice_items
Line items on an invoice.

```sql
CREATE TABLE shared.invoice_items (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id      UUID NOT NULL REFERENCES shared.invoices(id) ON DELETE CASCADE,
    description     TEXT NOT NULL,
    quantity        INTEGER NOT NULL DEFAULT 1,
    unit_price      INTEGER NOT NULL,                   -- smallest currency unit
    amount          INTEGER NOT NULL,                   -- quantity * unit_price
    product         TEXT,
    plan_id         UUID REFERENCES shared.plans(id),
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_invoice_items_invoice ON shared.invoice_items(invoice_id);
```

#### transactions
Every money movement — payments, refunds, credits. This is your ledger. Provider-agnostic.

```sql
CREATE TABLE shared.transactions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id     UUID NOT NULL REFERENCES shared.customers(id) ON DELETE CASCADE,
    invoice_id      UUID REFERENCES shared.invoices(id) ON DELETE SET NULL,
    subscription_id UUID REFERENCES shared.subscriptions(id) ON DELETE SET NULL,
    type            TEXT NOT NULL,
        -- 'payment', 'refund', 'credit', 'adjustment', 'payout', 'transfer'
    status          TEXT NOT NULL DEFAULT 'created',
        -- 'created', 'authorized', 'captured', 'processing', 'succeeded', 'failed', 'canceled', 'refunded'
        -- (maps to both Razorpay payment states and Stripe charge states)
    amount          INTEGER NOT NULL,                   -- smallest currency unit (paise/cents), always positive
    currency        TEXT NOT NULL DEFAULT 'inr',
    payment_method_id UUID REFERENCES shared.payment_methods(id) ON DELETE SET NULL,
    method          TEXT,                                -- 'card', 'upi', 'netbanking', 'wallet', 'emandate'
    -- settlement info (Razorpay settles to your bank)
    fee             INTEGER NOT NULL DEFAULT 0,          -- provider fee (paise/cents)
    tax_on_fee      INTEGER NOT NULL DEFAULT 0,          -- GST on provider fee
    net_amount      INTEGER NOT NULL DEFAULT 0,          -- amount - fee - tax_on_fee (what you actually get)
    settled         BOOLEAN NOT NULL DEFAULT false,
    settled_at      TIMESTAMPTZ,
    -- refund tracking
    failure_reason  TEXT,
    refunded_transaction_id UUID REFERENCES shared.transactions(id),
    refund_speed    TEXT,                                -- Razorpay: 'normal', 'optimum', 'instant'
    -- general
    description     TEXT,
    notes           JSONB NOT NULL DEFAULT '{}',         -- Razorpay: notes object, Stripe: metadata
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_transactions_customer ON shared.transactions(customer_id);
CREATE INDEX idx_transactions_invoice ON shared.transactions(invoice_id);
CREATE INDEX idx_transactions_subscription ON shared.transactions(subscription_id);
CREATE INDEX idx_transactions_type ON shared.transactions(type);
CREATE INDEX idx_transactions_status ON shared.transactions(status);
CREATE INDEX idx_transactions_created ON shared.transactions(created_at);
CREATE INDEX idx_transactions_settled ON shared.transactions(settled) WHERE NOT settled;
```

Note: Razorpay payment_id / order_id / Stripe charge_id / payment_intent_id
are in `provider_links`.

#### webhook_events
Idempotent webhook processing. Prevents double-processing of the same event.

```sql
CREATE TABLE shared.webhook_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider        TEXT NOT NULL,                      -- 'razorpay', 'stripe'
    event_id        TEXT NOT NULL,                      -- provider's event/webhook ID
    event_type      TEXT NOT NULL,                      -- 'payment.captured', 'subscription.activated', etc.
    product         TEXT,                               -- which product this webhook is for (if determinable)
    payload         JSONB NOT NULL,                     -- raw webhook body
    status          TEXT NOT NULL DEFAULT 'received',   -- 'received', 'processing', 'processed', 'failed'
    error           TEXT,
    attempts        INTEGER NOT NULL DEFAULT 0,
    processed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT unique_provider_event UNIQUE (provider, event_id)
);

CREATE INDEX idx_webhook_events_type ON shared.webhook_events(event_type);
CREATE INDEX idx_webhook_events_status ON shared.webhook_events(status);
CREATE INDEX idx_webhook_events_created ON shared.webhook_events(created_at);
```
```

---

### 6. PLATFORM UTILITIES

#### notifications
Cross-product notification system. Products write here, the frontend reads.

```sql
CREATE TABLE shared.notifications (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES shared.users(id) ON DELETE CASCADE,
    product         TEXT,                               -- NULL = platform-wide notification
    type            TEXT NOT NULL,                      -- 'info', 'warning', 'billing', 'invite', 'system'
    title           TEXT NOT NULL,
    body            TEXT,
    action_url      TEXT,                               -- deep link into a product
    is_read         BOOLEAN NOT NULL DEFAULT false,
    read_at         TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_notifications_user ON shared.notifications(user_id);
CREATE INDEX idx_notifications_unread ON shared.notifications(user_id, is_read) WHERE NOT is_read;
```

#### api_keys
Per-product API keys for programmatic access.

```sql
CREATE TABLE shared.api_keys (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES shared.users(id) ON DELETE CASCADE,
    org_id          UUID REFERENCES shared.organizations(id) ON DELETE CASCADE,
    product         TEXT NOT NULL,
    name            TEXT NOT NULL,                      -- user-given label
    key_hash        TEXT NOT NULL UNIQUE,               -- hashed API key
    key_prefix      TEXT NOT NULL,                      -- first 8 chars for identification
    scopes          JSONB NOT NULL DEFAULT '[]',        -- ['read', 'write', 'admin']
    last_used_at    TIMESTAMPTZ,
    expires_at      TIMESTAMPTZ,
    is_active       BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_api_keys_hash ON shared.api_keys(key_hash);
CREATE INDEX idx_api_keys_user ON shared.api_keys(user_id);
```

#### feature_flags
Simple feature gating. Products check this to enable/disable features
without redeploying.

```sql
CREATE TABLE shared.feature_flags (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    product         TEXT,                               -- NULL = applies globally
    flag_key        TEXT NOT NULL,                      -- 'new_dashboard', 'beta_export'
    is_enabled      BOOLEAN NOT NULL DEFAULT false,
    rollout_pct     INTEGER NOT NULL DEFAULT 0,         -- 0-100 percentage rollout
    allowed_users   UUID[] DEFAULT '{}',                -- specific user IDs
    allowed_orgs    UUID[] DEFAULT '{}',                -- specific org IDs
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT unique_flag_per_product UNIQUE (product, flag_key)
);
```

#### audit_logs
Immutable audit trail across all products.

```sql
CREATE TABLE shared.audit_logs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES shared.users(id) ON DELETE SET NULL,
    org_id          UUID REFERENCES shared.organizations(id) ON DELETE SET NULL,
    product         TEXT,
    action          TEXT NOT NULL,                      -- 'user.login', 'subscription.created', 'org.member_added'
    resource_type   TEXT,                                -- 'user', 'subscription', 'org'
    resource_id     UUID,
    ip_address      INET,
    user_agent      TEXT,
    old_data        JSONB,                              -- previous state (for updates)
    new_data        JSONB,                              -- new state
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- This table is append-only. Never UPDATE or DELETE.
CREATE INDEX idx_audit_logs_user ON shared.audit_logs(user_id);
CREATE INDEX idx_audit_logs_org ON shared.audit_logs(org_id);
CREATE INDEX idx_audit_logs_product ON shared.audit_logs(product);
CREATE INDEX idx_audit_logs_action ON shared.audit_logs(action);
CREATE INDEX idx_audit_logs_created ON shared.audit_logs(created_at);
```

---

## Repository Layer Mapping

Each logical domain gets its own repo file:

```
app/shared/repos/
├── user_repo.py            # users + user_profiles + user_emails
├── auth_repo.py            # auth_sessions + auth_providers + email_verification_tokens
├── org_repo.py             # organizations + org_memberships + org_invites
├── product_access_repo.py  # product_access
├── customer_repo.py        # customers
├── provider_link_repo.py   # provider_links (lookup/create provider IDs)
├── subscription_repo.py    # subscriptions + plans
├── payment_repo.py         # payment_methods + transactions
├── invoice_repo.py         # invoices + invoice_items
├── webhook_repo.py         # webhook_events
├── notification_repo.py    # notifications
├── api_key_repo.py         # api_keys
├── feature_flag_repo.py    # feature_flags
└── audit_log_repo.py       # audit_logs
```

---

## How Products Use This

### Getting a user's profile from any product:

```python
user_repo = UserRepo(session)
user = await user_repo.get_by_id(user_id)               # from shared.users
profile = await user_repo.get_profile(user_id)           # from shared.user_profiles
```

### Checking if user has an active subscription for this product:

```python
sub_repo = SubscriptionRepo(session)
sub = await sub_repo.get_active(customer_id, product="alpha")
if not sub or sub.status not in ("active", "trialing"):
    raise NoActiveSubscription()
```

### Checking a feature flag:

```python
ff_repo = FeatureFlagRepo(session)
enabled = await ff_repo.is_enabled("new_dashboard", product="alpha", user_id=user_id)
```

### Writing an audit log from any product:

```python
audit_repo = AuditLogRepo(session)
await audit_repo.log(
    user_id=user_id,
    product="alpha",
    action="resource.created",
    resource_type="project",
    resource_id=project_id,
    new_data=project_dict,
)
```

---

## Design Decisions & Rationale

**Why `provider_links` instead of provider columns on each table?**
Adding `stripe_X_id` and `razorpay_X_id` columns to every billing table creates
a mess — you'd need new columns for every provider, and nullable unique constraints
get ugly fast. With `provider_links`, adding a new provider is just inserting rows,
zero schema changes. One product can use Razorpay while another uses Stripe, and
the same customer can exist in both. The lookup is one indexed query:
`SELECT provider_id FROM provider_links WHERE entity_type='customer' AND entity_id=? AND provider='razorpay'`

**Why `webhook_events`?**
Razorpay and Stripe both send webhooks that can arrive multiple times or out of order.
The `unique(provider, event_id)` constraint gives you idempotency for free — if you've
already processed `pay_xyz`, the INSERT fails and you skip it. The `payload` JSONB
stores the raw body so you can replay/debug without going to the provider dashboard.

**Why Razorpay-specific fields like `auth_attempts`, `upi_id`, `refund_speed`?**
These are first-class Razorpay concepts that don't exist in Stripe. Rather than
burying them in metadata (which is hard to query), they get real columns. If you
never use Stripe, these columns just work. If you add Stripe later, these columns
are NULL for Stripe-backed entities — no conflict.

**Why `fee`, `tax_on_fee`, `net_amount` on transactions?**
Razorpay deducts fees before settlement. If a customer pays ₹1000, you might receive
₹976.70 after Razorpay's 2% fee + GST on fee. Tracking this per-transaction is
essential for reconciliation and accounting. Stripe works similarly with application fees.

**Why `customers` is separate from `users`?**
Because billing can be at the org level. An org has one customer record, and the
subscription/invoices attach to the org's customer, not individual users. This also
lets you have a different billing email than the login email.

**Why `plans` is a table and not hardcoded?**
So you can add plans, change pricing, run experiments, and create product-specific
tiers without redeploying. The `features` and `limits` JSONB columns let each product
define its own plan capabilities without schema changes.

**Why `product_access` exists separately from `subscriptions`?**
Because not all access is subscription-based. Free products, beta invites, admin overrides,
and lifetime deals all grant access without a subscription. The JWT `products` claim is
built from `product_access`, not from subscriptions.

**Why all money amounts are integers?**
To avoid floating-point rounding issues. Store paise (INR), cents (USD), etc. The
`currency` field tells the frontend how to format it. ₹499.00 = 49900 paise.

**Why `metadata JSONB` on so many tables?**
Escape hatch. When a future product needs one extra field on customers or subscriptions,
you put it in metadata instead of running a migration. Use sparingly — if you find yourself
querying metadata fields often, promote them to real columns.

**Why audit_logs is append-only?**
Immutability is the whole point. Never UPDATE or DELETE audit records. If you need to
correct something, append a new record. Partition this table by month if it grows large.

---

## Payment Provider Architecture

### How the service layer handles multiple providers

```python
# app/shared/services/payment_provider.py — abstract interface
class PaymentProvider(ABC):
    @abstractmethod
    async def create_customer(self, customer: Customer) -> str: ...  # returns provider_id
    @abstractmethod
    async def create_subscription(self, sub: Subscription, plan_provider_id: str) -> str: ...
    @abstractmethod
    async def capture_payment(self, amount: int, currency: str, ...) -> dict: ...
    @abstractmethod
    async def process_refund(self, transaction_provider_id: str, amount: int) -> dict: ...
    @abstractmethod
    async def verify_webhook(self, headers: dict, body: bytes) -> dict: ...

# app/shared/services/razorpay_provider.py
class RazorpayProvider(PaymentProvider):
    def __init__(self, key_id: str, key_secret: str):
        self.client = razorpay.Client(auth=(key_id, key_secret))

    async def create_customer(self, customer: Customer) -> str:
        result = self.client.customer.create({...})
        return result['id']  # 'cust_Kj3hF8...'
    ...

# app/shared/services/stripe_provider.py (added later)
class StripeProvider(PaymentProvider):
    ...

# app/shared/services/billing_service.py
class BillingService:
    def __init__(self, provider: PaymentProvider, ...):
        self.provider = provider

    async def subscribe(self, customer_id: UUID, plan_id: UUID, product: str):
        # 1. Create/get provider customer
        # 2. Create subscription via provider
        # 3. Store provider_link
        # 4. Create our internal subscription record
        ...
```

### Per-product provider config

```python
# app/core/config.py
class Settings(BaseSettings):
    # Default provider for all products
    DEFAULT_PAYMENT_PROVIDER: str = "razorpay"

    # Per-product overrides (JSON string in env)
    PRODUCT_PAYMENT_PROVIDERS: dict = {
        # "alpha": "razorpay",    (uses default)
        # "beta": "stripe",       (override for this product)
    }

    # Razorpay credentials
    RAZORPAY_KEY_ID: str
    RAZORPAY_KEY_SECRET: str
    RAZORPAY_WEBHOOK_SECRET: str

    # Stripe credentials (optional, add when needed)
    STRIPE_SECRET_KEY: str | None = None
    STRIPE_WEBHOOK_SECRET: str | None = None
```

This way, `billing_service` resolves the right provider per product at runtime.
No code changes needed when you add Stripe for a specific product — just set the
env var and add credentials.
