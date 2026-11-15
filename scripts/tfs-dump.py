#!/usr/bin/env python3
"""Dump Azure DevOps work items sprint by sprint to local JSON.

Run this while you are ON the corporate network; analyse the output later
while off it. Every call is a READ — nothing is written to Azure DevOps.

    python3 scripts/tfs-dump.py                  # 8 most recent sprints
    python3 scripts/tfs-dump.py --sprints 20     # more history
    python3 scripts/tfs-dump.py --all            # every sprint
    python3 scripts/tfs-dump.py --stream         # EVERYTHING in the area,
                                                 # any iteration (bugs included)
    python3 scripts/tfs-dump.py --no-samples     # structure only, no text
    python3 scripts/tfs-dump.py --insecure       # skip TLS verify (diagnosis)

Output (all git-ignored, see .gitignore):

    .tfs-dump/iterations.json      every sprint the team has
    .tfs-dump/sprints/<name>.json  raw work items for that sprint
    .tfs-dump/sprints/_stream.json --stream: the whole area, any iteration
    .tfs-dump/summary.json         <- the compact one worth sharing

Config comes from the repo-root .env. The PAT is never printed or written.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / ".tfs-dump"
BATCH = 200  # Azure DevOps caps workitemsbatch at 200 ids

# Delivery work worth pulling stream-wide. Mirrors DEFAULT_SYNC_TYPES in
# backend/app/integrations/tfs_task_provider.py — keep the two in step.
STREAM_TYPES = (
    "Product Backlog Item", "Task", "Bug", "Feature", "Epic", "Impediment",
    "Issue", "Release", "User Story", "Requirement",
)


# ---------------------------------------------------------------- config
def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    path = ROOT / ".env"
    if not path.exists():
        sys.exit(f"No .env at {path}")
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip("'\"")
    return env


# ---------------------------------------------------------------- http
class Client:
    def __init__(self, base: str, pat: str, api: str, insecure: bool) -> None:
        self.base = base.rstrip("/")
        self.api = api
        self.auth = base64.b64encode(f":{pat}".encode()).decode()
        self.ctx = ssl._create_unverified_context() if insecure else None

    def _call(self, url: str, body: dict | None = None) -> dict:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data)
        req.add_header("Authorization", f"Basic {self.auth}")
        req.add_header("Accept", "application/json")
        if data:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=120, context=self.ctx) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:300]
            raise RuntimeError(f"HTTP {e.code} on {url}\n  {detail}") from None
        except urllib.error.URLError as e:
            raise RuntimeError(
                f"Cannot reach the server ({e.reason}).\n"
                "  Are you on the corporate network / Ethernet?"
            ) from None

    def get(self, path: str, **params) -> dict:
        params["api-version"] = self.api
        qs = urllib.parse.urlencode(params, safe="\\$")
        return self._call(f"{self.base}/{path.lstrip('/')}?{qs}")

    def post(self, path: str, body: dict) -> dict:
        return self._call(
            f"{self.base}/{path.lstrip('/')}?api-version={self.api}", body
        )


def safe_name(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s).strip("_")[:80] or "unnamed"


# ---------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sprints", type=int, default=8, help="how many recent sprints")
    ap.add_argument("--all", action="store_true", help="every sprint")
    ap.add_argument("--stream", action="store_true",
                    help="also pull EVERY delivery item in the area, whatever "
                         "iteration it sits in (bugs and backlog live outside "
                         "the sprints)")
    ap.add_argument("--max", type=int, default=8000,
                    help="safety cap on --stream (default 8000)")
    ap.add_argument("--no-samples", action="store_true",
                    help="omit example field values from summary.json")
    ap.add_argument("--insecure", action="store_true", help="skip TLS verification")
    args = ap.parse_args()

    env = load_env()
    url, pat = env.get("TFS_URL", ""), env.get("TFS_PAT", "")
    project = env.get("TFS_PROJECT", "")
    area = env.get("TFS_AREA_PATH", "")
    api = env.get("TFS_API_VERSION", "7.1")
    if not (url and pat and project):
        sys.exit("TFS_URL / TFS_PAT / TFS_PROJECT must all be set in .env")

    c = Client(url, pat, api, args.insecure)
    (OUT / "sprints").mkdir(parents=True, exist_ok=True)

    print(f"server  : {url}")
    print(f"project : {project}")
    print(f"area    : {area or '(whole project)'}")
    print("=" * 70)

    # ---- 1. iterations -------------------------------------------------
    print("\n[1] Fetching iterations (sprints)")
    try:
        nodes = c.get(f"{project}/_apis/wit/classificationnodes/iterations",
                      **{"$depth": "5"})
    except RuntimeError as e:
        print(f"  {e}")
        return 1

    sprints: list[dict] = []

    def walk(n: dict, prefix: str = "") -> None:
        path = f"{prefix}\\{n['name']}" if prefix else n["name"]
        attrs = n.get("attributes") or {}
        kids = n.get("children", [])
        if not kids:  # leaf == an actual sprint
            sprints.append({
                "name": n["name"], "path": path,
                "start": attrs.get("startDate"), "finish": attrs.get("finishDate"),
            })
        for k in kids:
            walk(k, path)

    walk(nodes)
    sprints.sort(key=lambda s: s.get("start") or "", reverse=True)
    (OUT / "iterations.json").write_text(
        json.dumps(sprints, indent=2, ensure_ascii=False)
    )
    print(f"  found {len(sprints)} sprints -> .tfs-dump/iterations.json")

    picked = sprints if args.all else sprints[: args.sprints]
    print(f"  dumping {len(picked)}"
          f"{'' if args.all else f' most recent (--all for every one)'}")

    # ---- 2. per-sprint work items --------------------------------------
    print("\n[2] Work items per sprint")
    states: dict[str, Counter] = defaultdict(Counter)
    fields_seen: Counter = Counter()
    samples: dict[str, list] = defaultdict(list)
    totals = Counter()
    longest_title = 0
    grand = 0

    for i, sp in enumerate(picked, 1):
        where = [
            f"[System.TeamProject] = '{project.replace(chr(39), chr(39)*2)}'",
            f"[System.IterationPath] UNDER '{sp['path'].replace(chr(39), chr(39)*2)}'",
        ]
        if area:
            where.append(f"[System.AreaPath] UNDER '{area.replace(chr(39), chr(39)*2)}'")
        wiql = ("SELECT [System.Id] FROM WorkItems WHERE " + " AND ".join(where)
                + " ORDER BY [System.ChangedDate] DESC")

        label = f"  {i}/{len(picked)} {sp['name'][:42]:<42}"
        try:
            res = c.post(f"{project}/_apis/wit/wiql", {"query": wiql})
        except RuntimeError as e:
            print(f"{label} FAILED: {str(e).splitlines()[0]}")
            continue

        ids = [w["id"] for w in res.get("workItems", [])]
        items: list[dict] = []
        for j in range(0, len(ids), BATCH):
            try:
                got = c.post("_apis/wit/workitemsbatch",
                             {"ids": ids[j:j + BATCH], "$expand": "fields"})
                items.extend(got.get("value", []))
            except RuntimeError as e:
                print(f"{label} batch failed: {str(e).splitlines()[0]}")

        for it in items:
            f = it.get("fields", {})
            wit = f.get("System.WorkItemType", "?")
            totals[wit] += 1
            states[wit][f.get("System.State", "?")] += 1
            longest_title = max(longest_title, len(f.get("System.Title", "") or ""))
            for k, v in f.items():
                if v not in (None, ""):
                    fields_seen[k] += 1
                    if len(samples[k]) < 3:
                        samples[k].append(v)

        grand += len(items)
        (OUT / "sprints" / f"{safe_name(sp['name'])}.json").write_text(
            json.dumps({"sprint": sp, "count": len(items), "items": items},
                       indent=2, ensure_ascii=False)
        )
        print(f"{label} {len(items):>5} items")

    # ---- 2b. whole-stream pass -----------------------------------------
    # Sprint-scoped queries miss anything parked outside the dumped sprints —
    # which is where bugs and untriaged backlog usually live. This pass asks by
    # AREA only. Test artifacts are excluded in the query rather than after the
    # fact: they were 40% of the raw count and the area holds ~15k items.
    if args.stream:
        print("\n[2b] Whole stream (every iteration)")
        types = "', '".join(STREAM_TYPES)
        where = [f"[System.TeamProject] = '{project.replace(chr(39), chr(39)*2)}'",
                 f"[System.WorkItemType] IN ('{types}')"]
        if area:
            where.append(f"[System.AreaPath] UNDER '{area.replace(chr(39), chr(39)*2)}'")
        wiql = ("SELECT [System.Id] FROM WorkItems WHERE " + " AND ".join(where)
                + " ORDER BY [System.ChangedDate] DESC")
        try:
            res = c.post(f"{project}/_apis/wit/wiql", {"query": wiql})
        except RuntimeError as e:
            print(f"  FAILED: {str(e).splitlines()[0]}")
            return 1

        ids = [w["id"] for w in res.get("workItems", [])]
        print(f"  {len(ids)} items in the area across every iteration")
        if len(ids) > args.max:
            print(f"  capping at --max {args.max} (most recently changed first)")
            ids = ids[: args.max]

        items: list[dict] = []
        for j in range(0, len(ids), BATCH):
            try:
                got = c.post("_apis/wit/workitemsbatch",
                             {"ids": ids[j:j + BATCH], "$expand": "fields"})
                items.extend(got.get("value", []))
                print(f"    fetched {len(items)}/{len(ids)}", end="\r")
            except RuntimeError as e:
                print(f"\n    batch failed: {str(e).splitlines()[0]}")

        (OUT / "sprints" / "_stream.json").write_text(
            json.dumps({"sprint": {"name": "(whole stream)", "path": area},
                        "count": len(items), "items": items},
                       indent=2, ensure_ascii=False)
        )
        kinds = Counter(i.get("fields", {}).get("System.WorkItemType") for i in items)
        iters = Counter(
            (i.get("fields", {}).get("System.IterationPath") or "").split("\\")[-1]
            for i in items
        )
        print(f"\n  wrote {len(items)} items -> .tfs-dump/sprints/_stream.json")
        print("  by type:")
        for k, n in kinds.most_common():
            print(f"    {str(k):<24} {n:>5}")
        print(f"  spread over {len(iters)} iterations; top 5:")
        for k, n in iters.most_common(5):
            print(f"    {str(k)[:34]:<34} {n:>5}")

    # ---- 3. summary ----------------------------------------------------
    print("\n[3] Building summary")
    summary = {
        "server": url,
        "project": project,
        "area_path": area,
        "api_version": api,
        "sprints_total": len(sprints),
        "sprints_dumped": len(picked),
        "work_items_dumped": grand,
        "longest_title_chars": longest_title,
        "types": {t: n for t, n in totals.most_common()},
        "states_by_type": {t: dict(cs.most_common()) for t, cs in states.items()},
        "field_population": {
            k: {"count": n, "pct": round(100 * n / grand) if grand else 0}
            for k, n in fields_seen.most_common(60)
        },
        "sprints": [
            {"name": s["name"], "path": s["path"], "start": s["start"],
             "finish": s["finish"]}
            for s in picked
        ],
    }
    if not args.no_samples:
        summary["field_samples"] = {
            k: [str(v)[:120] for v in vs] for k, vs in samples.items()
            if k in dict(fields_seen.most_common(60))
        }

    (OUT / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False)
    )

    print("=" * 70)
    print(f"{grand} work items across {len(picked)} sprints")
    print(f"longest title: {longest_title} chars")
    print("\ntypes:")
    for t, n in totals.most_common():
        print(f"  {t:<28} {n:>5}")
    print("\nkey scheduling fields (are story points populated?):")
    for k in ["Microsoft.VSTS.Scheduling.StoryPoints",
              "Microsoft.VSTS.Scheduling.Effort",
              "Microsoft.VSTS.Scheduling.RemainingWork",
              "Microsoft.VSTS.Scheduling.OriginalEstimate",
              "Microsoft.VSTS.Common.Priority",
              "Microsoft.VSTS.Common.AcceptanceCriteria"]:
        n = fields_seen.get(k, 0)
        pct = round(100 * n / grand) if grand else 0
        mark = "✅" if pct else "—"
        print(f"  {mark} {k.split('.')[-1]:<20} {n:>5} items ({pct}%)")
    print("\nWrote .tfs-dump/summary.json — share that file with Claude.")
    print("(Raw per-sprint items stay local in .tfs-dump/sprints/)")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\ninterrupted")
        sys.exit(130)
