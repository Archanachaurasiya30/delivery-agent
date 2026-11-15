# Delivery Agent — Azure DevOps extension

Surfaces the Delivery Agent **agent layer** (AI actions, proposals queue, release-confidence /
portfolio) as a project-level hub inside Azure DevOps. Azure DevOps keeps owning the delivery core —
work items, boards, backlog, iterations, repos, pipelines — and this hub adds the agent on top.

## Architecture

```
Azure DevOps web UI (dev.azure.com)
  └─ "Delivery Agent" hub (iframe) = the React app, bundled into this .vsix, served by ADO's CDN
       └─ fetch → hosted FastAPI backend (https://<reachable-host>/api/v1/*)
            └─ TFSTaskProvider ⇄ ADO REST API (work items)  +  Celery / LLM / Postgres
```

The iframe is **pure UI**: it calls the hosted backend, which is the brain (AI, DB, queue) and which
syncs ADO work items via its existing `TFSTaskProvider`. The hub itself does not call the ADO REST
API, so the manifest requests no `scopes` in this version.

## Prerequisites

- A **reachable, HTTPS backend** (the FastAPI stack from `../backend`). For local testing, expose it
  with a dev tunnel (VS dev tunnels / ngrok) or deploy it. Run it with `INTEGRATION_PROVIDER=tfs`
  (+ `TFS_URL` / `TFS_PAT` / `TFS_PROJECT`) so the agent reasons over real ADO work items.
- Node.js (LTS) and the packaging tool: `npm install -g tfx-cli`.
- A Marketplace **publisher** (free): https://aka.ms/vsmarketplace-manage — then set `publisher` in
  `vss-extension.json` (currently `REPLACE_WITH_YOUR_PUBLISHER_ID`).

## Build the hub bundle

From `../frontend`, build the ADO bundle with the backend URL baked in. Output lands in
`extension/web/` (git-ignored):

```bash
cd ../frontend
npm install
VITE_API_BASE_URL=https://<your-backend-host> npm run build:ado
```

> If `VITE_API_BASE_URL` is omitted, the bundle falls back to relative `/api/v1` paths — useful only
> if the backend is same-origin. Inside ADO it must be an absolute URL.

## Package the .vsix

```bash
cd ../extension
tfx extension create --manifest-globs vss-extension.json
```

This produces `<publisher>.delivery-agent-0.1.0.vsix`.

## Install (sideload, private)

1. Publish/share the extension to your org, or upload the `.vsix` directly:
   Organization settings → **Extensions** → **Manage extensions** → **Upload extension**.
2. Install it to your organization, then open a project — **Delivery Agent** appears in the project
   left-nav. Open it and confirm the Proposals / AI Agent pages load and reach the backend (check the
   browser Network tab; if a request is blocked by CORS, add the iframe origin to the backend — see
   `backend/app/main.py`).

## Notes / next steps

- **Auth:** v1 trusts the network (CORS only). To harden, inject a token at the single
  `apiFetch` seam in `frontend/src/lib/api.ts` — e.g. `SDK.getAppToken()` validated by FastAPI
  (HS256 with the extension secret), or a user-supplied API key. Adding `getAppToken` validation also
  means the backend needs a JWT-validation dependency.
- **Icon / Marketplace polish:** add `extension/icon.png` (128×128) and an `"icons": {"default":
  "icon.png"}` entry (plus screenshots) before a public listing.
- **Scopes:** add `"scopes": ["vso.work"]` only if the hub itself starts calling the ADO REST API.
