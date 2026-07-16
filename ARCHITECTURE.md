# Smart Ledger — Server Architecture

## Overview

Smart Ledger follows a classic **client–server** architecture with a React SPA on the frontend and a FastAPI async backend, both communicating over a REST JSON API. All data lives in a single MongoDB cluster, isolated per business tenant by a `tenant_id` field on every document.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT  (Browser)                              │
│                                                                             │
│   React 19  •  React Router v7  •  TanStack Query  •  shadcn/ui            │
│                                                                             │
│   Pages: Dashboard │ POS │ Inventory │ Procurement │ Finance │ AI Insights  │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │  HTTPS  REST  JSON  /api/*
                                 │
┌────────────────────────────────▼────────────────────────────────────────────┐
│                           BACKEND  (FastAPI + Uvicorn)                      │
│                                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────┐  │
│  │  /auth   │  │/inventory│  │   /pos   │  │/procure- │  │  /finance   │  │
│  │          │  │          │  │          │  │  ment    │  │             │  │
│  │ Signup   │  │ Products │  │  Sales   │  │Suppliers │  │  Expenses   │  │
│  │ Login    │  │  Stock   │  │ Checkout │  │   POs    │  │   P&L       │  │
│  │ OAuth    │  │  Batches │  │ Refunds  │  │   GRN    │  │             │  │
│  │ Invite   │  │  Alerts  │  │Customers │  │          │  │             │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └─────────────┘  │
│                                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────┐  │
│  │/dashboard│  │   /ai    │  │/payments │  │ /notify  │  │/tts /uploads│  │
│  │          │  │          │  │          │  │          │  │             │  │
│  │  KPI     │  │   NLQ    │  │ Razorpay │  │  Twilio  │  │ ElevenLabs  │  │
│  │  Trends  │  │Forecast  │  │  Orders  │  │  SMS     │  │ Cloudinary  │  │
│  │  Top SKU │  │Insights  │  │  Verify  │  │WhatsApp  │  │             │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └─────────────┘  │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │               Auth Middleware  (JWT + RBAC)                         │   │
│  │   get_current() → AuthContext { user_id, tenant_id, role }          │   │
│  │   require_roles("owner","manager") dependency guard                 │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │  Motor (async)
                                 │
┌────────────────────────────────▼────────────────────────────────────────────┐
│                            MongoDB  (Atlas or local)                        │
│                                                                             │
│  Collections (all indexed on tenant_id):                                    │
│                                                                             │
│  tenants │ users │ locations │ categories │ products │ batches             │
│  stock_levels │ stock_movements │ customers │ sales                        │
│  suppliers │ purchase_orders │ expenses                                    │
│  notifications │ razorpay_orders                                           │
│                                                                             │
│  Unique indexes: users.email │ (tenant_id, sku) on products               │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Request Lifecycle

```
Browser Request
    │
    ▼
CORS Middleware  (FastAPI CORSMiddleware)
    │
    ▼
Route Handler  (e.g. POST /api/pos/sales)
    │
    ├─► JWT Dependency  get_current()
    │       ├─ Decode JWT → user_id, tenant_id, role
    │       └─ Return AuthContext
    │
    ├─► Role Guard  require_roles(["owner","manager"])  (if present)
    │
    ├─► Pydantic Model validation  (request body)
    │
    ▼
Business Logic
    │
    ├─► Motor  (async MongoDB queries — always filtered by tenant_id)
    │
    └─► External APIs  (OpenAI / Razorpay / Twilio / ElevenLabs / Cloudinary)
            │
            ▼
    JSON Response  →  Browser
```

---

## Component Breakdown

### Frontend (`frontend/src/`)

```
App.js
 ├── AuthProvider (Context)          # JWT store, login/logout, token refresh
 ├── BrowserRouter
 │    ├── /login  /signup            # Public routes
 │    └── /  (Protected)
 │         ├── Layout.jsx            # Sidebar nav shell
 │         ├── /              → Dashboard.jsx
 │         ├── /inventory     → Inventory.jsx
 │         ├── /pos           → POS.jsx
 │         ├── /sales         → Sales.jsx
 │         ├── /procurement   → Procurement.jsx
 │         ├── /finance       → Finance.jsx
 │         ├── /ai            → AIInsights.jsx
 │         ├── /notifications → Notifications.jsx
 │         └── /settings      → Settings.jsx
 └── NLQDialog.jsx                   # AI query modal (accessible from any page)
```

State management follows a **server-state** pattern — TanStack Query owns all remote data (caching, invalidation, background refresh). No global Redux/Zustand store. Auth state lives in React Context.

### Backend (`backend/`)

```
server.py                  # App factory, lifespan, CORS, router mounting
├── db.py                  # Motor client singleton
├── auth.py                # JWT issue/verify, AuthContext, RBAC guards
├── models.py              # All Pydantic models (BaseDoc, Product, Sale, …)
├── seed.py                # Demo data — auto-runs on startup
│
├── routes_auth.py         # /api/auth/*
├── routes_inventory.py    # /api/inventory/*
├── routes_pos.py          # /api/pos/*
├── routes_procurement.py  # /api/procurement/*
├── routes_finance.py      # /api/finance/*
├── routes_dashboard.py    # /api/dashboard/*
├── routes_ai.py           # /api/ai/*
├── routes_payments.py     # /api/payments/*
├── routes_notifications.py# /api/notify/*
├── routes_tts.py          # /api/tts/*
└── routes_uploads.py      # /api/uploads/*
```

---

## Data Model — Entity Relationships

```
Tenant (1)
 ├──── User (N)           role: owner | manager | cashier | warehouse | accountant
 ├──── Location (N)       store branches / warehouses
 ├──── Category (N)
 ├──── Product (N)
 │      └── StockLevel (N per location)
 │      └── Batch (N per location — track_batch=true)
 │      └── StockMovement (N)  kind: sale|purchase|adjustment|transfer|return
 ├──── Customer (N)
 ├──── Sale (N)
 │      └── SaleLine (embedded)
 ├──── Supplier (N)
 ├──── PurchaseOrder (N)
 │      └── POLine (embedded, has received_qty)
 ├──── Expense (N)
 ├──── Notification (N)
 └──── RazorpayOrder (N)
```

All IDs are UUID strings. No ObjectId references between collections — documents reference each other by `id` field.

---

## Multi-Tenancy

Tenants share a single MongoDB database and collections. Isolation is enforced **at the application layer**:

- Every `BaseDoc` subclass includes `tenant_id: str`
- Every route uses `ctx.tenant_id` from `get_current()` as the first query filter
- The NLQ AI pipeline **always** injects `{ "$match": { "tenant_id": "<id>" } }` as the first stage before executing user-generated aggregations
- Demo seed creates a single `demo` tenant — new signups create their own isolated tenant

---

## Authentication Flow

### Email/Password
```
POST /api/auth/signup
  → Create Tenant record
  → Hash password (bcrypt)
  → Create User with role=owner
  → Issue JWT { user_id, tenant_id, role }
  → Return token

POST /api/auth/login
  → Look up User by email
  → Verify bcrypt hash
  → Issue JWT
  → Return token
```

### Google OAuth
```
Frontend → Google OAuth popup (Emergent Agent OAuth)
  → Receive #session_id=<hash> in URL fragment
  → AuthCallback.jsx sends session_id to POST /api/auth/google/session
  → Backend exchanges session_id with Emergent session endpoint → { email, name }
  → Find or create User + Tenant
  → Issue JWT
  → Return token
```

JWT is stored in `localStorage`. The Axios instance attaches `Authorization: Bearer <token>` to every request. On 401, the auth context clears the token and redirects to `/login`.

---

## AI / NLQ Architecture

```
User types question
    │
    ▼
POST /api/ai/nlq  { question: "..." }
    │
    ├─► System prompt: MongoDB schema + tenant_id substituted
    │
    ├─► GPT-4o-mini completion (max_tokens: 1000)
    │       Returns: { collection, pipeline, chart, explanation }
    │
    ├─► _sanitize_pipeline()
    │       - Strip $out / $merge stages
    │       - Prepend { $match: { tenant_id } } unconditionally
    │       - Append { $limit: 200 }
    │
    ├─► Collection allowlist check
    │
    ├─► db[collection].aggregate(pipeline)
    │
    └─► Return { rows, chart, explanation, pipeline }
            │
            ▼
     Frontend renders:
       - Table (default)
       - BarChart / LineChart / PieChart  (Recharts)
       - Explanation text
```

---

## External Service Integrations

| Service | Purpose | Integration Point |
|---|---|---|
| OpenAI API | NLQ query generation, business insights narrative | `routes_ai.py` — async via `openai` SDK |
| Razorpay | Payment order creation + signature verification + webhooks | `routes_payments.py` |
| Twilio | SMS + WhatsApp notifications (invoices, low-stock alerts, daily P&L) | `routes_notifications.py` |
| ElevenLabs | Text-to-speech (AI insights read-aloud, multilingual) | `routes_tts.py` — `asyncio.to_thread` to avoid blocking |
| Cloudinary | Product image hosting via signed browser-direct uploads | `routes_uploads.py` — backend only signs, no file bytes traverse Python |

---

## Security Notes

- All secrets in `.env` — never committed
- CORS restricted to `CORS_ORIGINS` env var (defaults to `*` in dev)
- NLQ pipeline sanitized before execution (no writes, tenant-scoped)
- Cloudinary uploads signed server-side (expiring signature, never expose secret to browser)
- Razorpay webhooks verified with HMAC-SHA256
- bcrypt cost factor applies to all stored passwords
- JWT `exp` claim enforced on every protected endpoint

---

## Deployment Topology (Recommended)

```
                        ┌──────────────────┐
                        │   Cloudflare /   │
                        │   CDN / CDN Edge │
                        └────────┬─────────┘
                                 │
              ┌──────────────────┴──────────────────┐
              │                                      │
   ┌──────────▼──────────┐             ┌─────────────▼──────────┐
   │   Static Hosting    │             │    App Server           │
   │  (Vercel / Netlify) │             │  (Fly.io / Render /     │
   │                     │             │   Railway / EC2)        │
   │   React Build       │             │                         │
   │   (npm run build)   │             │   uvicorn server:app    │
   └─────────────────────┘             │   --host 0.0.0.0        │
                                       │   --port 8001           │
                                       └─────────────┬───────────┘
                                                     │
                                       ┌─────────────▼───────────┐
                                       │     MongoDB Atlas        │
                                       │   (M10 or higher)       │
                                       └─────────────────────────┘
```
