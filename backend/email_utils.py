"""Async email sending via SMTP (Gmail App Password supported)."""
import os
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import aiosmtplib

logger = logging.getLogger(__name__)


async def send_email(to: str, subject: str, html: str, text: str = "") -> bool:
    """Send an email. Returns True on success, False on failure (non-blocking)."""
    # Read env vars at call time so Render env vars are always fresh
    smtp_host = os.environ.get("SMTP_HOST", "")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASS", "")
    smtp_from = os.environ.get("SMTP_FROM", smtp_user)

    if not all([smtp_host, smtp_user, smtp_pass]):
        logger.warning("SMTP not configured — skipping email to %s", to)
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = smtp_from
        msg["To"] = to
        if text:
            msg.attach(MIMEText(text, "plain"))
        msg.attach(MIMEText(html, "html"))
        await aiosmtplib.send(
            msg,
            hostname=smtp_host,
            port=smtp_port,
            username=smtp_user,
            password=smtp_pass,
            start_tls=True,
        )
        logger.info("Email sent to %s — %s", to, subject)
        return True
    except Exception as e:
        logger.error("Email failed to %s: %s", to, e)
        return False


def bill_email_html(sale: dict, tenant_name: str, currency: str = "₹") -> tuple[str, str]:
    """Returns (html, plain_text) for a bill/invoice email sent to a customer."""
    invoice_no = sale.get("invoice_no", "N/A")
    customer_name = sale.get("customer_name") or "Valued Customer"
    lines = sale.get("lines", [])
    subtotal = sale.get("subtotal", 0)
    tax = sale.get("tax", 0)
    total = sale.get("total", 0)
    payment_mode = sale.get("payment_mode", "cash").upper()
    created_at = sale.get("created_at", "")
    # Format date nicely if possible
    try:
        from datetime import datetime
        dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        date_str = dt.strftime("%d %b %Y, %I:%M %p")
    except Exception:
        date_str = created_at[:10] if created_at else "N/A"

    # Build line items rows
    rows_html = ""
    rows_plain = ""
    for line in lines:
        name_cell = line.get("name", "")
        sku = line.get("sku", "")
        qty = line.get("qty", 0)
        price = line.get("price", 0)
        lt = line.get("line_total", qty * price)
        rows_html += f"""
        <tr>
          <td style="padding:10px 12px;border-bottom:1px solid #27272A;">{name_cell}<br><span style="font-size:11px;color:#71717A;">SKU: {sku}</span></td>
          <td style="padding:10px 12px;border-bottom:1px solid #27272A;text-align:center;">{qty}</td>
          <td style="padding:10px 12px;border-bottom:1px solid #27272A;text-align:right;">{currency}{price:,.2f}</td>
          <td style="padding:10px 12px;border-bottom:1px solid #27272A;text-align:right;">{currency}{lt:,.2f}</td>
        </tr>"""
        rows_plain += f"  {name_cell} (x{qty}) @ {currency}{price:,.2f} = {currency}{lt:,.2f}\n"

    html = f"""<!DOCTYPE html>
<html>
<body style="font-family:Inter,sans-serif;background:#09090B;color:#FAFAFA;margin:0;padding:0;">
  <div style="max-width:560px;margin:40px auto;background:#18181B;border:1px solid #27272A;border-radius:12px;overflow:hidden;">
    <div style="background:#2563EB;padding:24px 32px;display:flex;justify-content:space-between;align-items:center;">
      <div>
        <div style="font-size:22px;font-weight:700;letter-spacing:-0.5px;">{tenant_name}</div>
        <div style="font-size:13px;opacity:0.8;margin-top:4px;">Invoice / Bill Receipt</div>
      </div>
      <div style="text-align:right;">
        <div style="font-size:16px;font-weight:700;">{invoice_no}</div>
        <div style="font-size:12px;opacity:0.8;">{date_str}</div>
      </div>
    </div>
    <div style="padding:28px 32px;">
      <p style="margin:0 0 20px;font-size:15px;">Dear <strong>{customer_name}</strong>,</p>
      <p style="margin:0 0 24px;font-size:14px;color:#A1A1AA;">
        Thank you for your purchase at <strong style="color:#FAFAFA;">{tenant_name}</strong>. Please find your bill details below.
      </p>
      <!-- Line items table -->
      <table style="width:100%;border-collapse:collapse;font-size:13px;margin-bottom:20px;">
        <thead>
          <tr style="background:#09090B;">
            <th style="padding:10px 12px;text-align:left;color:#71717A;font-weight:600;border-bottom:1px solid #27272A;">Item</th>
            <th style="padding:10px 12px;text-align:center;color:#71717A;font-weight:600;border-bottom:1px solid #27272A;">Qty</th>
            <th style="padding:10px 12px;text-align:right;color:#71717A;font-weight:600;border-bottom:1px solid #27272A;">Unit Price</th>
            <th style="padding:10px 12px;text-align:right;color:#71717A;font-weight:600;border-bottom:1px solid #27272A;">Total</th>
          </tr>
        </thead>
        <tbody>{rows_html}
        </tbody>
      </table>
      <!-- Totals -->
      <div style="border-top:1px solid #27272A;padding-top:16px;">
        <div style="display:flex;justify-content:space-between;font-size:13px;color:#A1A1AA;margin-bottom:8px;">
          <span>Subtotal</span><span>{currency}{subtotal:,.2f}</span>
        </div>
        <div style="display:flex;justify-content:space-between;font-size:13px;color:#A1A1AA;margin-bottom:12px;">
          <span>Tax</span><span>{currency}{tax:,.2f}</span>
        </div>
        <div style="display:flex;justify-content:space-between;font-size:16px;font-weight:700;color:#FAFAFA;border-top:1px solid #3F3F46;padding-top:12px;">
          <span>Total Paid</span><span style="color:#4ADE80;">{currency}{total:,.2f}</span>
        </div>
        <div style="margin-top:12px;font-size:12px;color:#71717A;">Payment via <strong style="color:#A1A1AA;">{payment_mode}</strong></div>
      </div>
    </div>
    <div style="background:#09090B;padding:16px 32px;text-align:center;font-size:12px;color:#52525B;">
      {tenant_name} &nbsp;·&nbsp; Thank you for shopping with us!
    </div>
  </div>
</body>
</html>"""

    plain = (
        f"BILL RECEIPT — {invoice_no}\n"
        f"{tenant_name}\n"
        f"Date: {date_str}\n\n"
        f"Dear {customer_name},\n\n"
        f"Thank you for your purchase. Here are your bill details:\n\n"
        f"Items:\n{rows_plain}\n"
        f"Subtotal : {currency}{subtotal:,.2f}\n"
        f"Tax      : {currency}{tax:,.2f}\n"
        f"Total    : {currency}{total:,.2f}\n"
        f"Paid via : {payment_mode}\n\n"
        f"Thank you for shopping with us!\n— {tenant_name}"
    )
    return html, plain


def invite_email_html(name: str, email: str, password: str, role: str,
                      tenant_name: str, login_url: str) -> tuple[str, str]:
    """Returns (html, plain_text) for an invite email."""
    role_cap = role.capitalize()
    html = f"""
<!DOCTYPE html>
<html>
<body style="font-family:Inter,sans-serif;background:#09090B;color:#FAFAFA;margin:0;padding:0;">
  <div style="max-width:480px;margin:40px auto;background:#18181B;border:1px solid #27272A;border-radius:12px;overflow:hidden;">
    <div style="background:#2563EB;padding:24px 32px;">
      <div style="font-size:22px;font-weight:700;letter-spacing:-0.5px;">Smart Ledger</div>
      <div style="font-size:13px;opacity:0.8;margin-top:4px;">You've been invited to a workspace</div>
    </div>
    <div style="padding:32px;">
      <p style="margin:0 0 16px;font-size:15px;">Hi <strong>{name}</strong>,</p>
      <p style="margin:0 0 24px;font-size:14px;color:#A1A1AA;">
        You've been added to <strong style="color:#FAFAFA;">{tenant_name}</strong> as a <strong style="color:#FAFAFA;">{role_cap}</strong>.
        Use the credentials below to sign in.
      </p>
      <div style="background:#09090B;border:1px solid #27272A;border-radius:8px;padding:20px;margin-bottom:24px;">
        <div style="margin-bottom:12px;">
          <div style="font-size:10px;text-transform:uppercase;letter-spacing:0.1em;color:#71717A;margin-bottom:4px;">Login URL</div>
          <a href="{login_url}" style="color:#60A5FA;font-size:13px;">{login_url}</a>
        </div>
        <div style="margin-bottom:12px;">
          <div style="font-size:10px;text-transform:uppercase;letter-spacing:0.1em;color:#71717A;margin-bottom:4px;">Email</div>
          <div style="font-family:monospace;font-size:14px;color:#FAFAFA;">{email}</div>
        </div>
        <div>
          <div style="font-size:10px;text-transform:uppercase;letter-spacing:0.1em;color:#71717A;margin-bottom:4px;">Temporary Password</div>
          <div style="font-family:monospace;font-size:14px;color:#FAFAFA;">{password}</div>
        </div>
      </div>
      <a href="{login_url}" style="display:inline-block;background:#2563EB;color:#fff;text-decoration:none;padding:10px 24px;border-radius:8px;font-size:14px;font-weight:600;">
        Sign in now →
      </a>
      <p style="margin:24px 0 0;font-size:12px;color:#52525B;">
        Please change your password after your first login. If you weren't expecting this, ignore this email.
      </p>
    </div>
  </div>
</body>
</html>
"""
    plain = (
        f"Hi {name},\n\n"
        f"You've been invited to {tenant_name} on Smart Ledger as {role_cap}.\n\n"
        f"Login URL: {login_url}\n"
        f"Email: {email}\n"
        f"Temporary Password: {password}\n\n"
        f"Please change your password after first login.\n"
    )
    return html, plain
