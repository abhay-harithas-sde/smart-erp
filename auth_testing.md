# Auth-Gated App Testing Playbook (Emergent Google Auth)

## Notes for ATH ERP
- Our app uses **JWT bearer tokens** (Authorization header + localStorage), NOT cookie session storage.
- Google flow: `session_id` (URL hash) → backend `POST /api/auth/google/session` with `X-Session-ID` header → backend calls Emergent's `/session-data` → upsert user + tenant → returns our own JWT.
- Both email/password login and Google login return the same JWT shape.

## Step 1: Create Test User & Session (only if using cookie flow)
Not applicable — we don't store session_tokens in DB. Instead:

## Step 2: Test Backend
# Google flow: get a real session_id from browser flow (auth.emergentagent.com), then:
curl -X POST "https://sme-hub-2.preview.emergentagent.com/api/auth/google/session" \
  -H "X-Session-ID: <session_id_from_url_hash>"
# → returns { token, user, tenant } — our JWT

# Use JWT like normal:
curl -X GET "https://sme-hub-2.preview.emergentagent.com/api/auth/me" \
  -H "Authorization: Bearer <our_jwt>"

## Step 3: Browser Testing
1. Visit /login
2. Click "Continue with Google" button
3. Expect redirect to auth.emergentagent.com
4. After Google login → redirected back to /#session_id=xxx
5. Frontend AuthCallback exchanges session_id for our JWT → stores in localStorage → navigates to /

## Success Indicators
- New Google email → new tenant auto-created, user becomes Owner
- Existing email (invited by another owner) → logs into their assigned tenant
- Existing email/password user → same account, both login methods work

## Checklist
- [ ] Multi-tenant isolation preserved
- [ ] Existing invited users log into correct tenant
- [ ] New Google users create their own tenant (Owner role)
- [ ] JWT expires per JWT_EXPIRE_HOURS setting
- [ ] Email/password flow still works alongside
