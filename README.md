# 🧾 Smart Ledger

> AI-powered multi-tenant ERP for Indian retail businesses — built for hackathons, production-ready in architecture.

Smart Ledger is a full-stack business management platform covering POS sales, inventory, procurement, finance tracking, and AI-driven insights. Built with a dark-mode-first UI, it targets SMBs in India with GST compliance, multi-location support, and natural language querying baked in.

---

## ✨ Features at a Glance

| Module | What it does |
|---|---|
| **Dashboard** | Live KPIs — today's revenue, order count, stock value, low-stock alerts, 30-day trend, top products |
| **Point of Sale** | Barcode-ready checkout, GST calculation, split payments (cash / card / UPI), customer selection, refunds |
| **Inventory** | Multi-location stock, batch/expiry tracking, stock adjustments, movement history, low-stock alerts |
| **Procurement** | Supplier management, Purchase Orders, Goods Receipt Notes, weighted average cost accounting |
| **Finance** | Expense tracking, P&L report (Revenue → COGS → Gross Profit → Net Profit) |
| **AI Insights** | Natural language queries → live charts, 30-day demand forecasting, LLM-generated business narratives |
| **Notifications** | SMS & WhatsApp via Twilio — low-stock digest, daily P&L summary, invoice delivery |
| **Payments** | Razorpay order creation, HMAC signature verification, webhook handling |
| **TTS** | ElevenLabs text-to-speech for AI insights read-aloud |
| **Uploads** | Cloudinary signed browser-direct image uploads |
| **Settings** | User management, role-based access, team invites |

---

## 🏗️ Tech Stack

### Backend
| Layer | Technology |
|---|---|
| Framework | FastAPI 0.110 + Uvicorn |
| Database | MongoDB via Motor 3.3 (async) |
| Auth | JWT (PyJWT / python-jose) + bcrypt/passlib |
| Validation | Pydantic v2 |
| AI/LLM | OpenAI API (gpt-4o-mini) |
| Payments | Razorpay 2.0 |
| Messaging | Twilio 9.10 (SMS + WhatsApp) |
| TTS | ElevenLabs 2.58 |
| Storage | Cloudinary 1.45 |

### Frontend
| Layer | Technology |
|---|---|
| Framework | React 19 (CRA + CRACO) |
| Routing | React Router v7 |
| Styling | Tailwind CSS v3 + shadcn/ui (Radix UI) |
| Data fetching | TanStack Query v5 + Axios |
| Charts | Recharts |
| Animations | Framer Motion |
| Forms | React Hook Form + Zod |
| Notifications | Sonner toasts |

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+ / Yarn 1.22
- MongoDB 6+ (local or Atlas)

### 1. Clone the repo
```bash
git clone <repo-url>
cd smart
```

### 2. Backend setup
```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

Copy and fill in the environment variables:
```bash
cp .env.example .env   # if it exists, otherwise edit .env directly
```

Required `.env` keys:
```env
MONGO_URL=mongodb://localhost:27017
DB_NAME=smart_ledger
JWT_SECRET=your-secret-key-here
EMERGENT_LLM_KEY=your-openai-key
LLM_MODEL=gpt-4o-mini
LLM_BASE_URL=                          # leave blank for OpenAI default

# Optional integrations
RAZORPAY_KEY_ID=
RAZORPAY_KEY_SECRET=
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_FROM_NUMBER=
ELEVENLABS_API_KEY=
CLOUDINARY_CLOUD_NAME=
CLOUDINARY_API_KEY=
CLOUDINARY_API_SECRET=
CORS_ORIGINS=http://localhost:3000
```

Start the backend:
```bash
uvicorn server:app --reload --port 8001
```

On first startup the server auto-seeds demo data (tenant, products, sales).

### 3. Frontend setup
```bash
cd frontend
yarn install
```

Set the API URL in `.env.local`:
```env
REACT_APP_BACKEND_URL=http://localhost:8001
```

Start the frontend:
```bash
yarn start
```

Open [http://localhost:3000](http://localhost:3000) — log in with the demo credentials printed in the backend console.

---

## 🗂️ Project Structure

```
smart/
├── backend/
│   ├── server.py            # FastAPI app, CORS, lifespan/index setup
│   ├── db.py                # Motor client + db reference
│   ├── auth.py              # JWT issue/verify, RBAC dependency
│   ├── models.py            # Pydantic models for all entities
│   ├── seed.py              # Demo data seeder
│   ├── routes_auth.py       # /api/auth/*
│   ├── routes_inventory.py  # /api/inventory/*
│   ├── routes_pos.py        # /api/pos/*  (sales, customers)
│   ├── routes_procurement.py# /api/procurement/*
│   ├── routes_finance.py    # /api/finance/*
│   ├── routes_dashboard.py  # /api/dashboard/summary
│   ├── routes_ai.py         # /api/ai/* (NLQ, forecast, insights)
│   ├── routes_payments.py   # /api/payments/razorpay/*
│   ├── routes_notifications.py # /api/notify/*
│   ├── routes_tts.py        # /api/tts/*
│   ├── routes_uploads.py    # /api/uploads/*
│   └── requirements.txt
│
└── frontend/
    └── src/
        ├── App.js           # Routes + auth guards
        ├── pages/
        │   ├── Dashboard.jsx
        │   ├── Inventory.jsx
        │   ├── POS.jsx
        │   ├── Sales.jsx
        │   ├── Procurement.jsx
        │   ├── Finance.jsx
        │   ├── AIInsights.jsx
        │   ├── Notifications.jsx
        │   └── Settings.jsx
        ├── components/
        │   ├── Layout.jsx   # Sidebar + nav shell
        │   ├── NLQDialog.jsx# Natural language query modal
        │   └── ui/          # shadcn/ui primitives
        └── lib/
            ├── auth.jsx     # AuthContext + JWT helpers
            └── api.js       # Axios instance
```

---

## 🔐 Authentication & Multi-tenancy

- Dual auth: **email/password** (bcrypt hashed) and **Google OAuth** (via session exchange)
- JWT encodes `user_id`, `tenant_id`, and `role` — no extra DB lookup per request
- Five roles: `owner`, `manager`, `cashier`, `warehouse`, `accountant`
- Every MongoDB document carries a `tenant_id` — all queries are tenant-scoped by default

---

## 🤖 AI Features

### Natural Language Query (NLQ)
Ask questions in plain English — "What were my top 5 products last week?" — and the system:
1. Sends your question + MongoDB schema to GPT-4o-mini
2. Receives a MongoDB aggregation pipeline
3. Sanitizes it (strips write stages, enforces `tenant_id`)
4. Executes it and returns results with a chart type hint (bar / line / pie / table)

### Demand Forecasting
Pulls 60 days of sales history, computes per-SKU average daily velocity, projects 30-day demand, and calculates recommended reorder quantities factoring in lead time.

### Business Insights
Feeds recent sales KPIs to GPT-4o-mini and returns 3–4 actionable bullet points, optionally read aloud via ElevenLabs TTS.

---

## 📡 API Reference

All endpoints are prefixed with `/api`. Interactive docs available at `http://localhost:8001/docs`.

| Prefix | Description |
|---|---|
| `/api/auth` | Signup, login, user management, Google OAuth |
| `/api/inventory` | Products, stock levels, movements, alerts |
| `/api/pos` | Sales (checkout), customers, refunds |
| `/api/procurement` | Suppliers, Purchase Orders, GRNs |
| `/api/finance` | Expenses, P&L report |
| `/api/dashboard` | Summary KPIs + trends |
| `/api/ai` | NLQ, demand forecast, insights narrative |
| `/api/payments/razorpay` | Order creation, payment verification, webhooks |
| `/api/notify` | SMS, WhatsApp, low-stock digest, invoice delivery |
| `/api/tts` | Text-to-speech (ElevenLabs) |
| `/api/uploads` | Cloudinary signed upload params |

---

## 🧪 Running Tests

```bash
cd backend
pytest
```

---

## 📝 License

MIT
