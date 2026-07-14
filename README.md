# ATH — AI-Augmented ERP Platform

> Multi-tenant SaaS ERP for SMEs (retail, pharmacy, distributors) covering inventory, POS, procurement, and finance — with GPT-5.2-powered natural-language querying and demand forecasting.

**Live demo credentials:** `owner@demo.ath` / `demo1234`

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Server Architecture](#2-server-architecture)
3. [API Reference](#3-api-reference)
4. [AI Integrations](#4-ai-integrations)
5. [Future Scaling](#5-future-scaling)
6. [Local Setup](#6-local-setup)

---

## 1. Project Overview

### What it does

ATH is a production-grade, opinionated ERP built for small and medium businesses that outgrow Excel but can't afford SAP. It unifies five ops surfaces on a single tenant-isolated data plane:

| Module | What ships today |
|---|---|
| **Auth & Tenants** | Email/password + Google Sign-in, JWT, 5 RBAC roles (Owner, Manager, Cashier, Warehouse, Accountant), tenant-scoped data isolation on every collection |
| **Inventory** | Product catalog (SKU/barcode/tax), multi-location stock levels, batch + expiry tracking (pharmacy), weighted-average costing, stock-movement ledger, low-stock + expiry alerts |
| **Sales / POS** | Fast barcode/search POS, cart with keyboard shortcuts, GST invoice generation, split payment modes, refunds with stock restore, printable receipts |
| **Procurement** | Supplier records, purchase orders (draft → sent → received), Goods Receipt Notes (GRN) with batch/expiry capture and auto stock-in |
| **Finance** | Auto GST invoicing from POS, manual expense entries, P&L (revenue / COGS / gross / net / tax collected) |
| **AI Layer** | Natural-language query (English → Mongo aggregation, tenant-scoped), 30-day demand forecast per SKU with reorder-quantity suggestions, LLM-narrated business insights |
| **Dashboard** | 6 KPIs (revenue, orders, stock value, low-stock, expiring, pending POs) + sales trend line + top-products bar + category-mix pie + AI insights panel |

### Design principles

- **Dense, data-first UI** — Linear meets QuickBooks, dark theme by default, tabular figures, one accent color (blue-500). No purple gradients, no AI-slop aesthetics.
- **Tenant isolation is inviolable** — every query carries `tenant_id`. Even the NLQ endpoint injects a `$match: {tenant_id: ...}` as the first stage before any LLM-generated pipeline runs.
- **Keyboard-first for operators** — `Ctrl+K` opens NLQ from anywhere; `Space` completes POS checkout.
- **Deterministic + probabilistic split** — deterministic code owns invariants (stock, money, RBAC); the LLM only proposes queries and narrations that are sanitized before execution.

---

## 2. Server Architecture

### Runtime topology

```
                  ┌─────────────────────────────────────────┐
                  │   Kubernetes Ingress                    │
                  │   /api/*  → 8001  (FastAPI)             │
                  │   /*      → 3000  (React)               │
                  └────────────┬────────────────────────────┘
                               │
                   ┌───────────┴───────────┐
                   │                       │
             ┌─────▼─────┐          ┌──────▼──────┐
             │  React    │          │  FastAPI    │
             │  CRA SPA  │          │  Uvicorn    │
             │  :3000    │          │  :8001      │
             └─────┬─────┘          └──────┬──────┘
                   │                       │
                   │                       ├───► MongoDB (Motor async)
                   │                       │      • tenants, users, sessions
                   │                       │      • products, batches, stock_levels, stock_movements
                   │                       │      • sales, customers, suppliers, purchase_orders
                   │                       │      • expenses, categories, locations
                   │                       │
                   │                       ├───► Emergent LLM Gateway
                   │                       │      (GPT-5.2 via emergentintegrations)
                   │                       │
                   └───────────────────────┴───► Emergent Google Auth
                                                (auth.emergentagent.com)
```

### Backend module layout (`/app/backend/`)

```
server.py              # FastAPI entry, router registration, indexes, auto-seed on startup
db.py                  # Motor client + tenant-scope helpers
auth.py                # bcrypt password hashing, JWT sign/verify, RBAC dependencies
models.py              # All Pydantic models (BaseDoc carries tenant_id + id + created_at)
seed.py                # Demo retail tenant with 20 SKUs + 45 days of sales history
routes_auth.py         # /auth/signup, /login, /me, /google/session, /invite, /users
routes_inventory.py    # Products, categories, locations, batches, alerts, stock adjustment
routes_pos.py          # POS checkout, sales listing, refund, customers
routes_procurement.py  # Suppliers, POs, GRN (auto stock-in + batch capture)
routes_finance.py      # Expenses + P&L aggregation
routes_dashboard.py    # KPI summary + chart data (30-day trend, top products, category mix)
routes_ai.py           # NLQ (schema-aware GPT-5.2), demand forecast, insights narrator
```

Every router mounts under `/api` (Kubernetes ingress requirement), and every FastAPI dependency chain funnels through `get_current` (JWT → `AuthContext(user_id, tenant_id, role)`) → optional `require_roles(...)`.

### Data model — key contracts

**Tenant isolation contract.** Every collection except `tenants` carries `tenant_id`. `BaseDoc` in `models.py` enforces this at the type level. On startup, `server.py` creates a compound index `(tenant_id, 1)` on all 12 tenant-scoped collections. Uniqueness constraints (`email`, `sku`) use compound indexes so tenants can independently reuse SKUs.

**Stock is a materialized view.** Two collections form the source of truth:
- `stock_movements` — append-only signed-quantity ledger (`+in`, `-out`), tagged by `kind` (`sale`, `purchase`, `adjustment`, `transfer`, `return`).
- `stock_levels` — cached `{tenant_id, product_id, location_id, qty, avg_cost}` for O(1) reads.

The `_apply_movement()` helper in `routes_inventory.py` is the only writer; POS checkout, GRN receipt, and manual adjustment all funnel through it. It recomputes weighted-average cost on incoming stock.

**Invoices are deterministic.** `INV-000001` sequence is a per-tenant `count_documents + 1`. Same for `PO-00001`. No global counters — tenants stay isolated even in numbering.

### Auth flow

Two entry points converge on one JWT:

**Email/password** — `POST /api/auth/signup` creates `{tenant, default location, owner user}` in one call. `POST /api/auth/login` verifies bcrypt and issues a JWT.

**Google (Emergent-managed)** — Frontend redirects to `https://auth.emergentagent.com/?redirect=<origin>/`. On return, `session_id` is in the URL hash. Frontend posts it as `X-Session-ID` to `POST /api/auth/google/session`. Backend calls `https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data`, then applies **Option-C multi-tenant logic**:
- Known email → log into their existing tenant with existing role.
- New email → auto-create tenant + Owner user.

Both flows return the same JWT payload `{sub, tid, role, exp}` (HS256, 7-day expiry, HTTP `Authorization: Bearer`).

### RBAC

```python
Owner       → everything
Manager     → products, POs, sales, customers, invites, expenses
Cashier     → POS checkout only
Warehouse   → products, stock adjust, GRN
Accountant  → expenses, P&L
```

Route-level enforcement via `Depends(require_roles("owner", "manager"))`. Roles are baked into the JWT; a role change requires re-login.

---

## 3. API Reference

Base URL: `${REACT_APP_BACKEND_URL}/api`. All authenticated endpoints require `Authorization: Bearer <jwt>`.

### Auth

| Method | Path | Role | Purpose |
|---|---|---|---|
| POST | `/auth/signup` | public | Create tenant + owner user, return JWT |
| POST | `/auth/login` | public | Email/password login |
| POST | `/auth/google/session` | public | Exchange Emergent session_id for JWT |
| GET  | `/auth/me` | any | Current user + tenant |
| GET  | `/auth/users` | owner/manager | List tenant members |
| POST | `/auth/invite` | owner/manager | Create team member with role + temp password |

### Inventory

| Method | Path | Role | Purpose |
|---|---|---|---|
| GET  | `/inventory/products?q=` | any | List with search filter, includes computed stock totals |
| GET  | `/inventory/products/{id}` | any | Detail |
| POST | `/inventory/products` | owner/manager/warehouse | Create |
| PUT  | `/inventory/products/{id}` | owner/manager/warehouse | Update |
| DELETE | `/inventory/products/{id}` | owner/manager | Delete |
| GET  | `/inventory/locations` | any | List locations |
| POST | `/inventory/locations` | owner/manager | Create location |
| GET  | `/inventory/categories` | any | List |
| POST | `/inventory/categories` | owner/manager | Create |
| POST | `/inventory/adjust` | owner/manager/warehouse | Manual stock delta |
| GET  | `/inventory/movements?product_id=` | any | Recent 200 movements |
| GET  | `/inventory/alerts` | any | `{low_stock: [...], expiring: [...]}` |

### POS / Sales

| Method | Path | Role | Purpose |
|---|---|---|---|
| POST | `/pos/sales` | owner/manager/cashier | Checkout — deducts stock, generates invoice, records movements |
| GET  | `/pos/sales?limit=` | any | Recent sales |
| GET  | `/pos/sales/{id}` | any | Detail |
| POST | `/pos/sales/{id}/refund` | owner/manager | Restore stock, mark refunded |
| GET  | `/pos/customers?q=` | any | Search customers |
| POST | `/pos/customers` | any | Create customer |

### Procurement

| Method | Path | Role | Purpose |
|---|---|---|---|
| GET  | `/procurement/suppliers` | any | List |
| POST | `/procurement/suppliers` | owner/manager | Create |
| GET  | `/procurement/pos` | any | List POs |
| GET  | `/procurement/pos/{id}` | any | Detail |
| POST | `/procurement/pos` | owner/manager | Create PO (status=sent) |
| POST | `/procurement/grn` | owner/manager/warehouse | Receive goods — stock-in + batch/expiry capture, updates PO to `partial`/`received` |

### Finance

| Method | Path | Role | Purpose |
|---|---|---|---|
| GET  | `/finance/expenses` | any | List |
| POST | `/finance/expenses` | owner/manager/accountant | Create expense |
| GET  | `/finance/pnl` | any | Revenue, COGS, gross, expenses, net, tax collected |

### Dashboard

| Method | Path | Role | Purpose |
|---|---|---|---|
| GET  | `/dashboard/summary` | any | 6 KPIs + 30-day trend + top products + category mix |

### AI

| Method | Path | Role | Purpose |
|---|---|---|---|
| POST | `/ai/nlq` | any | English question → sanitized Mongo aggregation → rows + chart hint |
| GET  | `/ai/forecast` | any | Per-SKU 30-day demand forecast + reorder quantity |
| GET  | `/ai/insights` | any | LLM-generated 3-4 bullet business narrative |

### Response conventions

- **Success**: JSON body with the resource shape (or `{ok: true}` for side-effect-only endpoints).
- **Error**: `{"detail": "message"}` with HTTP `400` (client error), `401` (auth), `403` (RBAC), `404` (not found), `500` (server).
- **Timestamps**: All `created_at` stored as ISO-8601 UTC strings (not native BSON dates) — makes tenant-scoped range queries cheap without timezone gymnastics.
- **IDs**: UUIDv4 strings on every doc's `id` field. Mongo's `_id` is projected out of every response.

---

## 4. AI Integrations

### 4.1 GPT-5.2 via Emergent Universal Key

All LLM calls route through the `emergentintegrations` Python library using a single `EMERGENT_LLM_KEY`. This gives us:

- Zero SDK juggling — one key covers OpenAI (GPT-5.2), Anthropic (Claude), Gemini.
- Emergent handles rate-limits, retries, and billing.
- Model swap is a one-line change (`chat.with_model("anthropic", "claude-sonnet-4-6")`).

The provider/model are pinned in `routes_ai.py`:

```python
LLM_PROVIDER = "openai"
LLM_MODEL = "gpt-5.2"
```

### 4.2 Natural Language Query (NLQ)

**Pattern**: English → schema-aware system prompt → GPT-5.2 → JSON `{collection, pipeline, chart, explanation}` → sanitizer → Mongo `aggregate()` → typed table/chart back to UI.

**Why it's safe against prompt injection and data leaks**:

1. **System prompt hardcodes the schema and rules** (`SCHEMA_DESCRIPTION` in `routes_ai.py`): only 8 allowed collections listed; read-only aggregations; must return JSON.
2. **Sanitizer runs after LLM output** (`_sanitize_pipeline()`):
   - Strips any `$out` / `$merge` stages (no writes).
   - **Prepends a hardcoded `$match: {tenant_id: <ctx.tenant_id>}` as the FIRST stage**, overriding whatever the LLM produced. Cross-tenant leak is structurally impossible.
   - Whitelists collection name against a Python `set`.
   - Appends `$limit: 200` unconditionally.
3. **Result rows have `_id` popped** before JSON serialization.

**Example**

```
User: "What were my top 5 products last month?"

GPT-5.2 emits:
{
  "collection": "sales",
  "pipeline": [
    {"$match": {"created_at": {"$gte": "2026-06-01", "$lt": "2026-07-01"}}},
    {"$unwind": "$lines"},
    {"$group": {"_id": "$lines.product_id",
                "name": {"$first": "$lines.name"},
                "sku": {"$first": "$lines.sku"},
                "qty_sold": {"$sum": "$lines.qty"},
                "revenue": {"$sum": "$lines.line_total"}}},
    {"$sort": {"revenue": -1}},
    {"$limit": 5}
  ],
  "chart": "bar",
  "explanation": "Top 5 products by revenue in June 2026"
}

Sanitizer prepends {$match: {tenant_id: "<current>"}} and adds {$limit: 200}.
Motor executes. Rows return to frontend, rendered as a bar chart.
```

### 4.3 Demand forecasting

Deterministic, **not** LLM-driven — the LLM is bad at arithmetic. `GET /api/ai/forecast`:

1. Pulls all sales from the last 60 days (tenant-scoped).
2. Aggregates quantity per product per day.
3. Computes `avg_daily = total_60d / 60`.
4. Forecasts `forecast_30d = avg_daily × 30`.
5. Suggests `reorder_qty = max(0, forecast_30d − current_stock + (avg_daily × lead_time_days))`.

Fast, explainable, defensible in an audit. LLM is only invoked for the **narrative** insights panel (`/ai/insights`), where hallucination cost is low.

### 4.4 Sign in with Google (Emergent-managed OAuth)

- Frontend redirects to `auth.emergentagent.com` with a dynamic `redirect=window.location.origin/` (never hardcoded — this is the #1 gotcha the Emergent playbook flags).
- Google auth completes → user returns to `/#session_id=xxx`.
- `AppRoutes` intercepts the hash **synchronously during render** (not in a `useEffect`, to prevent a race with `ProtectedRoute`) and renders `AuthCallback`.
- Frontend `POST /api/auth/google/session` with `X-Session-ID` header.
- Backend calls Emergent's `session-data` endpoint, applies Option-C tenant logic, returns our own JWT.

---

## 5. Future Scaling

### 5.1 Data plane

**Sharding key: `tenant_id`.** Every collection is already partitioned this way. When Mongo Atlas becomes the bottleneck, enabling sharding on `{tenant_id: "hashed"}` is a config change, not a schema change.

**Cold-tier stock movements.** `stock_movements` grows fastest. When a tenant crosses ~1M rows, move rows older than 12 months to a `stock_movements_archive` collection. All KPIs use ≤60-day windows, so the hot collection stays small.

**Read replicas for reports.** `GET /dashboard/summary` and `/ai/nlq` are read-heavy and eventually-consistent-safe. Route these through a read secondary once volume warrants.

**Materialized denormalizations.** Today `stock_levels` is a manually maintained view of `stock_movements`. At 10x scale, add nightly rebuild jobs that reconcile and a Redis cache for the hottest KPIs.

### 5.2 Compute plane

**Stateless backend.** FastAPI holds no session state (JWT is self-contained). Horizontal scaling is `replicas: N` — no sticky sessions, no shared memory. Uvicorn workers can multiply per pod.

**Move heavy AI calls off the request path.** NLQ and forecast are currently synchronous. For tenants with 100k+ products, forecast should run nightly (cron / Celery / RQ) and cache results in `forecast_cache` keyed by `(tenant_id, day)`. `/ai/nlq` can move to Server-Sent Events streaming (`stream_message()` is already supported by `emergentintegrations`).

**Background job runner.** Introduce a worker process (RQ or Celery + Redis) for:
- Nightly forecasts
- Low-stock and expiry alert emails (via Resend)
- Batch invoice PDF generation
- Data export jobs

### 5.3 Multi-region / multi-currency

- **Tenant.currency** already exists (default INR). Rate conversion is stubbed. When onboarding non-INR tenants, add a nightly rate fetch from Alpha Vantage or Fixer.
- Multi-region deployment is a Kubernetes concern. Mongo Atlas Global Clusters can pin `tenant_id` prefixes to specific regions for data-residency compliance (e.g., EU tenants → Frankfurt shard).

### 5.4 Compliance layer

- **GDPR / DPDP** — every collection already has `tenant_id`; per-tenant purge is a single `deleteMany({tenant_id})` per collection. Add a `POST /api/tenants/{id}/delete-all-data` endpoint gated by Owner + email confirmation.
- **HIPAA for pharmacy tenants** — encryption at rest is Mongo Atlas native; encryption in transit is enforced by ingress. Add audit-log trail (append-only `audit_logs` collection) on every mutation.
- **PCI-DSS** — out of scope today (we don't touch card data; Stripe hosts it). Stays out of scope as long as payments go through Stripe Checkout.

### 5.5 Observability

Not implemented in MVP. Recommended additions:
- **Structured logs** — replace Python `logging` with `structlog`, ship to Loki or Datadog.
- **Metrics** — expose `/metrics` (Prometheus) with per-tenant request rates, LLM call latency, Mongo query duration.
- **Traces** — OpenTelemetry auto-instrumentation for FastAPI + Motor; span the LLM calls too.
- **Error tracking** — Sentry SDK on both frontend and backend.

### 5.6 Deployment lanes

Today: single Emergent preview environment. Recommended progression:

1. **Dev** — current preview URL
2. **Staging** — separate Mongo DB, isolated LLM key, seeded with anonymized production sample
3. **Production** — Mongo Atlas M10+, dedicated LLM key with billing alerts, Cloudflare in front, health checks on `/api/`

---

## 6. Local Setup

### Prerequisites

- Python 3.11, Node.js 20+, MongoDB 6+, Yarn (never npm — package.json is Yarn-locked)

### Environment variables

**`/app/backend/.env`**
```
MONGO_URL="mongodb://localhost:27017"
DB_NAME="ath_erp"
CORS_ORIGINS="*"
EMERGENT_LLM_KEY=<from Emergent Profile → Universal Key>
JWT_SECRET=<random 32+ char string>
JWT_ALGORITHM=HS256
JWT_EXPIRE_HOURS=168
```

**`/app/frontend/.env`**
```
REACT_APP_BACKEND_URL=https://<your-preview>.preview.emergentagent.com
WDS_SOCKET_PORT=443
```

### Run

Both services are supervised on the Emergent platform — no manual start needed. For local:

```bash
# backend
cd /app/backend && pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8001 --reload

# frontend
cd /app/frontend && yarn install && yarn start
```

Auto-seed runs on backend startup. Demo tenant is created idempotently — subsequent restarts skip re-seeding.

### Testing endpoints

```bash
# Login and grab a token
TOKEN=$(curl -s -X POST http://localhost:8001/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"owner@demo.ath","password":"demo1234"}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')

# Try the AI NLQ
curl -X POST http://localhost:8001/api/ai/nlq \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"question":"What were my top 5 products last month?"}' | jq
```

---

## License

Proprietary — built on the Emergent platform.
