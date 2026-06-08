#!/bin/bash

# ============================================================
# Authentication Flow Test Script
# ============================================================
# Tests the complete auth flow including edge cases
# Usage: bash test_auth_flow.sh
# ============================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[TEST]${NC} $1"; }
log_success() { echo -e "${GREEN}[✓]${NC} $1"; }
log_fail() { echo -e "${RED}[✗]${NC} $1"; }

NGINX_PORT=${1:-2709}
BASE_URL="http://localhost:$NGINX_PORT/api/v1"
COOKIE_JAR="/tmp/mini_soc_cookies.txt"

# Clean up old cookies
rm -f "$COOKIE_JAR"

echo ""
log_info "======================================"
log_info "Authentication Flow Test"
log_info "======================================"
echo ""

# ============================================================
# Test 1: GET /auth/me without authentication (should be 401)
# ============================================================

log_info "Test 1: Access /auth/me without login..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    -b "$COOKIE_JAR" -c "$COOKIE_JAR" \
    "$BASE_URL/auth/me")

if [ "$STATUS" = "401" ]; then
    log_success "✓ Correctly returned 401 Unauthorized"
else
    log_fail "✗ Expected 401, got $STATUS"
fi

echo ""

# ============================================================
# Test 2: POST /auth/refresh without cookies (should be 401)
# ============================================================

log_info "Test 2: Call /auth/refresh without cookies..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST \
    -b "$COOKIE_JAR" -c "$COOKIE_JAR" \
    "$BASE_URL/auth/refresh")

if [ "$STATUS" = "401" ]; then
    log_success "✓ Correctly returned 401 Unauthorized"
elif [ "$STATUS" = "403" ]; then
    log_fail "✗ Got 403 (CSRF issue) - should be 401"
else
    log_fail "✗ Expected 401, got $STATUS"
fi

echo ""

# ============================================================
# Test 3: POST /auth/login with invalid credentials
# ============================================================

log_info "Test 3: Login with invalid credentials..."
RESPONSE=$(curl -s -w "\n%{http_code}" \
    -X POST \
    -b "$COOKIE_JAR" -c "$COOKIE_JAR" \
    -H "Content-Type: application/json" \
    -d '{"email":"invalid@example.com","password":"wrongpassword"}' \
    "$BASE_URL/auth/login")

STATUS=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | head -n-1)

if [ "$STATUS" = "401" ]; then
    log_success "✓ Login rejected with 401"
else
    log_fail "✗ Expected 401, got $STATUS"
fi

echo ""

# ============================================================
# Test 4: POST /auth/login with valid credentials
# ============================================================

log_info "Test 4: Login with admin credentials..."
echo "Enter admin email:"
read -r ADMIN_EMAIL
echo "Enter admin password:"
read -rs ADMIN_PASSWORD
echo ""

RESPONSE=$(curl -s -w "\n%{http_code}" \
    -X POST \
    -b "$COOKIE_JAR" -c "$COOKIE_JAR" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PASSWORD\"}" \
    "$BASE_URL/auth/login")

STATUS=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | head -n-1)

if [ "$STATUS" = "200" ]; then
    log_success "✓ Login successful"
    
    # Extract CSRF token
    CSRF_TOKEN=$(echo "$BODY" | grep -o '"csrf_token":"[^"]*"' | cut -d'"' -f4)
    if [ -n "$CSRF_TOKEN" ]; then
        log_success "✓ CSRF token received: ${CSRF_TOKEN:0:20}..."
    else
        log_fail "✗ No CSRF token in response"
    fi
else
    log_fail "✗ Login failed with status $STATUS"
    echo "$BODY"
    exit 1
fi

echo ""

# ============================================================
# Test 5: GET /auth/me with valid session
# ============================================================

log_info "Test 5: Access /auth/me with valid session..."
RESPONSE=$(curl -s -w "\n%{http_code}" \
    -b "$COOKIE_JAR" -c "$COOKIE_JAR" \
    "$BASE_URL/auth/me")

STATUS=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | head -n-1)

if [ "$STATUS" = "200" ]; then
    log_success "✓ Successfully retrieved user profile"
    EMAIL=$(echo "$BODY" | grep -o '"email":"[^"]*"' | cut -d'"' -f4)
    log_success "✓ Logged in as: $EMAIL"
else
    log_fail "✗ Expected 200, got $STATUS"
fi

echo ""

# ============================================================
# Test 6: POST /auth/refresh with valid cookies
# ============================================================

log_info "Test 6: Call /auth/refresh with valid session..."
RESPONSE=$(curl -s -w "\n%{http_code}" \
    -X POST \
    -b "$COOKIE_JAR" -c "$COOKIE_JAR" \
    -H "X-CSRF-Token: $CSRF_TOKEN" \
    "$BASE_URL/auth/refresh")

STATUS=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | head -n-1)

if [ "$STATUS" = "200" ]; then
    log_success "✓ Token refresh successful"
    
    NEW_CSRF=$(echo "$BODY" | grep -o '"csrf_token":"[^"]*"' | cut -d'"' -f4)
    if [ -n "$NEW_CSRF" ]; then
        log_success "✓ New CSRF token received"
        CSRF_TOKEN="$NEW_CSRF"
    fi
else
    log_fail "✗ Refresh failed with status $STATUS"
    echo "$BODY"
fi

echo ""

# ============================================================
# Test 7: POST /auth/logout
# ============================================================

log_info "Test 7: Logout..."
RESPONSE=$(curl -s -w "\n%{http_code}" \
    -X POST \
    -b "$COOKIE_JAR" -c "$COOKIE_JAR" \
    -H "X-CSRF-Token: $CSRF_TOKEN" \
    "$BASE_URL/auth/logout")

STATUS=$(echo "$RESPONSE" | tail -n1)

if [ "$STATUS" = "200" ]; then
    log_success "✓ Logout successful"
else
    log_fail "✗ Logout failed with status $STATUS"
fi

echo ""

# ============================================================
# Test 8: Verify session is cleared
# ============================================================

log_info "Test 8: Verify session cleared after logout..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    -b "$COOKIE_JAR" -c "$COOKIE_JAR" \
    "$BASE_URL/auth/me")

if [ "$STATUS" = "401" ]; then
    log_success "✓ Session correctly cleared (401)"
else
    log_fail "✗ Expected 401, got $STATUS"
fi

echo ""

# ============================================================
# Summary
# ============================================================

log_success "======================================"
log_success "Authentication Flow Test Complete"
log_success "======================================"
echo ""
log_info "All critical auth endpoints tested"
log_info "Cookie jar saved at: $COOKIE_JAR"
echo ""

# Cleanup
rm -f "$COOKIE_JAR"
