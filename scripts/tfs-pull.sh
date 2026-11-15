#!/usr/bin/env bash
#
# STEP 1 of 2 — run this while you are ON the corporate network.
#
# Caches everything the app needs from the on-prem Azure DevOps server into
# .tfs-dump/ (git-ignored). Every call is a READ; nothing is written to Azure
# DevOps. When you are back at your desk, run scripts/tfs-load.sh to push the
# cache into the app — that step needs no corporate network at all.
#
#   ./scripts/tfs-pull.sh                 # everything (recommended)
#   ./scripts/tfs-pull.sh --insecure      # skip TLS verification (diagnosis)
#   ./scripts/tfs-pull.sh --sprints 20    # deeper per-sprint history
#
# Config comes from the repo-root .env (TFS_URL / TFS_PAT / TFS_PROJECT /
# TFS_AREA_PATH). The PAT is never printed.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

SPRINTS=12
PASSTHRU=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --sprints) SPRINTS="$2"; shift 2 ;;
    --insecure) PASSTHRU+=("--insecure"); shift ;;
    -h|--help) sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $1 (try --help)" >&2; exit 2 ;;
  esac
done

if [[ ! -f .env ]]; then
  echo "No .env at $ROOT/.env — TFS_URL / TFS_PAT / TFS_PROJECT must be set." >&2
  exit 1
fi

PY="$(command -v python3 || true)"
if [[ -z "$PY" ]]; then
  echo "python3 not found on PATH." >&2
  exit 1
fi

echo "================================================================"
echo " STEP 1/2  Caching Azure DevOps into .tfs-dump/"
echo " (read-only; must be on the corporate network)"
echo "================================================================"

# --- work items -------------------------------------------------------
# --stream is the one that matters: it pulls every delivery item in the area
# whatever iteration it sits in, which is where bugs and untriaged backlog
# live. The per-sprint pass runs too, because it builds summary.json.
echo
echo ">>> [1/2] Work items, iterations and the whole stream"
"$PY" scripts/tfs-dump.py --sprints "$SPRINTS" --stream "${PASSTHRU[@]+"${PASSTHRU[@]}"}"

# --- people -----------------------------------------------------------
echo
echo ">>> [2/2] Team members and sprint capacity"
"$PY" scripts/tfs-people.py "${PASSTHRU[@]+"${PASSTHRU[@]}"}"

# --- manifest ---------------------------------------------------------
# Stamps what was captured and when, so tfs-load.sh can tell you the age of
# the cache instead of silently loading something from last month.
"$PY" - <<'PYEOF'
import glob, json, os, time
from collections import Counter

OUT = ".tfs-dump"
items, types = 0, Counter()
for path in glob.glob(os.path.join(OUT, "sprints", "*.json")):
    try:
        with open(path, encoding="utf-8") as fh:
            for it in json.load(fh).get("items", []):
                items += 1
                types[it.get("fields", {}).get("System.WorkItemType")] += 1
    except (OSError, json.JSONDecodeError):
        pass

people = 0
try:
    with open(os.path.join(OUT, "people.json"), encoding="utf-8") as fh:
        data = json.load(fh)
        people = len(data.get("people") or [])
except (OSError, json.JSONDecodeError):
    pass

manifest = {
    "pulled_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    "pulled_at_epoch": int(time.time()),
    "work_items": items,
    "by_type": dict(types.most_common()),
    "people": people,
    "stream_pass": os.path.exists(os.path.join(OUT, "sprints", "_stream.json")),
}
with open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8") as fh:
    json.dump(manifest, fh, indent=2, ensure_ascii=False)

print()
print("=" * 64)
print(f" CACHED  {items} work items, {people} people")
for k, n in types.most_common():
    print(f"   {str(k):<24} {n:>6}")
print("=" * 64)
PYEOF

echo
echo "Done. .tfs-dump/ is up to date (git-ignored — real internal data)."
echo "Next, at your desk:  ./scripts/tfs-load.sh"
