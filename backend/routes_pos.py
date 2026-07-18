"""POS / Sales / Customers / Invoices."""
import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from db import db, scope
from auth import get_current, AuthContext, require_roles
from models import Sale, SaleIn, Customer, gen_id, now_iso
from routes_inventory import _apply_movement
from email_utils import send_email, bill_email_html

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pos", tags=["pos"])


@router.get("/customers")
async def list_customers(q: Optional[str] = None, ctx: AuthContext = Depends(get_current)):
    query = scope(ctx.tenant_id)
    if q:
        query["$or"] = [{"name": {"$regex": q, "$options": "i"}}, {"phone": {"$regex": q, "$options": "i"}}]
    return await db.customers.find(query, {"_id": 0}).to_list(500)


@router.post("/customers")
async def create_customer(body: dict, ctx: AuthContext = Depends(get_current)):
    c = Customer(tenant_id=ctx.tenant_id, name=body["name"], phone=body.get("phone", ""), email=body.get("email", ""))
    await db.customers.insert_one(c.model_dump())
    return c.model_dump()


@router.post("/sales")
async def checkout(inp: SaleIn, ctx: AuthContext = Depends(require_roles("owner", "manager", "cashier"))):
    if not inp.lines:
        raise HTTPException(400, "Empty cart")

    # Compute totals + validate stock
    subtotal = 0.0
    tax = 0.0
    computed_lines = []
    for l in inp.lines:
        product = await db.products.find_one({"tenant_id": ctx.tenant_id, "id": l.product_id})
        if not product:
            raise HTTPException(400, f"Product {l.product_id} not found")
        line_sub = l.qty * l.price
        line_tax = line_sub * (l.tax_rate or product.get("tax_rate", 0)) / 100
        subtotal += line_sub
        tax += line_tax
        computed_lines.append({**l.model_dump(), "line_total": line_sub + line_tax})

    total = subtotal + tax
    seq = await db.sales.count_documents({"tenant_id": ctx.tenant_id}) + 1
    invoice_no = f"INV-{seq:06d}"

    sale = Sale(
        tenant_id=ctx.tenant_id,
        invoice_no=invoice_no,
        location_id=inp.location_id,
        customer_id=inp.customer_id,
        customer_name=inp.customer_name,
        lines=computed_lines,
        subtotal=round(subtotal, 2),
        tax=round(tax, 2),
        total=round(total, 2),
        payment_mode=inp.payment_mode,
        payments=inp.payments,
        status="paid",
        cashier_id=ctx.user_id,
    )
    await db.sales.insert_one(sale.model_dump())

    # Deduct stock
    for l in computed_lines:
        await _apply_movement(ctx.tenant_id, l["product_id"], inp.location_id, -abs(float(l["qty"])), "sale", sale.id, f"Sale {invoice_no}")

    # Send bill to customer email (non-blocking — never fails the sale)
    asyncio.create_task(_send_bill_email(ctx.tenant_id, sale.model_dump()))

    return sale.model_dump()


@router.get("/sales")
async def list_sales(limit: int = 100, ctx: AuthContext = Depends(get_current)):
    return await db.sales.find(scope(ctx.tenant_id), {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)


@router.get("/sales/{sid}")
async def get_sale(sid: str, ctx: AuthContext = Depends(get_current)):
    s = await db.sales.find_one({"tenant_id": ctx.tenant_id, "id": sid}, {"_id": 0})
    if not s:
        raise HTTPException(404, "Not found")
    return s


@router.post("/sales/{sid}/refund")
async def refund_sale(sid: str, ctx: AuthContext = Depends(require_roles("owner", "manager"))):
    s = await db.sales.find_one({"tenant_id": ctx.tenant_id, "id": sid})
    if not s:
        raise HTTPException(404, "Not found")
    if s.get("status") == "refunded":
        raise HTTPException(400, "Already refunded")
    for l in s["lines"]:
        await _apply_movement(ctx.tenant_id, l["product_id"], s["location_id"], abs(float(l["qty"])), "return", sid, f"Refund {s['invoice_no']}")
    await db.sales.update_one({"tenant_id": ctx.tenant_id, "id": sid}, {"$set": {"status": "refunded"}})
    return {"ok": True}


# ---------- Bill email helpers ----------

async def _send_bill_email(tenant_id: str, sale: dict) -> None:
    """Look up customer email and send the bill. Swallows all exceptions."""
    try:
        # Resolve customer email
        customer_email = ""
        customer_id = sale.get("customer_id", "")
        if customer_id:
            customer = await db.customers.find_one({"tenant_id": tenant_id, "id": customer_id})
            if customer:
                customer_email = customer.get("email", "")

        if not customer_email:
            logger.info("No customer email for sale %s — skipping bill email", sale.get("invoice_no"))
            return

        # Fetch tenant name for the email header
        tenant = await db.tenants.find_one({"id": tenant_id})
        tenant_name = tenant.get("name", "Smart Ledger") if tenant else "Smart Ledger"
        currency_sym = "₹" if tenant and tenant.get("currency", "INR") == "INR" else (tenant.get("currency", "₹") if tenant else "₹")

        html, plain = bill_email_html(sale, tenant_name, currency_sym)
        subject = f"Your Bill — {sale.get('invoice_no', '')} | {tenant_name}"
        await send_email(customer_email, subject, html, plain)
    except Exception as e:
        logger.error("Failed to send bill email for sale %s: %s", sale.get("id"), e)


@router.post("/sales/{sid}/send-email")
async def resend_bill_email(sid: str, ctx: AuthContext = Depends(require_roles("owner", "manager", "cashier"))):
    """Manually re-send the bill email for a sale to the customer's email address."""
    s = await db.sales.find_one({"tenant_id": ctx.tenant_id, "id": sid}, {"_id": 0})
    if not s:
        raise HTTPException(404, "Sale not found")

    customer_id = s.get("customer_id", "")
    customer_email = ""
    if customer_id:
        customer = await db.customers.find_one({"tenant_id": ctx.tenant_id, "id": customer_id})
        if customer:
            customer_email = customer.get("email", "")

    if not customer_email:
        raise HTTPException(400, "No email address on file for this customer")

    tenant = await db.tenants.find_one({"id": ctx.tenant_id})
    tenant_name = tenant.get("name", "Smart Ledger") if tenant else "Smart Ledger"
    currency_sym = "₹" if tenant and tenant.get("currency", "INR") == "INR" else (tenant.get("currency", "₹") if tenant else "₹")

    html, plain = bill_email_html(s, tenant_name, currency_sym)
    subject = f"Your Bill — {s.get('invoice_no', '')} | {tenant_name}"
    sent = await send_email(customer_email, subject, html, plain)
    if not sent:
        raise HTTPException(500, "Failed to send email — check SMTP configuration")
    return {"ok": True, "sent_to": customer_email}
