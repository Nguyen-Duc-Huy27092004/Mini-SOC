# 🚨 Quick Fix: 401/403/500 Auth Errors

## Symptoms

```
Failed to load resource: the server responded with a status of 401 (Unauthorized)
- /api/v1/auth/me → 401
- /api/v1/auth/refresh → 401

Failed to load resource: the server responded with a status of 500 (Internal Server Error)
- /api/v1/auth/change-password → 500
```

---

## Root Causes

### 1. **401 Unauthorized**
- **Cause:** Cookies not being sent from browser
- **Why:** CORS configuration issue, COOKIE_SECURE=true but using HTTP

### 2. **403 Forbidden** 
- **Cause:** CSRF token validation failing
- **Why:** CSRF_VALIDATE_ORIGIN=true blocking requests

### 3. **500 Internal Server Error**
- **Cause:** Missing `await db.commit()` in change-password endpoint
- **Why:** Code bug (now fixed in codebase)

---

## ONE-COMMAND FIX

```bash
bash fix_auth_complete.sh
```

This script automatically:
1. ✅ Sets COOKIE_SECURE=false (for HTTP)
2. ✅ Clears COOKIE_DOMAIN (for same-origin)
3. ✅ Sets CSRF_VALIDATE_ORIGIN=false
4. ✅ Updates BACKEND_CORS_ORIGINS
5. ✅ Fixes VITE_WS_URL (no double /ws)
6. ✅ Rebuilds frontend
7. ✅ Restarts services
8. ✅ Validates fixes

**Time:** 3-5 minutes

---

## Manual Fix (Step-by-Step)

### Step 1: Check .env.production

```bash
cd /opt/mini-soc
cat .env.production | grep -E "COOKIE_SECURE|CSRF_VALIDATE|BACKEND_CORS"
```

**Expected:**
```
COOKIE_SECURE="false"
CSRF_VALIDATE_ORIGIN="false"
BACKEND_CORS_ORIGINS="http://192.168.10.4:2709,http://localhost:2709"
```

**If wrong, fix:**
```bash
# Edit file
nano .env.production

# Change these lines:
COOKIE_SECURE="false"           # Must be false for HTTP
COOKIE_DOMAIN=""                # Must be empty
CSRF_VALIDATE_ORIGIN="false"    # Must be false for dev
BACKEND_CORS_ORIGINS="http://your-server-ip:2709,http://localhost:2709"
```

### Step 2: Check WebSocket URL

```bash
grep VITE_WS_URL .env.production
```

**Expected:**
```
VITE_WS_URL="ws://192.168.10.4:2709/ws"
```

**NOT:**
```
VITE_WS_URL="ws://192.168.10.4:2709/ws/ws"  ← WRONG! Double /ws
```

**If wrong:**
```bash
sed -i 's|/ws/ws|/ws|g' .env.production
```

### Step 3: Rebuild Frontend

```bash
# Frontend needs rebuild to pick up VITE_WS_URL changes
docker-compose -f docker-compose.production.yml build --no-cache frontend
```

### Step 4: Restart Services

```bash
docker-compose -f docker-compose.production.yml restart backend frontend nginx
```

### Step 5: Wait & Test

```bash
# Wait 30 seconds for services to start
sleep 30

# Test health
curl http://localhost:2709/api/v1/health/ready

# Should return: {"status":"ok",...}
```

### Step 6: Clear Browser Cache

**IMPORTANT:** Browser may have cached bad CORS/cookies

```
Chrome/Edge:  Ctrl+Shift+Delete → Clear cookies & cache
Firefox:      Ctrl+Shift+Delete → Clear cookies & cache
```

### Step 7: Try Login Again

```
1. Open: http://your-server-ip:2709
2. Login with admin credentials
3. Check browser DevTools → Console
4. Should see no errors
```

---

## Verification Checklist

### Backend Container
```bash
# Check environment variables loaded
docker-compose -f docker-compose.production.yml exec backend env | grep COOKIE_SECURE

# Expected: COOKIE_SECURE=false
```

### Browser DevTools

**Console (F12):**
```
✓ No CORS errors
✓ No "Blocked by CORS policy" messages
✓ WebSocket connected (if on dashboard)
```

**Application → Cookies:**
```
✓ access_token (HttpOnly, SameSite=Lax)
✓ refresh_token (HttpOnly, SameSite=Lax)
✓ csrf_token (readable)
```

**Network → /api/v1/auth/login:**
```
Request Headers:
  Origin: http://192.168.10.4:2709
  
Response Headers:
  Access-Control-Allow-Origin: http://192.168.10.4:2709
  Access-Control-Allow-Credentials: true
  Set-Cookie: access_token=...; HttpOnly; SameSite=Lax
  Set-Cookie: refresh_token=...; HttpOnly; SameSite=Lax
```

---

## Still Not Working?

### Debug Step 1: Check Backend Logs

```bash
docker-compose -f docker-compose.production.yml logs --tail 100 backend | grep -iE "error|cors|cookie"
```

**Look for:**
```
❌ CORS error: Origin not allowed
   → Fix BACKEND_CORS_ORIGINS

❌ CSRF validation failed
   → Set CSRF_VALIDATE_ORIGIN=false

❌ Cookie secure mismatch
   → Set COOKIE_SECURE=false
```

### Debug Step 2: Test CORS Directly

```bash
curl -i -X OPTIONS http://localhost:2709/api/v1/health \
  -H "Origin: http://localhost:2709" \
  -H "Access-Control-Request-Method: GET"
```

**Expected response headers:**
```
Access-Control-Allow-Origin: http://localhost:2709
Access-Control-Allow-Credentials: true
Access-Control-Allow-Methods: GET, POST, PUT, PATCH, DELETE, OPTIONS
```

**If missing → CORS not working**

### Debug Step 3: Test Cookie Setting

```bash
# Login and capture cookies
curl -i -X POST http://localhost:2709/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"your-password"}' \
  -c /tmp/cookies.txt

# Check cookies file
cat /tmp/cookies.txt
```

**Expected:**
```
access_token    ...
refresh_token   ...
```

**If empty → Cookies not being set**

---

## Common Mistakes

### Mistake 1: COOKIE_SECURE=true with HTTP
```bash
# ❌ WRONG (for HTTP deployment)
COOKIE_SECURE="true"

# ✅ CORRECT
COOKIE_SECURE="false"
```

**Why:** Secure cookies only sent over HTTPS. HTTP deployment needs `false`.

### Mistake 2: CORS Missing Frontend URL
```bash
# ❌ WRONG (missing actual access URL)
BACKEND_CORS_ORIGINS="http://localhost:2709"

# ✅ CORRECT (includes server IP)
BACKEND_CORS_ORIGINS="http://192.168.10.4:2709,http://localhost:2709"
```

### Mistake 3: WebSocket Path Wrong
```bash
# ❌ WRONG (double /ws)
VITE_WS_URL="ws://192.168.10.4:2709/ws/ws"

# ✅ CORRECT
VITE_WS_URL="ws://192.168.10.4:2709/ws"
```

### Mistake 4: Not Rebuilding Frontend
```bash
# ❌ WRONG (just editing .env)
nano .env.production
docker-compose restart

# ✅ CORRECT (rebuild frontend for VITE_ vars)
nano .env.production
docker-compose build frontend
docker-compose restart
```

---

## Bug Fix: 500 Error in change-password

### Fixed in Code

**File:** `backend/app/api/v1/auth.py`

**Issue:** Missing `await db.commit()`

```python
# ❌ BEFORE (causes 500 error)
current_user.hashed_password = await hash_password(new_password)
db.add(current_user)
await revoke_all_user_sessions(db, current_user.id)  # ← Uses uncommitted data!

# ✅ AFTER (fixed)
current_user.hashed_password = await hash_password(new_password)
db.add(current_user)
await db.commit()  # ← Commit before revoking sessions
await revoke_all_user_sessions(db, current_user.id)
```

**Solution:** Code already fixed in repository. Rebuild backend:

```bash
docker-compose -f docker-compose.production.yml build --no-cache backend
docker-compose -f docker-compose.production.yml restart backend
```

---

## Quick Reference

### Files to Check
```
/opt/mini-soc/.env.production        ← All configuration
/opt/mini-soc/docker-compose.production.yml
```

### Key Variables
```
COOKIE_SECURE="false"
COOKIE_DOMAIN=""
CSRF_VALIDATE_ORIGIN="false"
BACKEND_CORS_ORIGINS="http://server-ip:port,http://localhost:port"
VITE_WS_URL="ws://server-ip:port/ws"
```

### Commands
```bash
# View config
cat .env.production

# Edit config
nano .env.production

# Rebuild frontend
docker-compose -f docker-compose.production.yml build frontend

# Restart services
docker-compose -f docker-compose.production.yml restart

# View logs
docker-compose -f docker-compose.production.yml logs backend

# Full reset
docker-compose -f docker-compose.production.yml down -v
sudo bash deploy_on_wazuh.sh
```

---

## Success Indicators

After fixing, you should see:

### In Browser DevTools → Console
```
✓ No CORS errors
✓ No 401 errors on /api/v1/auth/me
✓ No 403 errors on /api/v1/auth/refresh
✓ No 500 errors on /api/v1/auth/change-password
✓ WebSocket connected to ws://...
```

### In Browser DevTools → Application → Cookies
```
Domain: your-server-ip:2709

Cookies:
  access_token   (HttpOnly ✓, Secure ✗, SameSite Lax)
  refresh_token  (HttpOnly ✓, Secure ✗, SameSite Lax)
  csrf_token     (HttpOnly ✗, Secure ✗, SameSite Lax)
```

### In Browser → UI
```
✓ Can login successfully
✓ Dashboard loads
✓ No "Session expired" messages
✓ Can navigate between pages
✓ Can change password (no 500 error)
```

---

## Summary

**ONE COMMAND:**
```bash
bash fix_auth_complete.sh
```

**Or MANUAL STEPS:**
1. Edit `.env.production` (COOKIE_SECURE=false, CSRF_VALIDATE_ORIGIN=false)
2. Fix VITE_WS_URL (no double /ws)
3. Rebuild frontend
4. Restart services
5. Clear browser cache
6. Try login again

**Auth should work perfectly after this!** ✅

---

**Last Updated:** 2026-06-08  
**Bug Status:** All fixed in codebase ✅
