"""Auth + tenant signup routes."""
import httpx
from fastapi import APIRouter, HTTPException, Depends, Header, Request
from typing import Optional
from pydantic import BaseModel, EmailStr
from db import db, strip_mongo_id
from auth import hash_password, verify_password, make_token, get_current, AuthContext, require_roles
from models import Tenant, User, SignupIn, LoginIn, InviteIn, Location
from email_utils import send_email, invite_email_html

router = APIRouter(prefix="/auth", tags=["auth"])

EMERGENT_SESSION_URL = "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"


@router.post("/signup")
async def signup(inp: SignupIn):
    existing = await db.users.find_one({"email": inp.email.lower()})
    if existing:
        raise HTTPException(400, "Email already registered")

    tenant = Tenant(name=inp.business_name, business_type=inp.business_type)
    await db.tenants.insert_one(tenant.model_dump())

    # default location
    loc = Location(tenant_id=tenant.id, name="Main Store")
    await db.locations.insert_one(loc.model_dump())

    user = User(
        tenant_id=tenant.id,
        email=inp.email.lower(),
        name=inp.name,
        role="owner",
        password_hash=hash_password(inp.password),
    )
    await db.users.insert_one(user.model_dump())

    token = make_token(user.id, tenant.id, user.role)
    return {
        "token": token,
        "user": {"id": user.id, "email": user.email, "name": user.name, "role": user.role},
        "tenant": {"id": tenant.id, "name": tenant.name, "business_type": tenant.business_type, "currency": tenant.currency},
    }


@router.post("/login")
async def login(inp: LoginIn):
    doc = await db.users.find_one({"email": inp.email.lower()})
    if not doc or not verify_password(inp.password, doc["password_hash"]):
        raise HTTPException(401, "Invalid credentials")
    if not doc.get("active", True):
        raise HTTPException(403, "Account disabled")
    tenant = strip_mongo_id(await db.tenants.find_one({"id": doc["tenant_id"]}))
    token = make_token(doc["id"], doc["tenant_id"], doc["role"])
    return {
        "token": token,
        "user": {"id": doc["id"], "email": doc["email"], "name": doc["name"], "role": doc["role"]},
        "tenant": tenant,
    }


@router.get("/me")
async def me(ctx: AuthContext = Depends(get_current)):
    user = strip_mongo_id(await db.users.find_one({"id": ctx.user_id}))
    tenant = strip_mongo_id(await db.tenants.find_one({"id": ctx.tenant_id}))
    if user:
        user.pop("password_hash", None)
    return {"user": user, "tenant": tenant}


@router.get("/users")
async def list_users(ctx: AuthContext = Depends(require_roles("owner", "manager"))):
    users = await db.users.find({"tenant_id": ctx.tenant_id}, {"_id": 0, "password_hash": 0}).to_list(500)
    return users


@router.post("/google/session")
async def google_session(x_session_id: Optional[str] = Header(None, alias="X-Session-ID")):
    """Exchange Emergent Google session_id for our own JWT.
    - Existing email → log into their tenant.
    - New email → auto-create tenant, user becomes Owner.
    """
    if not x_session_id:
        raise HTTPException(400, "Missing X-Session-ID header")

    try:
        async with httpx.AsyncClient(timeout=10) as http:
            r = await http.get(EMERGENT_SESSION_URL, headers={"X-Session-ID": x_session_id})
        if r.status_code != 200:
            raise HTTPException(401, "Invalid Google session")
        data = r.json()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Auth service unavailable: {e}")

    email = (data.get("email") or "").lower()
    name = data.get("name") or email.split("@")[0]
    if not email:
        raise HTTPException(400, "No email returned from Google")

    existing = await db.users.find_one({"email": email})
    if existing:
        if not existing.get("active", True):
            raise HTTPException(403, "Account disabled")
        user = existing
    else:
        # Auto-create tenant + user (Option C - new email gets own workspace as Owner)
        tenant = Tenant(name=f"{name}'s Workspace", business_type="retail")
        await db.tenants.insert_one(tenant.model_dump())
        await db.locations.insert_one(Location(tenant_id=tenant.id, name="Main Store").model_dump())
        new_user = User(
            tenant_id=tenant.id,
            email=email,
            name=name,
            role="owner",
            password_hash="",  # Google-only account
        )
        await db.users.insert_one(new_user.model_dump())
        user = new_user.model_dump()

    tenant = strip_mongo_id(await db.tenants.find_one({"id": user["tenant_id"]}))
    token = make_token(user["id"], user["tenant_id"], user["role"])
    return {
        "token": token,
        "user": {"id": user["id"], "email": user["email"], "name": user["name"], "role": user["role"]},
        "tenant": tenant,
    }


@router.post("/invite")
async def invite(inp: InviteIn, request: Request, ctx: AuthContext = Depends(require_roles("owner", "manager"))):
    if await db.users.find_one({"email": inp.email.lower()}):
        raise HTTPException(400, "Email already exists")
    user = User(
        tenant_id=ctx.tenant_id,
        email=inp.email.lower(),
        name=inp.name,
        role=inp.role,
        password_hash=hash_password(inp.password),
    )
    await db.users.insert_one(user.model_dump())

    # Send invite email (non-blocking — failure doesn't break the invite)
    tenant = await db.tenants.find_one({"id": ctx.tenant_id})
    tenant_name = tenant["name"] if tenant else "Smart Ledger"
    login_url = str(request.base_url).rstrip("/").replace("http://", "https://")
    # Use frontend origin if available via Referer/Origin header
    origin = request.headers.get("origin") or request.headers.get("referer", "").rstrip("/")
    if origin:
        login_url = origin.rstrip("/") + "/login"
    else:
        login_url = login_url + "/login"

    html, plain = invite_email_html(
        name=inp.name,
        email=inp.email.lower(),
        password=inp.password,
        role=inp.role,
        tenant_name=tenant_name,
        login_url=login_url,
    )
    email_sent = await send_email(
        to=inp.email.lower(),
        subject=f"You've been invited to {tenant_name} on Smart Ledger",
        html=html,
        text=plain,
    )

    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "email_sent": email_sent,
    }


class TestEmailIn(BaseModel):
    to: EmailStr


@router.post("/test-email")
async def test_email(inp: TestEmailIn, ctx: AuthContext = Depends(require_roles("owner"))):
    """Send a test email to verify SMTP config. Owner-only."""
    import os
    smtp_host = os.environ.get("SMTP_HOST", "")
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASS", "")
    smtp_port = os.environ.get("SMTP_PORT", "587")

    html = f"""
<!DOCTYPE html>
<html>
<body style="font-family:Inter,sans-serif;background:#09090B;color:#FAFAFA;margin:0;padding:0;">
  <div style="max-width:480px;margin:40px auto;background:#18181B;border:1px solid #27272A;border-radius:12px;overflow:hidden;">
    <div style="background:#2563EB;padding:24px 32px;">
      <div style="font-size:22px;font-weight:700;letter-spacing:-0.5px;">Smart Ledger</div>
      <div style="font-size:13px;opacity:0.8;margin-top:4px;">Email configuration test</div>
    </div>
    <div style="padding:32px;">
      <p style="margin:0 0 16px;font-size:15px;">✅ <strong>SMTP is working correctly.</strong></p>
      <p style="margin:0 0 24px;font-size:14px;color:#A1A1AA;">
        Your Smart Ledger workspace email is configured and sending successfully.
        Invite emails will be delivered to new team members.
      </p>
      <div style="background:#09090B;border:1px solid #27272A;border-radius:8px;padding:20px;margin-bottom:24px;">
        <div style="margin-bottom:10px;">
          <div style="font-size:10px;text-transform:uppercase;letter-spacing:0.1em;color:#71717A;margin-bottom:4px;">SMTP Host</div>
          <div style="font-family:monospace;font-size:13px;color:#FAFAFA;">{smtp_host}:{smtp_port}</div>
        </div>
        <div>
          <div style="font-size:10px;text-transform:uppercase;letter-spacing:0.1em;color:#71717A;margin-bottom:4px;">Sending From</div>
          <div style="font-family:monospace;font-size:13px;color:#FAFAFA;">{smtp_user}</div>
        </div>
      </div>
      <p style="margin:0;font-size:12px;color:#52525B;">This is an automated test from Smart Ledger.</p>
    </div>
  </div>
</body>
</html>
"""
    plain = (
        "SMTP Test — Smart Ledger\n\n"
        "Your email configuration is working correctly.\n"
        f"SMTP Host: {smtp_host}:{smtp_port}\n"
        f"Sending from: {smtp_user}\n"
    )

    sent = await send_email(
        to=inp.to,
        subject="✅ Smart Ledger — Email test successful",
        html=html,
        text=plain,
    )

    if not sent:
        raise HTTPException(
            500,
            detail=f"Email failed. Check SMTP config: host={smtp_host}, user={smtp_user}, pass={'set' if smtp_pass else 'MISSING'}",
        )

    return {"success": True, "message": f"Test email sent to {inp.to}"}
