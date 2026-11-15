# Syncing from on-prem Azure DevOps

The Northwind server (`tfs.northwind.example`) is only reachable from
the corporate ethernet/VPN, and the app usually runs where that network is not.
So the sync is split in two: **pull** the data while you have access, **load**
it whenever you like.

```
  corporate network                    anywhere
  ┌──────────────────┐                ┌──────────────────┐
  │ ./scripts/       │   .tfs-dump/   │ ./scripts/       │
  │   tfs-pull.sh    │ ─────────────▶ │   tfs-load.sh    │ ──▶ board
  │  (reads ADO)     │   (on disk)    │ (migrate + sync) │
  └──────────────────┘                └──────────────────┘
```

Everything is **read-only** against Azure DevOps. `PUSH_ENABLED=false` in the
repo-root `.env` makes the provider itself refuse writes, so no code path —
API, Celery, or autopilot — can mutate the real instance. The pull scripts only
ever issue GET/WIQL reads.

---

## Step 1 — pull (on the corporate network)

```bash
./scripts/tfs-pull.sh                 # everything
./scripts/tfs-pull.sh --sprints 20    # deeper per-sprint history
./scripts/tfs-pull.sh --insecure      # skip TLS verification (diagnosis only)
```

It runs the two underlying pulls in order and stamps a manifest:

1. **Work items** — `tfs-dump.py --sprints 12 --stream`. The `--stream` pass is
   the important one: it queries by **area path only**, with no iteration
   filter, so it catches everything in the stream regardless of which sprint it
   sits in. Bugs and untriaged backlog live outside the sprints, and a
   sprint-scoped query silently misses them.
2. **People** — `tfs-people.py`. Finds the team that owns the stream, then
   pulls its members and the sprint capacity.
3. **Manifest** — `.tfs-dump/manifest.json`, recording when the pull ran, how
   many items by type, how many people, and whether the stream pass happened.

Expect it to take a couple of minutes. Test artifacts (Test Case / Suite /
Plan) are excluded **in the query**, not afterwards — they are ~40% of the raw
count and the area holds roughly 15k work items.

### What lands on disk

| File | Contents |
|---|---|
| `.tfs-dump/iterations.json` | every sprint the project defines (146) |
| `.tfs-dump/sprints/Sprint_NNNN.json` | work items for that sprint |
| `.tfs-dump/sprints/_stream.json` | the whole area, any iteration |
| `.tfs-dump/people.json` | team survey, members, capacity per person |
| `.tfs-dump/summary.json` | compact overview — the one safe to share |
| `.tfs-dump/manifest.json` | when the pull ran and what it captured |

`.tfs-dump/` is **git-ignored** — it holds real internal work items and staff
names. Keep it that way.

---

## Step 2 — load (anywhere)

```bash
./scripts/tfs-load.sh          # migrate + sync + report
./scripts/tfs-load.sh --check  # report only, change nothing
```

Needs no corporate network — it only talks to your local containers. It:

1. reports the cache age, and warns if it is over a week old or has no stream pass
2. starts the stack if it is not already up, and waits for the API
3. runs `alembic upgrade head`
4. POSTs `/api/v1/tasks/sync`
5. prints what landed

The sync **upserts on work item id**, so running it repeatedly updates rather
than duplicates, and loading one sprint's cache leaves the other sprints alone.

### What a healthy load looks like

```
work items     940
people          43
sprints          8
open bugs        9
open issues     18

by type:
  Task                  561
  Product Backlog Item  186
  Issue                  99
  Feature                56
  Bug                    35
  Release                 3
```

---

## What comes across

- **Work items** — Product Backlog Item, Task, Bug, Feature, Epic, Impediment,
  Issue, Release, User Story, Requirement. `Removed` items are dropped rather
  than counted as done, which would inflate completion.
- **Type** — stored on each task, so a Bug reads as a Bug on the board instead
  of an anonymous task.
- **Sub-area** — the leaf of the ADO area path (`Storefront`, `Smart Assistant`,
  `Pulse`, `Loyalty`). This is the only real grouping synced work carries; the
  board badges and the sidebar "Filter by Area" both come from it. Items filed
  on the stream root have none, and get no badge.
- **Assignees** — matched on the ADO identity GUID, never the display name.
  Names on a real instance vary in spelling and do not survive a rename.
- **Estimates** — hours, from `OriginalEstimate`. Neither `StoryPoints` nor
  `Effort` is populated anywhere on this instance.
- **Bug/Issue detail** — read from `ReproSteps`, not `Description`, which is
  empty for those types.

### Capacity

The team does **not** fill in the sprint Capacity tab — the pull confirms this
each run. Everyone therefore falls back to a default of **60h per sprint**
(`DEFAULT_CAPACITY_HOURS` in `frontend/src/lib/capacity.ts`, and the column
default in the database). Sprint days off *are* configured on the server and
are read, so if capacity is ever entered the pull picks it up automatically and
the default stops applying.

Capacity is a **per-sprint** quantity, so every view that compares assigned
hours against it pins itself to exactly one sprint. Do not sum across sprints
and divide by one sprint's hours.

---

## When you need finer control

The wrapper covers the normal case; the underlying scripts take more options.

```bash
python3 scripts/tfs-dump.py --all          # every sprint the project defines
python3 scripts/tfs-dump.py --stream       # area-wide pass on its own
python3 scripts/tfs-dump.py --no-samples   # structure only, no text in summary
python3 scripts/tfs-people.py --sprint "Sprint 2405"
python3 scripts/tfs-people.py --team "Retail Platform"
./scripts/tfs-check.sh                     # verify the connection end to end
```

Offline, `INTEGRATION_PROVIDER=dump` replays the capture through the *same*
mapping code the live provider uses, so the Sync button, the sync endpoint and
the Celery job all behave identically — only the transport changes.

---

## Troubleshooting

**"Cannot reach the server"** — you are off the corporate network. The hostname
does not resolve on wifi.

**TLS errors** — try `--insecure` to confirm it is certificate trust and not
connectivity. Do not leave it on.

**"No team owns \<area\>"** — `tfs-people.py` prints every team with its area
path and exits. Re-run with `--team "<name>"`. Note the team that matters is
the one **subscribed to the sprint you care about**: several sub-teams
(`Storefront`, `Smart Assistant`, `Pulse`, `Loyalty`) own areas under the
stream but are subscribed to stale iteration sets — one still ends at Sprint 24
from October 2024. Capacity is stored per *(team, sprint)*, so the subscription
is what decides, not the area path.

**"capacity: EMPTY"** — expected on this instance; see Capacity above.

**Sync returns 503/502/429** — the message names the host. 503 means the server
did not respond (check the VPN), 429 is a rate limit.

**Assignees not matching** — check `team_members.external_id` is populated. If
`people.json` is missing, the import falls back to name matching, which
resolves almost nothing against real data.

---

## Pending

**One sprint at a time** — not yet implemented. The intent:

```bash
./scripts/tfs-pull.sh                        # just the sprint containing today
./scripts/tfs-pull.sh --sprint "Sprint 2403"
./scripts/tfs-pull.sh --all                  # today's behaviour: 12 sprints + stream
```

This needs a `--sprint NAME` option on `tfs-dump.py` (it currently takes
`--sprints N` and `--all`), with the same value passed through to
`tfs-people.py` so members and capacity line up with the work items from the
same run. `tfs-load.sh` needs no change — the sync already upserts.

Trade-off: a single-sprint pull drops the stream-wide pass, so bugs and backlog
parked outside sprints do not come in. That pass is how 16 open Issues and 5
open Bugs on the stream root were found. Use one sprint for the routine round
trip and `--all` periodically.
