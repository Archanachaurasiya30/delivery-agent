#!/usr/bin/env bash
#
# STEP 2 of 2 — run this at your desk, after scripts/tfs-pull.sh.
#
# Loads the .tfs-dump/ cache into the app: brings the database schema up to
# date, replays the capture through the normal sync, and reports what landed.
# Needs no corporate network — it only talks to your local containers.
#
#   ./scripts/tfs-load.sh          # migrate + sync + report
#   ./scripts/tfs-load.sh --check  # report only, change nothing
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

CHECK_ONLY=0
[[ "${1:-}" == "--check" ]] && CHECK_ONLY=1
[[ "${1:-}" == "-h" || "${1:-}" == "--help" ]] && { sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'; exit 0; }

PORT="$(grep -oE '^\s*-\s*"([0-9]+):8000"' docker-compose.yml | grep -oE '[0-9]+:8000' | cut -d: -f1 | head -1)"
PORT="${PORT:-8002}"
API="http://localhost:${PORT}/api/v1"

echo "================================================================"
echo " STEP 2/2  Loading .tfs-dump/ into the app (localhost:${PORT})"
echo "================================================================"

# --- 1. is there a cache, and how old is it? --------------------------
if [[ ! -d .tfs-dump ]]; then
  echo "No .tfs-dump/ directory. Run ./scripts/tfs-pull.sh on the corporate network first." >&2
  exit 1
fi

python3 - <<'PYEOF'
import json, os, sys, time
try:
    with open(".tfs-dump/manifest.json", encoding="utf-8") as fh:
        m = json.load(fh)
except (OSError, json.JSONDecodeError):
    print("  (no manifest.json — cache predates tfs-pull.sh; loading it anyway)")
    sys.exit(0)

age_h = (time.time() - m.get("pulled_at_epoch", 0)) / 3600
print(f"  cache pulled : {m.get('pulled_at')}  ({age_h:.0f}h ago)")
print(f"  work items   : {m.get('work_items')}")
print(f"  people       : {m.get('people')}")
if not m.get("stream_pass"):
    print("  NOTE: no whole-stream pass in this cache — items outside the dumped")
    print("        sprints (untriaged bugs, backlog) will be missing.")
if age_h > 24 * 7:
    print("  NOTE: this cache is over a week old.")
PYEOF

# --- 2. containers up? ------------------------------------------------
echo
echo ">>> [1/3] Containers"
if ! docker compose ps --status running --services 2>/dev/null | grep -q backend; then
  echo "  backend is not running — starting the stack"
  docker compose up -d
  echo "  waiting for the API"
  for _ in $(seq 1 60); do
    curl -fsS "${API}/health" >/dev/null 2>&1 && break
    sleep 2
  done
fi
if ! curl -fsS "${API}/health" >/dev/null 2>&1; then
  echo "  API not answering on ${API}. Check: docker compose logs backend" >&2
  exit 1
fi
echo "  API is up"

if [[ "$CHECK_ONLY" == "1" ]]; then
  echo
  echo "--check: stopping before any change."
  exit 0
fi

# --- 3. schema --------------------------------------------------------
echo
echo ">>> [2/3] Database schema"
docker compose exec -T backend alembic upgrade head 2>&1 | grep -E "Running upgrade|already at|INFO.*head" || true
echo "  schema at head"

# --- 4. sync ----------------------------------------------------------
echo
echo ">>> [3/3] Sync"
RESP="$(curl -fsS -X POST "${API}/tasks/sync" --max-time 600)" || {
  echo "  sync failed. Check: docker compose logs backend" >&2
  exit 1
}
echo "  ${RESP}"

# --- 5. what landed ---------------------------------------------------
echo
echo "================================================================"
docker compose exec -T postgres psql -U delivery -d delivery_agent -tA -F'  ' -c "
select 'work items   ', count(*)::text from tasks
union all select 'people       ', count(*)::text from team_members
union all select 'sprints      ', count(*)::text from sprints
union all select 'open bugs    ', count(*)::text from tasks
  where work_item_type='Bug' and status<>'done'
union all select 'open issues  ', count(*)::text from tasks
  where work_item_type='Issue' and status<>'done';"
echo
echo "by type:"
docker compose exec -T postgres psql -U delivery -d delivery_agent -tA -F'  ' -c "
select coalesce(work_item_type,'(local)'), count(*)::text
from tasks group by 1 order by count(*) desc;" | sed 's/^/  /'
echo "================================================================"
echo "Open the board: http://localhost:3002"
