#!/usr/bin/env python3
"""Pull member names and sprint CAPACITY for the Retail Platform
stream, anchored to the sprint the work items actually live in.

Companion to tfs-dump.py, which captures work items. Work items say *who* a task
is assigned to but nothing about *how much* that person can take on: capacity
lives on the Work API, per team, per sprint.

Run it while you are ON the corporate network. Every call is a READ — nothing
is written to Azure DevOps.

    python3 scripts/tfs-people.py                      # Sprint 2404 (contains today)
    python3 scripts/tfs-people.py --sprint "Sprint 2405"
    python3 scripts/tfs-people.py --insecure           # skip TLS verify

Why the team is picked the way it is: capacity is stored per (team, iteration).
An area path alone is not enough — the Retail Platform stream is split across a parent area
and sub-areas (Storefront, Smart Assistant, Pulse), and a sub-team can be
subscribed to a completely different iteration set. So this surveys EVERY team,
prints which ones own a Retail Platform area and which are subscribed to the target sprint,
and pulls capacity from the teams where both are true.

Output (git-ignored, alongside the work-item dump):

    .tfs-dump/people.json    survey of all teams + members + capacity per person

Sprint hours = hours/day x (working days - personal days off - team days off),
which is how the Capacity tab totals it. The PAT is never printed.
"""

from __future__ import annotations

import argparse
import base64
import json
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / ".tfs-dump"
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday",
            "saturday", "sunday"]


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
    """Minimal read-only Azure DevOps client (stdlib only, as in tfs-dump)."""

    def __init__(self, base: str, pat: str, api: str, insecure: bool) -> None:
        self.base = base.rstrip("/")
        self.api = api
        self.auth = base64.b64encode(f":{pat}".encode()).decode()
        self.ctx = ssl._create_unverified_context() if insecure else None

    def get(self, path: str, **params) -> dict:
        params["api-version"] = self.api
        qs = urllib.parse.urlencode(params, safe="\\$")
        url = f"{self.base}/{path.lstrip('/')}?{qs}"
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"Basic {self.auth}")
        req.add_header("Accept", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=120, context=self.ctx) as r:
                body = r.read().decode("utf-8", "replace")
            return json.loads(body) if body.strip() else {}
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:300]
            raise RuntimeError(f"HTTP {e.code} on {url}\n  {detail}") from None
        except urllib.error.URLError as e:
            raise RuntimeError(
                f"Cannot reach the server ({e.reason}).\n"
                "  Are you on the corporate network / Ethernet?"
            ) from None
        except json.JSONDecodeError:
            raise RuntimeError(f"Non-JSON reply from {url} (auth redirect?)") from None


def q(segment: str) -> str:
    """URL-quote one path segment (team and project names contain spaces)."""
    return urllib.parse.quote(segment, safe="")


def values(payload: dict | list) -> list:
    """ADO returns either {"value": [...]} or a bare list, depending on release."""
    return payload if isinstance(payload, list) else (payload.get("value") or [])


# ---------------------------------------------------------------- dates
def as_date(value: str | None) -> date | None:
    """'2026-08-16T00:00:00Z' -> date(2026, 8, 16)."""
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def working_days(start: date, finish: date, week: list[str]) -> list[date]:
    """Every working day in the sprint, per the team's configured week."""
    allowed = {w.lower() for w in week} or set(WEEKDAYS[:5])
    days, cursor = [], start
    while cursor <= finish:
        if WEEKDAYS[cursor.weekday()] in allowed:
            days.append(cursor)
        cursor += timedelta(days=1)
    return days


def days_off_set(ranges: list[dict]) -> set[date]:
    """Flatten ADO's [{start, end}] day-off ranges into individual dates."""
    out: set[date] = set()
    for r in ranges or []:
        s, e = as_date(r.get("start")), as_date(r.get("end"))
        if not s or not e:
            continue
        cursor = s
        while cursor <= e:
            out.add(cursor)
            cursor += timedelta(days=1)
    return out


# ---------------------------------------------------------------- matching
def norm(path: str) -> str:
    return (path or "").strip().strip("\\").lower()


def in_stream(team_fields: dict, area_path: str) -> str | None:
    """The team's area path if it sits at, under, or above our stream.

    The Retail Platform stream is a parent area plus sub-areas, and each sub-area can have
    its own team, so "owns the exact area" is too narrow a test.
    """
    wanted = norm(area_path)
    if not wanted:
        return None
    for row in team_fields.get("values") or []:
        value = norm(row.get("value"))
        if not value:
            continue
        if value == wanted:
            return row.get("value")
        if value.startswith(wanted + "\\"):          # sub-area team
            return row.get("value")
        if row.get("includeChildren") and wanted.startswith(value + "\\"):
            return row.get("value")                  # parent team, incl. children
    return None


def dump_sprint(name: str | None) -> dict | None:
    """Resolve the target sprint from the work-item dump (the source of truth
    for where work actually sits), falling back to the sprint containing today.
    """
    try:
        rows = json.loads((OUT / "iterations.json").read_text())
    except (OSError, json.JSONDecodeError):
        return None
    if name:
        return next(
            (r for r in rows if (r.get("name") or "").lower() == name.lower()), None
        )
    today = date.today()
    for r in rows:
        s, f = as_date(r.get("start")), as_date(r.get("finish"))
        if s and f and s <= today <= f:
            return r
    return None


# ---------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sprint", default="",
                    help="sprint name (default: the one containing today)")
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
    OUT.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []

    # ---- 0. which sprint are we asking about? ---------------------------
    target = dump_sprint(args.sprint or None)
    if target is None and args.sprint:
        target = {"name": args.sprint, "path": f"{project}\\{args.sprint}"}
    if target is None:
        sys.exit("Could not resolve a sprint. Pass --sprint \"Sprint 2404\".")
    t_name, t_path = target.get("name"), target.get("path")

    print(f"server  : {url}")
    print(f"project : {project}")
    print(f"area    : {area or '(not set)'}")
    print(f"sprint  : {t_name}  ({target.get('start', '?')[:10]} -> "
          f"{target.get('finish', '?')[:10]})")
    print("=" * 78)

    # ---- 1. survey every team ------------------------------------------
    print("\n[1] Surveying teams (area path + is it subscribed to this sprint?)")
    try:
        all_teams = values(c.get(f"_apis/projects/{q(project)}/teams"))
    except RuntimeError as e:
        print(f"  {e}")
        return 1
    print(f"  {len(all_teams)} teams in {project}\n")

    survey: list[dict] = []
    for t in all_teams:
        name = t.get("name", "")
        row = {"id": t.get("id"), "name": name, "area_path": None,
               "in_stream": False, "subscribed": False, "iterations": 0,
               "iteration_id": None}
        try:
            fields = c.get(
                f"{q(project)}/{q(name)}/_apis/work/teamsettings/teamfieldvalues"
            )
            row["area_path"] = fields.get("defaultValue")
            row["in_stream"] = in_stream(fields, area) is not None
        except RuntimeError as e:
            errors.append(f"teamfieldvalues {name}: {str(e).splitlines()[0]}")
        try:
            iters = values(
                c.get(f"{q(project)}/{q(name)}/_apis/work/teamsettings/iterations")
            )
            row["iterations"] = len(iters)
            hit = next(
                (i for i in iters
                 if norm(i.get("path")) == norm(t_path)
                 or (i.get("name") or "").lower() == (t_name or "").lower()),
                None,
            )
            if hit:
                row["subscribed"] = True
                row["iteration_id"] = hit.get("id")
        except RuntimeError as e:
            errors.append(f"iterations {name}: {str(e).splitlines()[0]}")
        survey.append(row)

        mark = "*" if row["in_stream"] else " "
        sub = "YES" if row["subscribed"] else "no "
        print(f"  {mark} {name[:34]:<34} {sub}  {str(row['area_path'])[:34]:<34}"
              f" {row['iterations']:>3} its")

    picked = [r for r in survey if r["in_stream"] and r["subscribed"]]
    others = [r for r in survey if r["subscribed"] and not r["in_stream"]]
    print(f"\n  * = owns an area in {area!r}")
    print(f"  {len(picked)} team(s) both in-stream AND subscribed to {t_name}")
    if others:
        print(f"  ({len(others)} subscribed team(s) outside the stream, ignored)")

    if not picked:
        in_stream_only = [r for r in survey if r["in_stream"]]
        print(f"\n  No in-stream team is subscribed to {t_name}.")
        print(f"  In-stream teams and their iteration counts:")
        for r in in_stream_only:
            print(f"    {r['name'][:34]:<34} {r['iterations']:>3} iterations")
        print("\n  Capacity is stored per (team, sprint), so with no subscription")
        print("  there is no capacity to read. Names below are still usable.")

    # ---- 2. members + capacity ------------------------------------------
    print("\n[2] Members and capacity")
    teams_out: list[dict] = []
    # Names are worth having even from an in-stream team with no subscription.
    to_pull = picked or [r for r in survey if r["in_stream"]]
    roster: dict[str, dict] = {}
    rows_with_hours = 0

    for r in to_pull:
        name = r["name"]
        members: list[dict] = []
        try:
            raw = values(
                c.get(f"_apis/projects/{q(project)}/teams/{q(name)}/members")
            )
            for m in raw:
                ident = m.get("identity") or m
                members.append({
                    "id": ident.get("id"),
                    "name": ident.get("displayName"),
                    "unique_name": ident.get("uniqueName"),
                    "is_team_admin": m.get("isTeamAdmin", False),
                })
        except RuntimeError as e:
            errors.append(f"members {name}: {str(e).splitlines()[0]}")
        members.sort(key=lambda m: (m["name"] or "").lower())

        week: list[str] = []
        try:
            week = (c.get(f"{q(project)}/{q(name)}/_apis/work/teamsettings")
                    or {}).get("workingDays") or []
        except RuntimeError as e:
            errors.append(f"teamsettings {name}: {str(e).splitlines()[0]}")
        if not week:
            week = WEEKDAYS[:5]
            errors.append(f"{name}: no workingDays; assumed Mon-Fri")

        people: list[dict] = []
        sprint_days: list[date] = []
        team_off_days: set[date] = set()

        if r["subscribed"] and r["iteration_id"]:
            base = (f"{q(project)}/{q(name)}/_apis/work/teamsettings/"
                    f"iterations/{q(r['iteration_id'])}")
            try:
                caps = values(c.get(f"{base}/capacities"))
            except RuntimeError as e:
                errors.append(f"capacities {name}: {str(e).splitlines()[0]}")
                caps = []
            try:
                team_off = (c.get(f"{base}/teamdaysoff") or {}).get("daysOff", [])
            except RuntimeError as e:
                errors.append(f"teamdaysoff {name}: {str(e).splitlines()[0]}")
                team_off = []

            start, finish = as_date(target.get("start")), as_date(target.get("finish"))
            if start and finish:
                sprint_days = working_days(start, finish, week)
                team_off_days = days_off_set(team_off) & set(sprint_days)
            available = [d for d in sprint_days if d not in team_off_days]

            for cap in caps:
                who = cap.get("teamMember") or {}
                per_day = sum(
                    float((a or {}).get("capacityPerDay") or 0)
                    for a in (cap.get("activities") or [])
                )
                mine_off = days_off_set(cap.get("daysOff")) & set(available)
                my_days = len(available) - len(mine_off)
                hours = round(per_day * my_days, 1)
                if per_day > 0:
                    rows_with_hours += 1
                people.append({
                    "id": who.get("id"),
                    "name": who.get("displayName"),
                    "unique_name": who.get("uniqueName"),
                    "hours_per_day": per_day,
                    "working_days": my_days,
                    "days_off": len(mine_off),
                    "capacity_hours": hours,
                })
            people.sort(key=lambda p: (p["name"] or "").lower())

        cap_by_id = {p["id"]: p for p in people if p.get("id")}
        for m in members:
            key = m["id"] or m["unique_name"] or m["name"]
            entry = roster.setdefault(key, {
                "name": m["name"], "unique_name": m["unique_name"],
                "id": m["id"], "teams": [], "capacity_hours": 0.0,
                "hours_per_day": 0.0, "has_capacity": False,
            })
            entry["teams"].append(name)
            got = cap_by_id.get(m["id"])
            if got:
                entry["capacity_hours"] += got["capacity_hours"]
                entry["hours_per_day"] = max(entry["hours_per_day"],
                                             got["hours_per_day"])
                entry["has_capacity"] = entry["has_capacity"] or got["hours_per_day"] > 0

        total = round(sum(p["capacity_hours"] for p in people), 1)
        teams_out.append({
            "team": name,
            "area_path": r["area_path"],
            "subscribed_to_sprint": r["subscribed"],
            "working_days": week,
            "working_days_in_sprint": len(sprint_days),
            "team_days_off": sorted(d.isoformat() for d in team_off_days),
            "members": members,
            "capacity": people,
            "total_capacity_hours": total,
        })

        filled = sum(1 for p in people if p["hours_per_day"] > 0)
        state = f"{filled} with hours, {total} h" if r["subscribed"] else "not subscribed"
        print(f"\n  {name}  ({len(members)} members, {state})")
        for m in members:
            got = cap_by_id.get(m["id"])
            if got and got["hours_per_day"] > 0:
                print(f"      {(m['name'] or '?')[:32]:<32} "
                      f"{got['hours_per_day']:>4} h/d x {got['working_days']:>2} d "
                      f"= {got['capacity_hours']:>6} h")
            else:
                print(f"      {(m['name'] or '?')[:32]:<32} "
                      f"{m['unique_name'] or '':<20} (no capacity)")

    # ---- 3. write --------------------------------------------------------
    people_list = sorted(roster.values(), key=lambda p: (p["name"] or "").lower())
    payload = {
        "server": url,
        "project": project,
        "area_path": area,
        "sprint": target,
        "survey": survey,
        "teams": teams_out,
        "people": people_list,
        "errors": errors,
    }
    (OUT / "people.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False)
    )

    # ---- 4. verdict ------------------------------------------------------
    print("\n" + "=" * 78)
    print(f"sprint  : {t_name}")
    print(f"teams   : {len(teams_out)} pulled ({len(picked)} subscribed)")
    print(f"people  : {len(people_list)} distinct")
    if rows_with_hours:
        withc = sum(1 for p in people_list if p["has_capacity"])
        total = round(sum(p["capacity_hours"] for p in people_list), 1)
        print(f"capacity: {withc}/{len(people_list)} people, {total} hours total")
        print("\nCapacity IS configured — the import can use real hours.")
    else:
        print("capacity: none configured for this sprint")
        print("\nNo hours on the Capacity tab for any in-stream team. The names")
        print("above are still good — assignees can be fixed without capacity,")
        print("and capacity can be set per person in the app.")
    if errors:
        print(f"\n{len(errors)} non-fatal errors (first 8):")
        for e in errors[:8]:
            print(f"  - {e}")

    print("\nWrote .tfs-dump/people.json — tell Claude it is ready.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\ninterrupted")
        sys.exit(130)
