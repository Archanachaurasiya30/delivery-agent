# Technology Stack

**Project:** AI-Powered Delivery Management Agent
**Domain:** Python-based AI agent with web dashboard
**Researched:** 2026-02-05
**Overall Confidence:** MEDIUM (unable to verify latest versions via external sources)

## Research Methodology Note

This research was conducted with limited access to external verification sources (WebSearch, most WebFetch calls blocked, pip queries blocked). Recommendations are based on training data current through January 2025 and the one successful FastAPI documentation fetch. Version numbers and ecosystem trends should be verified against current PyPI and official documentation before implementation.

## Recommended Stack

### Python Runtime
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Python | 3.11+ | Runtime environment | Type hints, performance improvements, async support. 3.12+ preferred for speed gains. |

**Confidence:** HIGH (verified Python 3.12.4 available on system)

### AI Agent Framework
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| LangGraph | 0.2.x+ | AI agent orchestration | State machine approach for complex agent workflows. Built by LangChain team specifically for production agent systems. Better control flow than ReAct loops. Supports human-in-the-loop approval patterns (your "agent proposes, human approves" model). |

**Confidence:** MEDIUM (version unverified, but framework choice sound based on use case)

**Rationale for LangGraph over alternatives:**
- **vs CrewAI**: CrewAI excels at multi-agent role-playing scenarios (CEO, developer, designer working together). Your use case is a single agent with multiple capabilities, not a crew of persona-based agents. LangGraph's state graph model fits better.
- **vs AutoGen**: Microsoft's AutoGen is strong for conversational multi-agent systems with code execution. Overkill for your coordination-focused delivery agent. LangGraph provides cleaner control flow for your decision tree (standup → analyze → escalate blockers).
- **vs Custom**: LangGraph provides production-ready patterns (checkpointing, error recovery, streaming) that would take months to build correctly from scratch.

### Web Framework
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| FastAPI | 0.115+ | Backend API and dashboard server | Modern async Python framework with automatic OpenAPI docs, type validation via Pydantic, WebSocket support (for real-time agent updates), and excellent performance. Industry standard for Python AI applications. |

**Confidence:** HIGH (FastAPI documentation verified, version approximate)

**Why FastAPI over Django/Flask:**
- **vs Django**: Django is overkill for your use case. You need API-first with a JavaScript frontend, not server-side templates. Django's ORM, admin, and heavy middleware add complexity you don't need. FastAPI's async support crucial for long-running LLM calls without blocking.
- **vs Flask**: Flask is solid but synchronous by default. LLM calls take 1-30 seconds — you need async. FastAPI provides this plus automatic validation, OpenAPI docs, and modern Python type hints out of the box.

### LLM Abstraction Layer
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| LiteLLM | 1.50+ | Multi-provider LLM abstraction | Single interface for OpenAI, Anthropic, Azure OpenAI, and 100+ providers. Handles retries, fallbacks, cost tracking, and rate limiting. Avoids vendor lock-in. Simpler than LangChain's LLM abstraction. |

**Confidence:** MEDIUM (version unverified, library selection sound)

**Why LiteLLM over alternatives:**
- **vs LangChain LLM wrappers**: LangChain's abstractions are tightly coupled to the LangChain ecosystem. LiteLLM is provider-agnostic and works with any Python code. Cleaner separation of concerns.
- **vs direct API clients**: LiteLLM handles provider-specific quirks (token counting differences, retry strategies, response format normalization) so you don't maintain per-provider code.
- **vs custom wrapper**: LiteLLM is battle-tested across providers. Covers edge cases (streaming, function calling differences, rate limits) you'd spend weeks discovering.

### Frontend Framework
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| React | 18.x | Dashboard UI | Industry standard for complex interactive UIs. Large ecosystem, good tooling, excellent async state management options (TanStack Query). Team likely familiar. |
| Vite | 6.x | Build tool | Fast dev server, modern ESM-based bundling. Replaces Create React App (now deprecated). |
| TanStack Query | 5.x | Server state management | Handles API calls, caching, refetching, optimistic updates. Essential for real-time agent status updates and task management. |
| shadcn/ui | Latest | UI components | Accessible, customizable components built on Radix UI. Copy-paste approach means no dependency bloat. Looks professional with minimal effort. |

**Confidence:** MEDIUM (ecosystem choices sound, versions approximate)

**Why React over Next.js/Svelte/HTMX:**
- **vs Next.js**: You don't need SSR (server-side rendering) for a private dashboard. Next.js adds complexity (App Router, Server Components) that buys you nothing here. React + Vite is simpler and faster for your use case.
- **vs Svelte**: Svelte is excellent but smaller ecosystem. React's ecosystem for data management (TanStack Query), component libraries (shadcn/ui, Radix), and debugging tools is unmatched. Easier to hire for.
- **vs HTMX**: HTMX is great for server-rendered apps with sprinkles of interactivity. Your dashboard needs heavy client-side state (task lists, sprint boards, live agent status). HTMX would fight you. React embraces client-side complexity.

### Database
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| PostgreSQL | 16+ | Primary database | Tasks, sprints, standups, agent decisions. JSONB for flexible schema (agent reasoning artifacts). Strong transactions for approval workflows. |
| SQLAlchemy | 2.0+ | ORM | Async support, type-safe queries, migration management via Alembic. Python standard. |

**Confidence:** MEDIUM (versions approximate, choices standard)

**Why PostgreSQL:**
- **vs SQLite**: SQLite can't handle concurrent writes from multiple devs using the dashboard + agent background tasks. PostgreSQL required for multi-user.
- **vs MongoDB**: Your data is relational (tasks → sprints → developers). PostgreSQL's JSONB gives you flexible schema for LLM outputs while keeping relational integrity for core data.
- **vs MySQL**: PostgreSQL's JSONB, full-text search, and advanced query features (CTEs, window functions) are superior. Better fit for complex queries (finding blockers across sprints).

### Background Job Processing
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Celery | 5.4+ | Background tasks | Scheduled standups, async agent processing, delayed notifications. Industry standard, well-documented. |
| Redis | 7.2+ | Celery broker + cache | Message queue for Celery, caching for API responses. Simple, fast, battle-tested. |

**Confidence:** MEDIUM (versions approximate, Celery standard choice)

**Why Celery over alternatives:**
- **vs RQ (Redis Queue)**: RQ is simpler but less feature-rich. Celery handles scheduled tasks (cron-like), retries, task chains, and error handling better. Your standups need cron scheduling.
- **vs Dramatiq**: Dramatiq is excellent and more modern, but smaller ecosystem. Celery's maturity and extensive documentation outweigh Dramatiq's architectural improvements for your use case.
- **vs asyncio tasks**: Python asyncio alone can't persist tasks across restarts or distribute across workers. Celery provides durability and scalability.

### API/SDK Layer
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Pydantic | 2.x | Data validation | Type-safe request/response models. Integrates perfectly with FastAPI. JSON schema generation for frontend types. |
| httpx | 0.27+ | HTTP client | Async HTTP client for external API calls (future Webex/Azure DevOps integrations). Better than requests for async code. |

**Confidence:** MEDIUM (versions approximate, libraries standard)

### Development Tools
| Tool | Purpose | Notes |
|------|---------|-------|
| Ruff | Linting + formatting | Replaces Black, isort, Flake8 in one tool. 10-100x faster than alternatives. Python ecosystem moving to Ruff. |
| pytest | Testing | Python standard. Async support via pytest-asyncio. |
| mypy | Type checking | Catches type errors at development time. Essential for maintaining large Python codebases. |
| Alembic | Database migrations | Generates migrations from SQLAlchemy models. |

**Confidence:** MEDIUM (Ruff is current best practice, others standard)

## Complete Installation

```bash
# Python environment
python3.11 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Backend core
pip install fastapi[standard]>=0.115.0
pip install uvicorn[standard]>=0.30.0
pip install sqlalchemy>=2.0.0
pip install alembic>=1.13.0
pip install psycopg2-binary>=2.9.9  # PostgreSQL driver

# AI agent stack
pip install langgraph>=0.2.0
pip install langchain-core>=0.3.0
pip install litellm>=1.50.0

# Background jobs
pip install celery>=5.4.0
pip install redis>=5.0.0

# API/Data
pip install pydantic>=2.9.0
pip install httpx>=0.27.0

# Dev tools
pip install ruff>=0.7.0
pip install pytest>=8.3.0
pip install pytest-asyncio>=0.24.0
pip install mypy>=1.11.0

# Frontend (separate directory)
cd frontend
npm create vite@latest . -- --template react-ts
npm install
npm install @tanstack/react-query
npm install @radix-ui/react-*  # As needed for shadcn/ui
```

## Alternatives Considered

| Category | Recommended | Alternative | When to Use Alternative |
|----------|-------------|-------------|-------------------------|
| Agent Framework | LangGraph | CrewAI | Multi-agent role-playing (e.g., building a software team simulator). Not your use case. |
| Agent Framework | LangGraph | AutoGen | Heavy code execution, conversational debugging agents. Overkill for delivery coordination. |
| Web Framework | FastAPI | Django | Need Django admin, heavy server-side rendering, or traditional CMS features. Not your use case. |
| LLM Abstraction | LiteLLM | LangChain | Already deeply invested in LangChain ecosystem and using many LangChain integrations. |
| Frontend | React + Vite | Next.js | Need SEO, SSR, or multi-page marketing site. Not applicable for private dashboard. |
| Frontend | React | HTMX | Building mostly server-rendered app with light interactivity. Your dashboard is interaction-heavy. |
| Database | PostgreSQL | SQLite | Single-user development, simple POC. Not production multi-user. |
| Background Jobs | Celery | RQ | Very simple background job needs without scheduling. Celery's scheduling is crucial for standups. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| LangChain for orchestration | Overly complex LCEL (LangChain Expression Language) syntax. Hard to debug agent loops. Use it for retrieval/tools, not flow control. | LangGraph for agent orchestration, LangChain-core for tools/prompts |
| OpenAI SDK directly | Vendor lock-in. Hard to switch providers or implement fallbacks. | LiteLLM for provider abstraction |
| Create React App | Deprecated by React team. Slow build times, outdated dependencies. | Vite |
| Flask-SocketIO for real-time | Complicated to scale, poor async support. FastAPI's WebSocket support is native and async. | FastAPI WebSockets |
| Threads for background jobs | Can't persist across restarts, no retry logic, no scheduling. | Celery |
| Django ORM with FastAPI | Mixing async FastAPI with sync Django ORM creates headaches. | SQLAlchemy 2.0 (native async) |
| Pandas for task data | Overkill for transactional data. Slow, memory-hungry. Use for analytics if needed, not CRUD. | SQLAlchemy + Pydantic |

## Stack Patterns by Deployment

**Development:**
```bash
# Backend
uvicorn app.main:app --reload

# Celery worker (scheduled standups)
celery -A app.tasks worker --loglevel=info

# Celery beat (scheduler)
celery -A app.tasks beat --loglevel=info

# Frontend
cd frontend && npm run dev
```

**Production (On-Premises):**
- Uvicorn behind reverse proxy (nginx)
- Celery workers as systemd services
- PostgreSQL + Redis as system services or Docker containers
- Frontend served as static files from nginx
- Consider Docker Compose for simplified deployment

## Version Compatibility Notes

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| FastAPI 0.115+ | Pydantic 2.x | FastAPI <0.100 used Pydantic 1.x. Ensure Pydantic 2+ for recent FastAPI. |
| LangGraph 0.2+ | LangChain-core 0.3+ | LangGraph depends on langchain-core. Version mismatch causes import errors. |
| SQLAlchemy 2.0+ | Alembic 1.13+ | Alembic versions must support SQLAlchemy 2.0 syntax. |
| Celery 5.x | Redis 5.x+ | Celery works with Redis 3+, but 5+ recommended for security/performance. |

## Architecture Implications

This stack creates three-tier architecture:

1. **Frontend (React + Vite)**: Static SPA served from CDN/nginx
2. **Backend (FastAPI + LangGraph)**: API server + agent orchestration
3. **Workers (Celery + Redis)**: Background agent tasks, scheduled standups

**Communication:**
- Frontend ↔ Backend: REST + WebSocket (for live agent updates)
- Backend ↔ Database: SQLAlchemy (async)
- Backend ↔ Workers: Celery (via Redis)
- Backend ↔ LLMs: LiteLLM (uniform interface)

**Data Flow:**
1. User requests sprint plan via React dashboard
2. FastAPI endpoint validates request (Pydantic)
3. Queues background Celery task: "run agent planning"
4. LangGraph agent executes planning workflow (multiple LLM calls via LiteLLM)
5. Agent checkpoints state to PostgreSQL
6. WebSocket pushes progress updates to frontend
7. Agent returns proposed sprint for human approval
8. User approves/rejects via dashboard
9. Backend persists decision to PostgreSQL

## Open Questions Requiring Validation

Due to limited external verification, these items need validation during implementation:

1. **Current versions**: All version numbers are approximate based on training data through January 2025. Check PyPI for latest stable releases.
2. **LangGraph maturity**: Verify LangGraph 0.2+ has stabilized for production. Check GitHub issues for blockers.
3. **LiteLLM Azure OpenAI support**: Confirm LiteLLM's current Azure OpenAI integration quality (authentication, streaming, function calling).
4. **FastAPI WebSocket scaling**: Verify best practices for scaling WebSockets in production (may need Redis adapter for multi-process).
5. **React 19**: React 19 may be released by now. Check if stable and if TanStack Query supports it.

## Sources

- FastAPI Documentation: https://fastapi.tiangolo.com (HIGH confidence - verified Feb 2026)
- Training data through January 2025 (MEDIUM confidence - unverified for current state)
- System Python version verified: 3.12.4 (HIGH confidence)

**Note:** This research has MEDIUM overall confidence due to inability to verify current package versions, recent ecosystem changes, or emerging alternatives post-January 2025. Recommend validation phase before committing to stack.

---
*Stack research for: AI-Powered Delivery Management Agent*
*Researched: 2026-02-05*
*Confidence: MEDIUM (limited external verification)*
