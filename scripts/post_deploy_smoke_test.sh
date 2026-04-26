#!/usr/bin/env bash
# Post-deploy end-to-end smoke test.
#
# Usage:
#   BASE_URL=https://your-app.up.railway.app \
#   BEARER=your-bearer-token \
#   SEMRUSH_KEY=sm_xxx_optional \
#   ./scripts/post_deploy_smoke_test.sh
#
# - If SEMRUSH_KEY is set, runs the registration validation against
#   real Semrush and exercises a real /analyze call.
# - If SEMRUSH_KEY is NOT set, skips Semrush validation and uses a fake
#   key so we can still verify the BYOK plumbing (analyze will return
#   "fetch failed" notes — that's expected and the test PASSES anyway).
set -euo pipefail

BASE_URL="${BASE_URL:-}"
BEARER="${BEARER:-}"
SEMRUSH_KEY="${SEMRUSH_KEY:-sm_FAKE_smoke_test_no_real_key}"

if [ -z "$BASE_URL" ] || [ -z "$BEARER" ]; then
  echo "Usage: BASE_URL=https://your-app... BEARER=xxx [SEMRUSH_KEY=sm_xxx] $0"
  exit 1
fi

PASS=0
FAIL=0

pass() { printf "  \033[32m✓\033[0m  %s\n" "$*"; PASS=$((PASS+1)); }
fail() { printf "  \033[31m✗\033[0m  %s\n" "$*"; FAIL=$((FAIL+1)); }

# ---------------------------------------------------------------------
echo "== 1. /health =="
H=$(curl -s -o /tmp/h.json -w "%{http_code}" "$BASE_URL/health" || echo 000)
[ "$H" = "200" ] && pass "/health 200" || fail "/health got $H ($(cat /tmp/h.json 2>/dev/null))"
grep -q '"status":"ok"' /tmp/h.json && pass "/health body ok" || fail "/health body unexpected"

# ---------------------------------------------------------------------
echo "== 2. /setup HTML reachable =="
S=$(curl -s -o /tmp/s.html -w "%{http_code}" "$BASE_URL/setup" || echo 000)
[ "$S" = "200" ] && pass "/setup 200" || fail "/setup got $S"
grep -q "衣帽间\|Setup" /tmp/s.html && pass "/setup served the HTML form" || fail "/setup HTML missing expected content"

# ---------------------------------------------------------------------
echo "== 3. analyze without bearer → 401 =="
H=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/analyze" \
    -H 'Content-Type: application/json' \
    -d '{"competitor_domains":["shaw.com"]}' || echo 000)
[ "$H" = "401" ] && pass "missing bearer rejected ($H)" || fail "expected 401, got $H"

# ---------------------------------------------------------------------
echo "== 4. analyze with bearer but no user_token → 400 =="
H=$(curl -s -o /tmp/r.json -w "%{http_code}" -X POST "$BASE_URL/analyze" \
    -H "Authorization: Bearer $BEARER" \
    -H 'Content-Type: application/json' \
    -d '{"competitor_domains":["shaw.com"]}' || echo 000)
if [ "$H" = "400" ]; then
  pass "missing user_token rejected ($H)"
elif [ "$H" = "200" ]; then
  pass "(server is in shared-key mode, user_token optional — that's fine)"
else
  fail "unexpected status $H: $(cat /tmp/r.json 2>/dev/null)"
fi

# ---------------------------------------------------------------------
echo "== 5. /register with $( [ "$SEMRUSH_KEY" = "sm_FAKE_smoke_test_no_real_key" ] && echo 'FAKE' || echo 'REAL') key =="
TOKEN_JSON=$(curl -s -X POST "$BASE_URL/register" \
    -H 'Content-Type: application/json' \
    -d "{\"semrush_api_key\":\"$SEMRUSH_KEY\",\"label\":\"smoke-test-$(date +%s)\"}" || echo '{}')
USER_TOKEN=$(echo "$TOKEN_JSON" | python3 -c "import json,sys;print(json.load(sys.stdin).get('user_token',''))" 2>/dev/null || true)

if [ -z "$USER_TOKEN" ]; then
  ERR=$(echo "$TOKEN_JSON" | python3 -c "import json,sys;print(json.load(sys.stdin).get('detail',''))" 2>/dev/null || echo "$TOKEN_JSON")
  if [ "$SEMRUSH_KEY" = "sm_FAKE_smoke_test_no_real_key" ] && echo "$ERR" | grep -qi "validate\|invalid\|API"; then
    pass "/register rejected fake key (server has VALIDATE_SEMRUSH_ON_REGISTER=true — good)"
    echo "    Re-run with VALIDATE_SEMRUSH_ON_REGISTER=false in dashboard, or pass a real SEMRUSH_KEY"
  else
    fail "/register failed: $ERR"
  fi
else
  pass "/register returned token: $USER_TOKEN"

  # -------------------------------------------------------------------
  echo "== 6. /usage shows fresh token =="
  curl -s "$BASE_URL/usage/$USER_TOKEN" > /tmp/u1.json
  USED=$(python3 -c "import json;print(json.load(open('/tmp/u1.json'))['daily_used'])")
  [ "$USED" = "0" ] && pass "fresh token has daily_used=0" || fail "expected 0, got $USED"

  # -------------------------------------------------------------------
  echo "== 7. /analyze with valid token =="
  curl -s -X POST "$BASE_URL/analyze" \
      -H "Authorization: Bearer $BEARER" \
      -H 'Content-Type: application/json' \
      -d "{\"user_token\":\"$USER_TOKEN\",\"competitor_domains\":[\"shaw.com\",\"mohawkflooring.com\"],\"product_focus\":\"commercial\"}" \
      > /tmp/a.json
  DS=$(python3 -c "import json;print(json.load(open('/tmp/a.json')).get('data_source','?'))")
  TOPICS=$(python3 -c "import json;d=json.load(open('/tmp/a.json'));print(len(d.get('topics',[])))")
  QU=$(python3 -c "import json;d=json.load(open('/tmp/a.json'));print(d.get('quota_used_today'))")
  echo "    data_source=$DS  topics=$TOPICS  quota_used_today=$QU"
  if [ "$DS" = "semrush" ] && [ "$TOPICS" -gt 0 ]; then
    pass "real Semrush call returned $TOPICS topics"
  elif [ "$DS" = "semrush" ] && [ "$TOPICS" = "0" ]; then
    pass "Semrush call ran but returned 0 topics (likely fake key — expected when SEMRUSH_KEY is fake)"
  else
    fail "unexpected response: $(head -c 300 /tmp/a.json)"
  fi
  [ "$QU" = "1" ] && pass "quota_used_today correctly = 1 (no double-count bug)" || fail "quota_used_today=$QU (expected 1)"

  # -------------------------------------------------------------------
  echo "== 8. /revoke + retry analyze → 401 =="
  curl -s -X POST "$BASE_URL/revoke" -H 'Content-Type: application/json' -d "{\"user_token\":\"$USER_TOKEN\"}" > /dev/null
  H=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/analyze" \
      -H "Authorization: Bearer $BEARER" \
      -H 'Content-Type: application/json' \
      -d "{\"user_token\":\"$USER_TOKEN\",\"competitor_domains\":[\"shaw.com\"]}" || echo 000)
  [ "$H" = "401" ] && pass "revoked token rejected ($H)" || fail "expected 401, got $H"
fi

echo
echo "===================="
printf "  PASSED: %d\n" "$PASS"
printf "  FAILED: %d\n" "$FAIL"
echo "===================="
[ "$FAIL" = "0" ]
