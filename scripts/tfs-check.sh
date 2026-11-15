#!/bin/bash
# Verify the read-only TFS connection end to end. Run from the repo root:
#
#   bash scripts/tfs-check.sh
#
# Safe to re-run: every call is a READ. Nothing is written to Azure DevOps.
# Reads TFS_URL / TFS_PROJECT / TFS_PAT from the repo-root .env.
# The PAT is never printed.

cd "$(dirname "$0")/.." || exit 1

if [[ ! -f .env ]]; then echo "No .env in $(pwd)"; exit 1; fi
# shellcheck disable=SC1091
set -a; source .env 2>/dev/null; set +a

HOST=$(echo "$TFS_URL" | sed -E 's#https?://([^/]+).*#\1#')
PASS=0; FAIL=0
ok()   { echo "  ✅ $1"; PASS=$((PASS+1)); }
bad()  { echo "  ❌ $1"; FAIL=$((FAIL+1)); }
info() { echo "     $1"; }

echo "TFS_URL     : $TFS_URL"
echo "TFS_PROJECT : $TFS_PROJECT"
echo "PAT         : ${#TFS_PAT} chars"
echo "PUSH_ENABLED: ${PUSH_ENABLED:-unset}  (must be false for read-only)"
echo "======================================================================"

# ---------------------------------------------------------------- 1. network
echo
echo "[1] Network"
if ping -c1 -t3 "$HOST" >/dev/null 2>&1 || nc -z -w5 "$HOST" 443 >/dev/null 2>&1; then
  ok "$HOST reachable"
else
  if ! nslookup "$HOST" >/dev/null 2>&1; then
    bad "$HOST does not resolve — you are not on the corporate network"
  else
    bad "$HOST resolves but port 443 refused"
  fi
  echo; echo "STOP: fix connectivity first (switch to Ethernet / connect VPN)."
  exit 1
fi

# ---------------------------------------------------------------- 2. TLS
echo
echo "[2] TLS"
TLS=$(curl -s -o /dev/null -w "%{http_code}" -m 20 "$TFS_URL/_apis/projects?api-version=7.1" 2>&1)
if [[ "$TLS" =~ ^[0-9]+$ ]] && [[ "$TLS" != "000" ]]; then
  ok "certificate trusted (server answered HTTP $TLS)"
  INSECURE=""
else
  bad "TLS verification failed — internal CA not trusted"
  info "Diagnosing with -k (insecure). Proper fix: import the CA into Keychain"
  info "and mark it trusted, or set REQUESTS_CA_BUNDLE in the containers."
  INSECURE="-k"
fi

# ------------------------------------------------------- 3. api version + auth
echo
echo "[3] API version + PAT authentication"
GOOD_VER=""
for V in "${TFS_API_VERSION:-7.1}" 7.1 6.0 5.0; do
  CODE=$(curl -s $INSECURE -o /tmp/.tfsproj -w "%{http_code}" -m 25 \
         -u ":$TFS_PAT" "$TFS_URL/_apis/projects?api-version=$V" 2>/dev/null)
  case "$CODE" in
    200) ok "api-version $V works and the PAT authenticated"; GOOD_VER="$V"; break ;;
    401) bad "api-version $V: 401 Unauthorized — PAT rejected"; break ;;
    404) info "api-version $V: 404 (not supported by this server), trying older" ;;
    *)   info "api-version $V: HTTP $CODE" ;;
  esac
done

if [[ -z "$GOOD_VER" ]]; then
  echo
  echo "STOP: could not authenticate."
  echo "  401 -> the PAT is expired/revoked, or lacks 'Work Items (Read)'."
  echo "         Create a new one at:"
  echo "         $TFS_URL/_usersSettings/tokens"
  echo "         then update TFS_PAT in .env"
  echo "  404 on every version -> TFS_URL is wrong. It must be the COLLECTION"
  echo "         url, e.g. https://$HOST/DefaultCollection"
  exit 1
fi

if [[ "$GOOD_VER" != "${TFS_API_VERSION:-7.1}" ]]; then
  echo
  info "ACTION: set TFS_API_VERSION=$GOOD_VER in .env"
fi

# ---------------------------------------------------------------- 4. project
echo
echo "[4] Project '$TFS_PROJECT'"
python3 - "$TFS_PROJECT" <<'PY'
import json, sys
try:
    d = json.load(open('/tmp/.tfsproj'))
except Exception as e:
    print(f"  ❌ could not parse project list: {e}"); sys.exit(0)
names = [p['name'] for p in d.get('value', [])]
want = sys.argv[1]
if want in names:
    print(f"  ✅ found (server has {len(names)} projects)")
else:
    print(f"  ❌ '{want}' NOT found. Available:")
    for n in names[:25]: print(f"       - {n}")
    print("     ACTION: set TFS_PROJECT in .env to the exact name above")
PY

# ---------------------------------------------------- 5. process / state names
echo
echo "[5] Work item states (provider assumes the Agile process)"
curl -s $INSECURE -m 25 -u ":$TFS_PAT" -o /tmp/.tfswit \
  "$TFS_URL/$TFS_PROJECT/_apis/wit/workitemtypes?api-version=$GOOD_VER" 2>/dev/null
python3 - <<'PY'
import json
try:
    d = json.load(open('/tmp/.tfswit'))
except Exception as e:
    print(f"  ❌ could not read work item types: {e}"); raise SystemExit
known = {"New","Active","Resolved","Closed","Done","Removed"}
seen, types = set(), []
for t in d.get('value', []):
    st = {s['name'] for s in t.get('states', [])}
    if st: types.append(t['name']); seen |= st
print(f"  types : {', '.join(types[:12])}")
print(f"  states: {', '.join(sorted(seen))}")
unmapped = seen - known
if not unmapped:
    print("  ✅ all states map cleanly (Agile-compatible)")
else:
    print(f"  ⚠️  UNMAPPED states: {', '.join(sorted(unmapped))}")
    print("     These import as 'backlog'. To fix, edit STATE_TO_STATUS in")
    print("     backend/app/integrations/tfs_task_provider.py")
PY

# ---------------------------------------------------------------- 6. area path
echo
echo "[6] Area path"
if [[ -z "${TFS_AREA_PATH:-}" ]]; then
  echo "  ⚠️  TFS_AREA_PATH empty — the sync pulls the WHOLE project."
else
  echo "  configured: $TFS_AREA_PATH"
fi
curl -s $INSECURE -m 25 -u ":$TFS_PAT" -o /tmp/.tfsarea \
  "$TFS_URL/$TFS_PROJECT/_apis/wit/classificationnodes/areas?\$depth=2&api-version=$GOOD_VER" 2>/dev/null
python3 - "${TFS_AREA_PATH:-}" <<'PY'
import json, sys
want = sys.argv[1].strip().strip("'\"")
try:
    d = json.load(open('/tmp/.tfsarea'))
except Exception as e:
    print(f"  ❌ could not read areas: {e}"); raise SystemExit
paths = []
def walk(n, prefix=""):
    p = f"{prefix}\\{n['name']}" if prefix else n['name']
    paths.append(p)
    for c in n.get('children', []): walk(c, p)
walk(d)
if want and want in paths:
    print(f"  ✅ area path exists")
elif want:
    print(f"  ❌ '{want}' not found. Valid paths:")
    for p in paths[:25]: print(f"       {p}")
    print("     ACTION: copy the exact path into TFS_AREA_PATH in .env")
else:
    print("  available areas:")
    for p in paths[:25]: print(f"       {p}")
PY

# ---------------------------------------------------------------- 7. the query
echo
echo "[7] The exact WIQL the sync will run"
WHERE="[System.TeamProject] = '$TFS_PROJECT'"
if [[ -n "${TFS_AREA_PATH:-}" ]]; then
  CLEAN=$(echo "$TFS_AREA_PATH" | sed "s/^'//;s/'$//")
  WHERE="$WHERE AND [System.AreaPath] UNDER '$CLEAN'"
fi
Q=$(python3 -c "import json,sys; print(json.dumps({'query': \
  'SELECT [System.Id] FROM WorkItems WHERE '+sys.argv[1]+' ORDER BY [System.ChangedDate] DESC'}))" "$WHERE")
curl -s $INSECURE -m 40 -u ":$TFS_PAT" -H "Content-Type: application/json" \
  -o /tmp/.tfswiql -d "$Q" \
  "$TFS_URL/$TFS_PROJECT/_apis/wit/wiql?api-version=$GOOD_VER" 2>/dev/null
python3 - "${TFS_MAX_ITEMS:-0}" <<'PY'
import json, sys
try:
    d = json.load(open('/tmp/.tfswiql'))
except Exception as e:
    print(f"  ❌ WIQL failed: {e}"); raise SystemExit
if 'message' in d:
    print(f"  ❌ {d['message']}"); raise SystemExit
n = len(d.get('workItems', []))
cap = int(sys.argv[1] or 0)
print(f"  ✅ query returned {n} work items")
if n == 0:
    print("     ⚠️  nothing matched — TFS_AREA_PATH is probably too narrow")
elif cap and n > cap:
    print(f"     will import the {cap} most recently changed (TFS_MAX_ITEMS={cap})")
PY

# ---------------------------------------------------------------- 8. container
echo
echo "[8] Docker container reachability"
if docker compose ps --status running 2>/dev/null | grep -q backend; then
  if docker compose exec -T backend python -c "
import httpx,sys
try:
    r=httpx.get('$TFS_URL/_apis/projects?api-version=$GOOD_VER',timeout=20,verify=False)
    print('reachable, HTTP',r.status_code); sys.exit(0)
except Exception as e:
    print('FAILED:',type(e).__name__); sys.exit(1)
" 2>/dev/null | grep -q reachable; then
    ok "backend container can reach the server"
  else
    bad "container CANNOT reach it (host can) — Docker DNS issue"
    IP=$(dscacheutil -q host -a name "$HOST" | awk '/ip_address/{print $2; exit}')
    info "FIX: add this under BOTH the 'backend' and 'worker' services"
    info "     in docker-compose.yml, then: docker compose up -d"
    info ""
    info "     extra_hosts:"
    info "       - \"$HOST:${IP:-<ip>}\""
  fi
else
  info "backend not running — start it with: docker compose up -d"
fi

echo
echo "======================================================================"
echo "checks passed: $PASS   failed: $FAIL"
if [[ $FAIL -eq 0 ]]; then
  echo
  echo "Ready. Run the first read-only sync:"
  echo "  curl -s -X POST http://localhost:8002/api/v1/tasks/sync | python3 -m json.tool"
fi
