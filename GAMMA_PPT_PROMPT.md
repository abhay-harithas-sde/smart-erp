# Gamma.app Presentation Prompt

Paste the prompt below into [gamma.app](https://gamma.app) → "Generate with AI" to produce a polished pitch/demo deck for Smart Ledger.

---

## PROMPT (copy everything between the lines)

---

Create a 12-slide professional presentation titled **"Smart Ledger — AI-Powered ERP for Modern Retail"**.

Use a dark, minimal design theme with zinc/slate tones and green accent highlights. Each slide should include an icon or illustration suggestion in brackets.

---

### Slide 1 — Title
**Smart Ledger**
*AI-Powered Multi-Tenant ERP for Indian Retail*
Tagline: "Run your store. Ask questions. Get answers."
[Hero image: a sleek dark dashboard with charts and a chat interface]

---

### Slide 2 — The Problem
**Running a retail business in India is still manual work.**
- Inventory managed in Excel or paper ledgers
- No real-time visibility across multiple store locations
- GST calculations done manually — error-prone
- Business owners get insights only at month-end
- Disconnected tools for POS, stock, procurement, and payments
[Icon: fragmented puzzle pieces, cluttered desk]

---

### Slide 3 — The Solution
**Smart Ledger brings everything under one roof.**
- Unified platform: POS + Inventory + Procurement + Finance + AI
- Multi-location, multi-user with role-based access
- GST-compliant invoicing built in
- AI answers your business questions in plain English
- Real-time alerts, WhatsApp notifications, and demand forecasting
[Icon: a clean connected hub / single dashboard]

---

### Slide 4 — Key Features (6-block grid layout)
1. 🧾 **Smart POS** — Barcode checkout, split payments (cash/card/UPI), instant GST invoices
2. 📦 **Inventory** — Multi-location stock, batch & expiry tracking, low-stock alerts
3. 🚚 **Procurement** — Supplier POs, Goods Receipt Notes, weighted average cost
4. 💰 **Finance** — Expense tracking, live P&L (Revenue → COGS → Net Profit)
5. 🤖 **AI Insights** — Natural language queries, demand forecasting, business narratives
6. 📲 **Notifications** — WhatsApp invoices, SMS alerts, daily P&L summaries via Twilio
[Layout: 2×3 feature card grid]

---

### Slide 5 — AI Natural Language Query
**Ask your data anything. In plain English.**
- User types: *"What were my top 5 products last week?"*
- Smart Ledger sends the question to GPT-4o-mini with your MongoDB schema
- The AI returns a query pipeline — executed securely on your data
- Results visualized as a bar chart, line chart, pie chart, or table — instantly
- Every query is tenant-scoped. Your data never leaks.
[Illustration: chat input → AI → chart output flow diagram]

---

### Slide 6 — Demand Forecasting
**Know what to reorder before you run out.**
- Analyzes 60 days of sales history per SKU
- Computes average daily velocity and 30-day demand projection
- Factors in supplier lead time to calculate reorder quantity
- Automatically flags products below reorder level
- Eliminates stockouts and overstock situations
[Icon: upward trend line + warehouse shelf]

---

### Slide 7 — Architecture Overview
**Modern, async, multi-tenant.**
Three-tier architecture:
- **Frontend**: React 19 + Tailwind CSS + shadcn/ui (dark-mode-first SPA)
- **Backend**: FastAPI + Uvicorn (fully async Python)
- **Database**: MongoDB with Motor async driver

Multi-tenancy via `tenant_id` field isolation — not separate databases.
JWT authentication with role-based access control (owner / manager / cashier / warehouse / accountant).
[Diagram: Browser → FastAPI → MongoDB with service integrations on the side]

---

### Slide 8 — Tech Stack
**Built with production-grade tools.**

| Layer | Technology |
|---|---|
| Frontend | React 19, React Router v7, TanStack Query, Recharts |
| Styling | Tailwind CSS, shadcn/ui, Radix UI, Framer Motion |
| Backend | FastAPI, Uvicorn, Pydantic v2 |
| Database | MongoDB, Motor (async) |
| AI | OpenAI GPT-4o-mini |
| Payments | Razorpay |
| Messaging | Twilio (SMS + WhatsApp) |
| TTS | ElevenLabs (multilingual) |
| Storage | Cloudinary (signed direct uploads) |

[Icons: logos of the technologies listed]

---

### Slide 9 — Multi-Tenancy & Security
**One platform. Complete isolation.**
- Every database document carries a `tenant_id` — all queries are tenant-scoped
- AI queries are sanitized before execution: no write operations, no cross-tenant leaks
- Passwords hashed with bcrypt, secrets in environment variables
- Razorpay webhooks verified with HMAC-SHA256
- Cloudinary uploads: backend signs, browser uploads directly — files never touch the app server
- Role-based guards on every sensitive endpoint
[Icon: shield / lock with multi-user silhouettes]

---

### Slide 10 — Live Demo Flow
**From signup to first insight in under 3 minutes.**
1. Sign up with business name → tenant created automatically
2. Demo data seeded on first startup (products, sales, stock)
3. View dashboard KPIs and 30-day revenue trend
4. Checkout a sale on the POS — stock auto-deducted
5. Ask the AI: *"Show me revenue by payment mode this month"*
6. View demand forecast and reorder recommendations
[Flow arrows connecting each step as a visual journey]

---

### Slide 11 — Business Impact
**Why it matters for Indian retail.**
- 63 million MSMEs in India — majority still using paper/Excel
- GST compliance built-in reduces accounting errors
- WhatsApp-first notifications meet business owners where they already are
- AI insights previously available only to large enterprises — now for every kirana store
- Multi-location support enables franchise / chain operations from day one
[Icon: India map + shop illustration + growth chart]

---

### Slide 12 — Closing
**Smart Ledger — Because every business deserves enterprise-grade tools.**

Built at [Hackathon Name]
Stack: FastAPI · React · MongoDB · OpenAI · Razorpay · Twilio · ElevenLabs

[GitHub / Demo link / QR code placeholder]

[Hero: team photo or product screenshot montage]

---

*Presentation style notes for Gamma:*
- Use **dark zinc (#09090B background)** with **white text**
- Accent color: **emerald green (#10B981)**
- Font: Inter or Geist (sans-serif, modern)
- Slide transitions: subtle fade
- Data slides: use Gamma's built-in table and chart components where applicable
