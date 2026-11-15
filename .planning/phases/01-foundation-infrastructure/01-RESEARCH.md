# Phase 1: Foundation & Infrastructure - Research

**Researched:** 2026-02-05
**Domain:** Async AI agent infrastructure with LLM provider abstraction
**Confidence:** HIGH

## Summary

Phase 1 establishes the foundational infrastructure for an AI-powered delivery management agent with async-first architecture, human-in-the-loop approval workflows, and flexible LLM provider support. The research confirms that the planned stack (LangGraph, FastAPI, LiteLLM, React, PostgreSQL, Celery/Redis) represents current best practices for production AI agent systems in 2026.

The critical architectural insight is that async infrastructure, structured output validation, and provider abstraction cannot be retrofitted later without major rewrites. These must be built from day one. The research validates the "agent proposes, human approves" pattern as the standard approach for building trust in AI systems, with multiple frameworks now providing native support for human-in-the-loop workflows.

Key findings include: (1) LangGraph is the recommended orchestration framework for state-managed agents with human-in-the-loop patterns, (2) FastAPI's async capabilities make it the natural choice for I/O-bound LLM operations, (3) LiteLLM provides production-ready multi-provider abstraction with 8ms P95 latency, (4) SQLAlchemy 2.0 async with asyncpg is the standard for async database operations, and (5) structured output validation via Pydantic is essential for preventing hallucinated entity references.

**Primary recommendation:** Build async infrastructure, structured output validation, and LLM provider abstraction in Phase 1 as architectural foundations. These patterns are confirmed as non-negotiable for production AI agent systems in 2026.

## Standard Stack

The established libraries/tools for AI agent infrastructure with async operations:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **LangGraph** | 0.2+ | Agent orchestration with state management | Low-level framework used by Replit, Uber, LinkedIn, GitLab; native support for human-in-the-loop, durable execution, A2A/MCP standards (2026) |
| **FastAPI** | 0.115+ | Async API server and backend | Native async/await, automatic Pydantic validation, built-in OpenAPI docs; runs on ASGI enabling true concurrent request handling |
| **LiteLLM** | 1.50+ | Multi-provider LLM abstraction | Unified interface to 100+ LLMs in OpenAI format; 8ms P95 latency; built-in fallback, retry, load balancing |
| **SQLAlchemy** | 2.0+ | Async ORM and database access | First-class async support; standard for Python async database operations; used with asyncpg for PostgreSQL |
| **PostgreSQL** | 16+ | Primary database | JSONB for flexible LLM output storage; mature async drivers (asyncpg); trigger-based real-time notifications |
| **Pydantic** | 2.x | Data validation and schema definition | FastAPI integration; JSON schema generation for LLM structured outputs; runtime validation prevents hallucinated data |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **Celery** | 5.4+ | Distributed task queue | Scheduled jobs (standups), background agent processing; production standard for Python async tasks |
| **Redis** | 7.2+ | Message broker and result backend | Celery broker, WebSocket pub/sub, caching; fast transport for small messages |
| **React** | 18.x | Frontend UI framework | Industry standard with mature ecosystem; concurrent features via useSyncExternalStore |
| **Vite** | 6.x | Frontend build tool | Modern replacement for Create React App; fast HMR, optimized builds |
| **TanStack Query** | Latest | Frontend server state management | Handles async state, caching, background updates; integrates with React 18 concurrent features |
| **Uvicorn** | Latest | ASGI server | Production deployment with Gunicorn multi-worker setup for multi-core utilization |
| **asyncpg** | Latest | PostgreSQL async driver | Designed for asyncio; superior performance vs traditional drivers; recommended for SQLAlchemy async |
| **Alembic** | Latest | Database migrations | Standard migration tool for SQLAlchemy; supports async operations |
| **pytest-asyncio** | Latest | Async testing | Enables `@pytest.mark.asyncio` for testing async functions; AsyncMock support |
| **httpx** | Latest | Async HTTP client | AsyncClient for calling external APIs without blocking event loop |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| LangGraph | CrewAI, AutoGen | Multi-agent role-playing vs single agent; LangGraph better for state machines and HITL |
| Celery | ARQ | ARQ native asyncio but smaller ecosystem; Celery more mature, better monitoring |
| FastAPI | Flask, Django | FastAPI built for async, automatic validation; Flask/Django require extensions for async |
| LiteLLM | Direct provider SDKs | Direct SDKs have vendor lock-in; LiteLLM adds 8ms latency but enables fallback |
| PostgreSQL JSONB | MongoDB | Postgres hybrid (relational + JSONB) better for this use case; MongoDB loses relational integrity |

**Installation (Backend):**
```bash
# Core dependencies
pip install fastapi[all] uvicorn[standard] sqlalchemy[asyncio] asyncpg alembic
pip install pydantic pydantic-settings
pip install litellm
pip install langgraph langchain-core
pip install celery[redis] redis
pip install httpx
pip install pytest pytest-asyncio httpx

# Optional but recommended
pip install python-dotenv  # Environment variable management
pip install structlog      # Structured logging for audit trails
```

**Installation (Frontend):**
```bash
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install @tanstack/react-query axios
npm install -D tailwindcss postcss autoprefixer  # Styling (optional)
```

## Architecture Patterns

### Recommended Project Structure
```
delivery-agent/
├── backend/
│   ├── app/
│   │   ├── main.py                    # FastAPI app entry point
│   │   ├── config.py                  # Settings (Pydantic BaseSettings)
│   │   ├── database.py                # AsyncEngine, async_sessionmaker
│   │   ├── dependencies.py            # FastAPI dependency injection
│   │   │
│   │   ├── models/                    # SQLAlchemy models
│   │   │   ├── base.py                # Base model with common fields
│   │   │   ├── task.py                # Task model
│   │   │   ├── sprint.py              # Sprint model
│   │   │   ├── team.py                # TeamMember model
│   │   │   └── proposal.py            # Proposal model (agent outputs)
│   │   │
│   │   ├── schemas/                   # Pydantic schemas (request/response)
│   │   │   ├── task.py                # TaskCreate, TaskResponse
│   │   │   ├── sprint.py              # SprintCreate, SprintResponse
│   │   │   ├── team.py                # TeamMemberCreate, TeamMemberResponse
│   │   │   └── proposal.py            # ProposalCreate, ProposalResponse
│   │   │
│   │   ├── api/                       # API routers
│   │   │   ├── v1/
│   │   │   │   ├── tasks.py           # Task CRUD endpoints
│   │   │   │   ├── sprints.py         # Sprint CRUD endpoints
│   │   │   │   ├── team.py            # Team management endpoints
│   │   │   │   ├── agent.py           # Agent proposal endpoints
│   │   │   │   └── proposals.py       # Proposal approval endpoints
│   │   │   └── router.py              # Router aggregation
│   │   │
│   │   ├── services/                  # Domain logic (pure Python, no LLM)
│   │   │   ├── capacity.py            # Capacity calculation
│   │   │   ├── task_analyzer.py       # Task complexity analysis
│   │   │   ├── sprint_validator.py    # Sprint validation rules
│   │   │   └── entity_validator.py    # Validate entity references
│   │   │
│   │   ├── agents/                    # LangGraph agent orchestration
│   │   │   ├── base.py                # Base agent with common setup
│   │   │   ├── planning_agent.py      # Sprint planning agent
│   │   │   ├── coordinator.py         # Central agent coordinator
│   │   │   └── prompts.py             # System prompts and templates
│   │   │
│   │   ├── llm/                       # LLM provider abstraction
│   │   │   ├── base.py                # Abstract LLMProvider interface
│   │   │   ├── litellm_provider.py    # LiteLLM implementation
│   │   │   └── factory.py             # Provider factory (config-based)
│   │   │
│   │   ├── integrations/              # Pluggable integration adapters
│   │   │   ├── task_provider.py       # Abstract TaskProvider interface
│   │   │   ├── chat_provider.py       # Abstract ChatProvider interface
│   │   │   ├── mock_task_provider.py  # Mock implementation (v1)
│   │   │   └── mock_chat_provider.py  # Mock implementation (v1)
│   │   │
│   │   ├── workflows/                 # Proposal approval workflows
│   │   │   ├── states.py              # ProposalState enum (DRAFT, PENDING, etc.)
│   │   │   ├── proposal_workflow.py   # State machine logic
│   │   │   └── audit.py               # Audit trail logging
│   │   │
│   │   └── tasks/                     # Celery background tasks
│   │       ├── celery_app.py          # Celery configuration
│   │       ├── agent_tasks.py         # Agent execution tasks
│   │       └── scheduled_tasks.py     # Cron-like scheduled jobs
│   │
│   ├── alembic/                       # Database migrations
│   │   ├── versions/
│   │   └── env.py
│   │
│   ├── tests/
│   │   ├── conftest.py                # Pytest fixtures (AsyncClient, db session)
│   │   ├── test_api/                  # API endpoint tests
│   │   ├── test_services/             # Domain logic tests
│   │   ├── test_agents/               # Agent tests (mocked LLM)
│   │   └── test_workflows/            # Workflow tests
│   │
│   ├── pyproject.toml                 # Python dependencies
│   └── .env.example                   # Environment variable template
│
├── frontend/
│   ├── src/
│   │   ├── main.tsx                   # React entry point
│   │   ├── App.tsx                    # Root component
│   │   ├── api/                       # API client (axios/fetch)
│   │   ├── components/                # Reusable UI components
│   │   ├── pages/                     # Page components
│   │   │   ├── Dashboard.tsx          # Main dashboard
│   │   │   ├── TaskBoard.tsx          # Task management
│   │   │   ├── SprintPlanning.tsx     # Sprint planning UI
│   │   │   └── ProposalReview.tsx     # Proposal approval UI
│   │   ├── hooks/                     # Custom hooks (TanStack Query)
│   │   └── types/                     # TypeScript types
│   ├── package.json
│   └── vite.config.ts
│
├── docker-compose.yml                 # Local dev environment
└── README.md
```

### Pattern 1: Async-First Architecture
**What:** All LLM and I/O operations are async by default; endpoints return immediately, processing happens in background.

**When to use:** Every agent operation, database query, external API call.

**Implementation:**
```python
# Source: FastAPI patterns + LiteLLM docs
# API endpoint returns 202 Accepted immediately
@router.post("/agent/propose-sprint", status_code=202)
async def propose_sprint(
    sprint_config: SprintConfig,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Enqueue agent task, return immediately."""
    # Create proposal record in DRAFT state
    proposal = await create_proposal(db, type="sprint_planning", status="DRAFT")

    # Enqueue background task
    background_tasks.add_task(
        execute_agent_task,
        proposal_id=proposal.id,
        config=sprint_config
    )

    return {"proposal_id": proposal.id, "status": "processing"}

# Agent execution in background
async def execute_agent_task(proposal_id: str, config: SprintConfig):
    """Background task that calls LLM and updates proposal."""
    async with async_sessionmaker() as db:
        # Call LLM via LiteLLM (async)
        agent_output = await planning_agent.run(config)

        # Validate output
        validated = validate_proposal(agent_output, db)

        # Update proposal to PENDING_REVIEW
        await update_proposal(db, proposal_id, validated, status="PENDING_REVIEW")

        # Notify frontend via WebSocket
        await broadcast_proposal_update(proposal_id)
```

**Why this works:** UI never blocks, users can continue working. Background tasks handle expensive LLM calls. WebSocket updates notify UI when ready.

### Pattern 2: Structured Output with Validation
**What:** LLM outputs are validated against Pydantic schemas and cross-checked with database entities.

**When to use:** All agent outputs that reference database entities (team members, tasks, sprints).

**Implementation:**
```python
# Source: Pydantic for LLMs + entity validation patterns
# Define strict Pydantic schema for agent output
class SprintProposalOutput(BaseModel):
    """Structured schema for sprint planning agent output."""
    sprint_name: str
    start_date: date
    end_date: date
    proposed_tasks: List[str]  # Task IDs, not descriptions
    task_assignments: Dict[str, str]  # {task_id: team_member_id}
    reasoning: str
    confidence: Literal["high", "medium", "low"]

# Agent uses schema for structured output
async def planning_agent_run(config: SprintConfig) -> SprintProposalOutput:
    """Agent generates structured output, not free text."""
    # LiteLLM with Pydantic schema
    response = await litellm.acompletion(
        model="gpt-4",
        messages=messages,
        response_format=SprintProposalOutput  # Structured output
    )

    # Parse into Pydantic model (validation happens here)
    proposal = SprintProposalOutput.model_validate(response.choices[0].message.content)
    return proposal

# Validate entity references against database
async def validate_proposal(
    proposal: SprintProposalOutput,
    db: AsyncSession
) -> SprintProposalOutput:
    """Cross-check all entity references exist in database."""
    # Verify all task IDs exist
    tasks = await db.execute(
        select(Task).where(Task.id.in_(proposal.proposed_tasks))
    )
    existing_task_ids = {t.id for t in tasks.scalars()}
    invalid_tasks = set(proposal.proposed_tasks) - existing_task_ids
    if invalid_tasks:
        raise ValidationError(f"Invalid task IDs: {invalid_tasks}")

    # Verify all team member IDs exist
    members = await db.execute(
        select(TeamMember).where(TeamMember.id.in_(proposal.task_assignments.values()))
    )
    existing_member_ids = {m.id for m in members.scalars()}
    invalid_members = set(proposal.task_assignments.values()) - existing_member_ids
    if invalid_members:
        raise ValidationError(f"Invalid team member IDs: {invalid_members}")

    return proposal
```

**Why this works:** Pydantic validates structure, custom validator checks entities. Catches hallucinated references before storage.

### Pattern 3: LLM Provider Abstraction with Fallback
**What:** Abstract interface for LLM providers enables switching/fallback without code changes.

**When to use:** All LLM calls throughout the application.

**Implementation:**
```python
# Source: LiteLLM Router patterns
# Abstract provider interface
class LLMProvider(ABC):
    @abstractmethod
    async def complete(
        self,
        messages: List[Dict],
        response_format: Optional[Type[BaseModel]] = None
    ) -> Union[str, BaseModel]:
        pass

# LiteLLM implementation with fallback
class LiteLLMProvider(LLMProvider):
    def __init__(self, config: LLMConfig):
        # Router with multiple deployments
        self.router = Router(
            model_list=[
                {
                    "model_name": "gpt-4",
                    "litellm_params": {
                        "model": "azure/gpt-4",
                        "api_base": config.azure_endpoint,
                    }
                },
                {
                    "model_name": "gpt-4",  # Same name for fallback
                    "litellm_params": {
                        "model": "openai/gpt-4",
                        "api_key": config.openai_key,
                    }
                },
                {
                    "model_name": "gpt-4",  # Second fallback
                    "litellm_params": {
                        "model": "anthropic/claude-3-opus",
                        "api_key": config.anthropic_key,
                    }
                }
            ],
            fallbacks=[
                {"azure/gpt-4": ["openai/gpt-4"]},
                {"openai/gpt-4": ["anthropic/claude-3-opus"]}
            ],
            num_retries=3,
            timeout=60.0
        )

    async def complete(self, messages, response_format=None):
        """Automatic fallback on provider failure."""
        response = await self.router.acompletion(
            model="gpt-4",  # Router handles provider selection
            messages=messages,
            response_format=response_format
        )
        return response

# Factory for config-based provider selection
def create_llm_provider(config: LLMConfig) -> LLMProvider:
    if config.provider == "litellm":
        return LiteLLMProvider(config)
    # Could add other providers
    raise ValueError(f"Unknown provider: {config.provider}")
```

**Why this works:** LiteLLM Router handles fallback automatically. Config change switches providers without code changes.

### Pattern 4: Human-in-the-Loop Approval Workflow
**What:** All consequential agent actions go through proposal → review → approval → execution workflow.

**When to use:** Sprint planning, blocker routing, release decisions (anything that changes state).

**Implementation:**
```python
# Source: HITL patterns from Permit.io, Microsoft AG-UI
# State machine for proposal lifecycle
class ProposalState(str, Enum):
    DRAFT = "draft"                      # Agent working on it
    PENDING_REVIEW = "pending_review"    # Waiting for human
    APPROVED = "approved"                # Human approved
    REJECTED = "rejected"                # Human rejected
    EXECUTED = "executed"                # System executed
    FAILED = "failed"                    # Execution failed

# Proposal model with audit trail
class Proposal(Base):
    __tablename__ = "proposals"

    id: Mapped[str] = mapped_column(primary_key=True)
    type: Mapped[str]  # "sprint_planning", "blocker_routing", etc.
    state: Mapped[ProposalState]

    # Agent output (JSONB for flexibility)
    content: Mapped[Dict] = mapped_column(JSONB)
    reasoning: Mapped[str]  # Why agent proposed this
    confidence: Mapped[str]  # "high", "medium", "low"

    # Audit trail
    created_by_agent: Mapped[str]  # Agent name
    created_at: Mapped[datetime]
    reviewed_by: Mapped[Optional[str]]  # User ID
    reviewed_at: Mapped[Optional[datetime]]
    execution_result: Mapped[Optional[Dict]] = mapped_column(JSONB)

    # Prompt logging (full audit trail)
    prompt_log: Mapped[Dict] = mapped_column(JSONB)  # Full context sent to LLM

# API endpoints for approval
@router.post("/proposals/{proposal_id}/approve")
async def approve_proposal(
    proposal_id: str,
    user_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Human approves agent proposal."""
    proposal = await get_proposal(db, proposal_id)

    if proposal.state != ProposalState.PENDING_REVIEW:
        raise HTTPException(400, "Proposal not in reviewable state")

    # Update state
    proposal.state = ProposalState.APPROVED
    proposal.reviewed_by = user_id
    proposal.reviewed_at = datetime.utcnow()
    await db.commit()

    # Execute in background
    background_tasks.add_task(execute_proposal, proposal_id)

    return {"status": "approved", "execution": "queued"}

@router.post("/proposals/{proposal_id}/reject")
async def reject_proposal(
    proposal_id: str,
    user_id: str,
    reason: str,
    db: AsyncSession = Depends(get_db)
):
    """Human rejects agent proposal with feedback."""
    proposal = await get_proposal(db, proposal_id)

    proposal.state = ProposalState.REJECTED
    proposal.reviewed_by = user_id
    proposal.reviewed_at = datetime.utcnow()
    proposal.execution_result = {"rejection_reason": reason}
    await db.commit()

    # Optional: Feed rejection reason back to agent for learning
    await log_rejection_feedback(proposal, reason)

    return {"status": "rejected"}
```

**Why this works:** Clear state machine, explicit approval actions, full audit trail. No ambiguity about what agent did vs proposed.

### Pattern 5: SQLAlchemy Async Session Management
**What:** Proper async session lifecycle with FastAPI dependency injection.

**When to use:** All database operations.

**Implementation:**
```python
# Source: SQLAlchemy 2.0 async documentation
# database.py - Engine and sessionmaker setup
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine
)

# Create engine at startup
async_engine: AsyncEngine = create_async_engine(
    "postgresql+asyncpg://user:pass@localhost/db",
    echo=True,
    pool_pre_ping=True,  # Verify connections before using
    pool_recycle=3600,   # Recycle connections every hour
)

# Create sessionmaker (reuse this, don't recreate per request)
async_session_maker = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Don't expire objects after commit
)

# FastAPI dependency for injecting session
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that provides async database session."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

# Use in API endpoints
@router.get("/tasks")
async def list_tasks(
    db: AsyncSession = Depends(get_db)
):
    """Dependency injection provides session."""
    result = await db.execute(select(Task))
    tasks = result.scalars().all()
    return tasks

# Prevent implicit I/O with eager loading
@router.get("/tasks/{task_id}")
async def get_task_with_assignee(
    task_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Eager load relationships to avoid lazy loading I/O."""
    result = await db.execute(
        select(Task)
        .options(selectinload(Task.assignee))  # Eager load relationship
        .where(Task.id == task_id)
    )
    task = result.scalar_one()

    # Can access task.assignee without triggering I/O
    return {"task": task, "assignee": task.assignee}
```

**Why this works:** Single engine per application, short-lived sessions per request, explicit eager loading prevents implicit I/O.

### Pattern 6: WebSocket Real-Time Updates
**What:** Broadcast agent status updates to frontend without polling.

**When to use:** Long-running agent operations, proposal state changes.

**Implementation:**
```python
# Source: FastAPI WebSocket + Redis pub/sub patterns
# Connection manager with Redis pub/sub for multi-worker scaling
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.redis_client = redis.asyncio.Redis.from_url("redis://localhost")

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        """Broadcast to all local connections."""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)

        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn)

    async def broadcast_via_redis(self, channel: str, message: dict):
        """Publish to Redis for multi-worker broadcasting."""
        await self.redis_client.publish(channel, json.dumps(message))

    async def subscribe_to_redis(self, channel: str):
        """Subscribe to Redis and forward to local connections."""
        pubsub = self.redis_client.pubsub()
        await pubsub.subscribe(channel)

        async for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                await self.broadcast(data)

manager = ConnectionManager()

# WebSocket endpoint
@app.websocket("/ws/proposals")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Keep connection alive
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# Broadcast proposal updates
async def broadcast_proposal_update(proposal_id: str):
    """Called after proposal state changes."""
    message = {
        "type": "proposal_update",
        "proposal_id": proposal_id,
        "timestamp": datetime.utcnow().isoformat()
    }
    # Broadcast via Redis (works across multiple workers)
    await manager.broadcast_via_redis("proposals", message)
```

**Why this works:** Real-time updates without polling. Redis pub/sub scales across multiple workers.

### Anti-Patterns to Avoid
- **Synchronous LLM calls in API endpoints:** Blocks event loop, UI hangs. Always use background tasks or Celery.
- **String parsing of agent outputs:** Unreliable, can't validate. Always use Pydantic structured outputs.
- **Direct provider SDK imports in business logic:** Vendor lock-in. Use LLMProvider abstraction.
- **Lazy loading relationships in async context:** Triggers implicit I/O, breaks. Use `selectinload()`.
- **Single provider without fallback:** System unusable during provider outage. Use LiteLLM Router.
- **No entity validation:** Agent hallucinates invalid references. Cross-check with database.
- **Mutable global state for sessions:** Thread safety issues. Use dependency injection.
- **No audit trail for agent decisions:** Can't debug wrong recommendations. Log full prompts.

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Multi-provider LLM abstraction | Custom wrapper for each provider | LiteLLM | Handles 100+ providers, fallback logic, retry, streaming; 8ms overhead is negligible |
| Async task queue | Custom queue with asyncio | Celery (or ARQ for pure asyncio) | Production-proven, monitoring, retry, cron scheduling, distributed workers |
| Structured LLM output | Regex parsing or JSON.parse | Pydantic with response_format | Handles validation, nested structures, custom validators, clear error messages |
| Agent state management | Dict or custom state tracking | LangGraph state management | Built-in checkpointing, durable execution, human-in-the-loop interrupts |
| WebSocket scaling | In-memory connection list | Redis pub/sub | Scales across multiple workers, handles disconnects, message persistence |
| Database migrations | Manual SQL scripts | Alembic | Tracks versions, supports rollback, generates migrations from model changes |
| API documentation | Hand-written docs | FastAPI automatic OpenAPI | Generated from Pydantic schemas, interactive UI, always in sync with code |
| Session management | Global session variable | FastAPI dependency injection | Request-scoped, explicit lifecycle, testable, no global state |

**Key insight:** Modern Python async ecosystem has mature solutions for LLM infrastructure. Custom solutions miss edge cases (provider rate limits, connection pool exhaustion, checkpoint recovery). Use proven libraries, focus on domain logic.

## Common Pitfalls

### Pitfall 1: Implicit I/O in Async Context
**What goes wrong:** Lazy-loaded SQLAlchemy relationships trigger synchronous I/O in async context, blocking event loop.

**Why it happens:** SQLAlchemy 2.0 async doesn't allow implicit attribute access for relationships. Accessing `task.assignee` when not eager-loaded tries to load synchronously.

**How to avoid:**
- Use `selectinload()` or `joinedload()` to eager-load relationships in query
- Use `AsyncAttrs` mixin and `awaitable_attrs` accessor for explicit async access
- Set `lazy="raise"` on relationships during development to catch mistakes early
- Never access relationships without eager loading in async endpoints

**Warning signs:**
- `greenlet_spawn has not been called` errors
- Intermittent hangs in API responses
- Database queries logged after endpoint returns response

**Code example:**
```python
# WRONG - Implicit I/O
@router.get("/tasks/{task_id}")
async def get_task(task_id: str, db: AsyncSession = Depends(get_db)):
    task = await db.get(Task, task_id)
    return {"task": task.title, "assignee": task.assignee.name}  # ERROR: Implicit I/O

# RIGHT - Eager loading
@router.get("/tasks/{task_id}")
async def get_task(task_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Task)
        .options(selectinload(Task.assignee))  # Eager load
        .where(Task.id == task_id)
    )
    task = result.scalar_one()
    return {"task": task.title, "assignee": task.assignee.name}  # OK
```

### Pitfall 2: Hallucinated Entity References
**What goes wrong:** Agent generates proposals referencing non-existent team members, tasks, or sprints. Teams follow proposals, discover references don't exist.

**Why it happens:** LLMs generate plausible-sounding IDs/names without grounding in actual database state. Without validation, hallucinated data gets stored and displayed to users.

**How to avoid:**
- Define strict Pydantic schemas requiring IDs, not free-text names
- Validate all entity references against database before storing proposal
- Provide agent with explicit list of valid entities in context
- Use structured output format (response_format parameter) not free text
- Implement two-phase generation: agent generates template, system fills real data

**Warning signs:**
- Proposals reference people who left company
- Task IDs in proposals don't exist in database
- Agent suggests assignments to non-existent team members
- Dates fall on weekends/holidays

**Code example:**
```python
# Validation function (from Pattern 2)
async def validate_proposal(proposal: SprintProposalOutput, db: AsyncSession):
    """Cross-check all entity references."""
    # Verify task IDs
    tasks = await db.execute(select(Task).where(Task.id.in_(proposal.proposed_tasks)))
    existing_ids = {t.id for t in tasks.scalars()}
    invalid = set(proposal.proposed_tasks) - existing_ids
    if invalid:
        raise ValidationError(f"Invalid task IDs: {invalid}")
    # Similar for team members, sprints, etc.
```

### Pitfall 3: Synchronous Blocking in Background Tasks
**What goes wrong:** Background task uses sync code or blocks on I/O, exhausts Celery worker pool. New tasks queue up, system becomes unresponsive.

**Why it happens:** Mixing sync and async code. Calling sync functions in async context runs in threadpool, limited threads cause bottleneck.

**How to avoid:**
- Use async all the way: async LLM calls, async database, async HTTP clients
- If must call sync library, use `asyncio.to_thread()` to explicitly move to threadpool
- Configure Celery with sufficient worker processes for expected concurrency
- Set task time limits to prevent runaway tasks
- Monitor task queue depth and worker utilization

**Warning signs:**
- Celery worker pool at 100% utilization
- Task queue depth growing unbounded
- Long wait times before tasks start executing
- Workers log "long-running task" warnings

**Code example:**
```python
# WRONG - Sync LLM call in async task
@celery_app.task
async def process_proposal(proposal_id: str):
    # This blocks the worker!
    response = openai.Completion.create(...)  # Sync call

# RIGHT - Async LLM call
@celery_app.task
async def process_proposal(proposal_id: str):
    response = await litellm.acompletion(...)  # Async call

# ALTERNATIVE - Explicit thread usage for sync library
@celery_app.task
async def process_proposal(proposal_id: str):
    response = await asyncio.to_thread(
        openai.Completion.create, ...  # Explicit threadpool
    )
```

### Pitfall 4: Missing Fallback on Provider Failure
**What goes wrong:** Primary LLM provider (e.g., OpenAI) has outage. All agent operations fail. System unusable despite infrastructure being fine.

**Why it happens:** Tight coupling to single provider. No graceful degradation or fallback to alternative provider.

**How to avoid:**
- Use LiteLLM Router with multiple providers configured (Pattern 3)
- Configure fallback chain: Azure OpenAI → OpenAI → Anthropic
- Implement circuit breaker to detect provider failures quickly
- Cache recent proposals to reuse similar inputs when provider down
- Provide manual mode for creating proposals without agent

**Warning signs:**
- All agent requests failing simultaneously
- Error logs show provider-specific errors (OpenAI 503, rate limit)
- No fallback providers configured
- Tests only mock LLM, never test actual provider failures

**Code example:**
```python
# LiteLLM Router with fallback (from Pattern 3)
router = Router(
    model_list=[
        {"model_name": "gpt-4", "litellm_params": {"model": "azure/gpt-4"}},
        {"model_name": "gpt-4", "litellm_params": {"model": "openai/gpt-4"}},
        {"model_name": "gpt-4", "litellm_params": {"model": "anthropic/claude-3-opus"}},
    ],
    fallbacks=[
        {"azure/gpt-4": ["openai/gpt-4"]},
        {"openai/gpt-4": ["anthropic/claude-3-opus"]}
    ]
)
```

### Pitfall 5: No Audit Trail for Agent Decisions
**What goes wrong:** Three months later, can't reconstruct why agent made decision. Can't debug wrong recommendations. Compliance questions unanswerable.

**Why it happens:** Only storing agent outputs (proposals), not inputs (prompts, context, reasoning). Logging feels like overhead, deferred.

**How to avoid:**
- Store full prompt sent to LLM in proposal.prompt_log (JSONB column)
- Include agent reasoning in structured output (reasoning field)
- Tag each decision with model version, timestamp, context state
- Use structured logging (JSON format) for easy querying
- Define retention policy (e.g., keep 1 year for compliance)

**Warning signs:**
- Can't reproduce agent output for same inputs
- No record of what context was provided to agent
- Users ask "why did it suggest this?" and can't answer
- Only final proposal stored, not intermediate steps

**Code example:**
```python
# Audit trail in Proposal model (from Pattern 4)
class Proposal(Base):
    # ... other fields ...

    # Full audit trail
    prompt_log: Mapped[Dict] = mapped_column(JSONB)  # Complete prompt
    reasoning: Mapped[str]  # Agent's step-by-step reasoning
    confidence: Mapped[str]  # Agent's confidence level
    created_by_agent: Mapped[str]  # Which agent version
    created_at: Mapped[datetime]  # When

# Store prompt when creating proposal
async def create_proposal_with_audit(
    db: AsyncSession,
    agent_output: SprintProposalOutput,
    prompt_messages: List[Dict]  # Full prompt
):
    proposal = Proposal(
        type="sprint_planning",
        content=agent_output.model_dump(),
        reasoning=agent_output.reasoning,
        confidence=agent_output.confidence,
        prompt_log={
            "messages": prompt_messages,
            "model": "gpt-4",
            "timestamp": datetime.utcnow().isoformat()
        }
    )
    db.add(proposal)
    await db.commit()
```

### Pitfall 6: TOAST Performance Degradation with Large JSONB
**What goes wrong:** Storing large LLM outputs (>2KB) in JSONB causes TOAST storage overhead. Queries slow down, I/O spikes.

**Why it happens:** PostgreSQL moves large values to separate TOAST storage. Extra I/O to fetch TOAST data degrades performance.

**How to avoid:**
- Keep JSONB documents small (ideally <2KB)
- Store large content (full conversation history) in separate table or object storage
- Use JSONB for structured metadata, not large text blobs
- Monitor query performance, add indexes on frequently queried JSONB paths
- Consider splitting proposals: metadata in JSONB, large content in TEXT column

**Warning signs:**
- Slow queries when selecting proposals
- High disk I/O for seemingly simple queries
- EXPLAIN shows TOAST table access
- JSONB columns consistently >2KB

**Code example:**
```python
# WRONG - Storing large content in JSONB
class Proposal(Base):
    content: Mapped[Dict] = mapped_column(JSONB)  # Includes full conversation history

# RIGHT - Split metadata and large content
class Proposal(Base):
    # Small metadata in JSONB (<2KB)
    metadata: Mapped[Dict] = mapped_column(JSONB)  # {sprint_name, dates, confidence}

    # Large content in separate column
    reasoning: Mapped[str] = mapped_column(Text)  # Full reasoning text

    # Or reference to external storage
    conversation_url: Mapped[Optional[str]]  # S3/object storage URL
```

### Pitfall 7: Shared Async Session Across Concurrent Tasks
**What goes wrong:** Multiple concurrent tasks use same AsyncSession. Race conditions, corrupted state, hard-to-debug errors.

**Why it happens:** Reusing session across tasks for "efficiency". SQLAlchemy docs explicitly warn: AsyncSession "not safe for use in multiple concurrent tasks."

**How to avoid:**
- Create new AsyncSession per task using async_sessionmaker
- Use FastAPI dependency injection for request-scoped sessions
- Never share sessions across concurrent operations
- Use asyncio.TaskGroup or gather() but create separate sessions per task

**Warning signs:**
- Intermittent database errors with no clear cause
- "Session is already closed" errors
- Data corruption in concurrent writes
- Transactions rolling back unexpectedly

**Code example:**
```python
# WRONG - Shared session across tasks
async def process_multiple_proposals(proposal_ids: List[str], db: AsyncSession):
    tasks = [process_proposal(pid, db) for pid in proposal_ids]  # WRONG: shared db
    await asyncio.gather(*tasks)

# RIGHT - Separate session per task
async def process_multiple_proposals(proposal_ids: List[str]):
    async def process_with_session(pid: str):
        async with async_sessionmaker() as db:  # New session per task
            await process_proposal(pid, db)

    tasks = [process_with_session(pid) for pid in proposal_ids]
    await asyncio.gather(*tasks)
```

### Pitfall 8: Mock Integration Divergence
**What goes wrong:** v1 mocks are too simple. v2 real APIs have pagination, rate limits, auth expiry that break in production.

**Why it happens:** Mocks start simple, diverge from real API over time. No forcing function to keep accurate.

**How to avoid:**
- Design integration interface based on real API docs, not mock capabilities
- Include failure modes in mocks (timeouts, 429s, partial data)
- Run integration tests against real API staging even in v1
- Use contract testing to verify mocks match real API
- Document API complexity (pagination, rate limits) in interface comments

**Warning signs:**
- Mocks never fail or timeout
- Mocks return perfectly structured data always
- No pagination in mock responses
- Integration interface designed around mock simplicity

**Code example:**
```python
# Mock that simulates real API complexity
class MockTaskProvider(TaskProvider):
    """Mock that simulates real API behavior."""

    async def list_tasks(self, page: int = 1, page_size: int = 50) -> TaskPage:
        """Simulates pagination like real API."""
        # Simulate rate limit
        if random.random() < 0.01:  # 1% chance
            raise RateLimitError("Rate limit exceeded", retry_after=60)

        # Simulate timeout
        if random.random() < 0.005:  # 0.5% chance
            await asyncio.sleep(10)  # Simulate slow response
            raise TimeoutError("Request timeout")

        # Return paginated results
        total = 100
        start = (page - 1) * page_size
        end = start + page_size
        return TaskPage(
            items=self.tasks[start:end],
            total=total,
            page=page,
            page_size=page_size,
            has_more=end < total
        )
```

## Code Examples

Verified patterns from official sources:

### Async FastAPI Endpoint with Background Task
```python
# Source: FastAPI documentation + async patterns
from fastapi import BackgroundTasks, FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

@app.post("/agent/propose-sprint")
async def propose_sprint(
    config: SprintConfig,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """API endpoint returns immediately, processing in background."""
    # Create proposal in DRAFT state
    proposal = Proposal(
        type="sprint_planning",
        state=ProposalState.DRAFT,
        content=config.model_dump()
    )
    db.add(proposal)
    await db.commit()

    # Queue background task
    background_tasks.add_task(
        run_planning_agent,
        proposal_id=proposal.id,
        config=config
    )

    return {"proposal_id": proposal.id, "status": "processing"}
```

### LiteLLM with Pydantic Structured Output
```python
# Source: LiteLLM + Pydantic for LLMs documentation
import litellm
from pydantic import BaseModel

class SprintProposal(BaseModel):
    sprint_name: str
    task_ids: List[str]
    reasoning: str
    confidence: Literal["high", "medium", "low"]

async def generate_sprint_proposal(context: dict) -> SprintProposal:
    """Agent generates structured, validated output."""
    messages = [
        {"role": "system", "content": "You are a sprint planning assistant."},
        {"role": "user", "content": f"Plan sprint with context: {context}"}
    ]

    response = await litellm.acompletion(
        model="gpt-4",
        messages=messages,
        response_format=SprintProposal  # Structured output
    )

    # Parse and validate with Pydantic
    proposal = SprintProposal.model_validate_json(
        response.choices[0].message.content
    )
    return proposal
```

### SQLAlchemy Async Session with Eager Loading
```python
# Source: SQLAlchemy 2.0 async documentation
from sqlalchemy import select
from sqlalchemy.orm import selectinload

async def get_task_with_relationships(
    task_id: str,
    db: AsyncSession
) -> Task:
    """Eager load relationships to avoid implicit I/O."""
    result = await db.execute(
        select(Task)
        .options(
            selectinload(Task.assignee),      # Eager load assignee
            selectinload(Task.sprint),        # Eager load sprint
            selectinload(Task.comments)       # Eager load comments
        )
        .where(Task.id == task_id)
    )
    task = result.scalar_one()

    # Can now access relationships without triggering I/O
    print(f"Task: {task.title}")
    print(f"Assignee: {task.assignee.name}")
    print(f"Sprint: {task.sprint.name}")
    return task
```

### Celery Background Task for Agent Execution
```python
# Source: Celery + FastAPI integration patterns
from celery import Celery

celery_app = Celery("delivery-agent", broker="redis://localhost:6379/0")

@celery_app.task(bind=True, max_retries=3)
async def run_planning_agent(self, proposal_id: str, config: dict):
    """Background task for agent execution with retry."""
    async with async_sessionmaker() as db:
        try:
            # Get proposal
            proposal = await db.get(Proposal, proposal_id)

            # Run agent
            agent_output = await planning_agent.run(config)

            # Validate
            validated = await validate_proposal(agent_output, db)

            # Update proposal
            proposal.state = ProposalState.PENDING_REVIEW
            proposal.content = validated.model_dump()
            await db.commit()

            # Notify frontend via WebSocket
            await broadcast_proposal_update(proposal_id)

        except Exception as exc:
            # Retry on failure
            raise self.retry(exc=exc, countdown=60)  # Retry after 1 minute
```

### FastAPI Dependency for Database Session
```python
# Source: SQLAlchemy async + FastAPI dependency injection
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that provides database session."""
    async with async_sessionmaker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

# Usage in endpoint
@app.get("/tasks")
async def list_tasks(
    db: AsyncSession = Depends(get_db)  # Injected session
):
    result = await db.execute(select(Task))
    return result.scalars().all()
```

### TanStack Query for Frontend Server State
```typescript
// Source: TanStack Query React documentation
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

// Fetch proposals
function useProposals() {
  return useQuery({
    queryKey: ['proposals'],
    queryFn: async () => {
      const response = await fetch('/api/proposals');
      return response.json();
    },
    refetchInterval: 5000,  // Poll every 5s (or use WebSocket)
  });
}

// Approve proposal mutation
function useApproveProposal() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (proposalId: string) => {
      const response = await fetch(`/api/proposals/${proposalId}/approve`, {
        method: 'POST',
      });
      return response.json();
    },
    onSuccess: () => {
      // Invalidate and refetch proposals
      queryClient.invalidateQueries({ queryKey: ['proposals'] });
    },
  });
}

// Usage in component
function ProposalReview() {
  const { data: proposals, isLoading } = useProposals();
  const approveProposal = useApproveProposal();

  if (isLoading) return <div>Loading...</div>;

  return (
    <div>
      {proposals.map(proposal => (
        <div key={proposal.id}>
          <h3>{proposal.type}</h3>
          <button onClick={() => approveProposal.mutate(proposal.id)}>
            Approve
          </button>
        </div>
      ))}
    </div>
  );
}
```

### WebSocket Connection Manager
```python
# Source: FastAPI WebSocket documentation
from fastapi import WebSocket, WebSocketDisconnect
from typing import List

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        """Send message to all connected clients."""
        for connection in self.active_connections:
            await connection.send_json(message)

manager = ConnectionManager()

@app.websocket("/ws/proposals")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| LangChain for orchestration | LangGraph for state management | 2024-2025 | LangGraph provides lower-level control, better for state machines; LangChain abstractions now built on top of LangGraph |
| Direct OpenAI SDK | LiteLLM for provider abstraction | 2023-2024 | Multi-provider support, fallback logic, unified interface; LiteLLM now standard for provider abstraction |
| Sync SQLAlchemy | SQLAlchemy 2.0 async | 2023 | Native async support eliminates need for sync wrappers; required for FastAPI async endpoints |
| Create React App | Vite | 2021-2023 | Vite much faster dev experience, better build optimization; CRA deprecated in 2023 |
| Flask for APIs | FastAPI for async APIs | 2019-2024 | FastAPI native async, automatic validation, OpenAPI docs; now default choice for Python APIs |
| String parsing of LLM outputs | Pydantic structured outputs | 2023-2024 | Providers now support response_format parameter; Pydantic validation standard |
| Thread-based concurrency | Async/await with asyncio | 2018-2024 | Python asyncio mature, FastAPI/SQLAlchemy have native async; thread overhead eliminated |
| Manual WebSocket scaling | Redis pub/sub for WebSockets | 2020-2024 | Multi-worker deployment requires Redis; standard pattern for production WebSocket |

**Deprecated/outdated:**
- **Flask-SocketIO for WebSockets:** Use FastAPI native WebSocket support
- **LangChain agent abstractions:** Use LangGraph for better control flow
- **Sync database drivers (psycopg2):** Use asyncpg for async PostgreSQL
- **OpenAI SDK without abstraction:** Use LiteLLM for provider flexibility
- **Create React App:** Use Vite for frontend tooling
- **Manual JSON parsing of LLM outputs:** Use Pydantic with response_format
- **Threading for concurrency:** Use asyncio for I/O-bound operations
- **Global Session objects in SQLAlchemy:** Use dependency injection for request-scoped sessions

**2026 emerging patterns:**
- **A2A (Agent-to-Agent) protocol:** LangGraph adding support for cross-framework agent communication
- **MCP (Model Context Protocol):** Standard for authorization in agent workflows
- **Pydantic AI:** New framework from Pydantic team for type-safe agent development
- **ARQ for asyncio:** Alternative to Celery for pure async task queues with FastAPI

## Open Questions

Things that couldn't be fully resolved:

1. **LangGraph Production Maturity**
   - What we know: Used by major companies (Replit, Uber, LinkedIn); 2026 major version planned with API stability
   - What's unclear: Breaking changes in major version; stability of current 0.2+ API
   - Recommendation: Monitor LangGraph GitHub for breaking changes during Phase 1 development; consider pinning version until major version releases

2. **Celery vs ARQ for FastAPI**
   - What we know: Celery more mature with better monitoring; ARQ native asyncio, simpler with FastAPI
   - What's unclear: ARQ production readiness for 5-15 teams; monitoring/observability compared to Celery
   - Recommendation: Start with Celery for Phase 1 (proven, mature); evaluate ARQ in Phase 2 if Celery integration friction high

3. **LiteLLM Latency at Scale**
   - What we know: 8ms P95 latency at 1k RPS; adds abstraction overhead
   - What's unclear: Latency impact at 5-15 concurrent teams with long-running agent workflows
   - Recommendation: Benchmark LiteLLM with expected load during Phase 1; measure end-to-end latency including LLM provider response time

4. **React 19 Compatibility**
   - What we know: React 19 may have released by now; TanStack Query supports React 18
   - What's unclear: Whether React 19 is stable for production; TanStack Query React 19 compatibility
   - Recommendation: Check React 19 release status; stick with React 18.x for Phase 1 if React 19 not production-ready

5. **Optimal JSONB Size Threshold**
   - What we know: PostgreSQL TOAST kicks in around 2KB; performance degrades with large JSONB
   - What's unclear: Exact threshold for agent proposals (varies by query pattern)
   - Recommendation: Monitor JSONB column sizes during development; split content if consistently >2KB

## Sources

### Primary (HIGH confidence)
- [LangGraph Overview - LangChain Docs](https://docs.langchain.com/oss/python/langgraph/overview) - Core concepts, human-in-the-loop patterns
- [LiteLLM Documentation](https://docs.litellm.ai/docs/) - Multi-provider abstraction, Router configuration, fallback patterns
- [SQLAlchemy 2.0 Async Documentation](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html) - AsyncSession lifecycle, eager loading patterns, preventing implicit I/O
- [FastAPI WebSocket Documentation](https://fastapi.tiangolo.com/advanced/websockets/) - Native WebSocket support, connection management
- [Pydantic for LLMs](https://pydantic.dev/articles/llm-intro) - Structured output validation, schema generation
- [FastAPI Bigger Applications](https://fastapi.tiangolo.com/tutorial/bigger-applications/) - Project structure, dependency injection
- [GitHub - BerriAI/litellm](https://github.com/BerriAI/litellm) - LiteLLM features, provider support

### Secondary (MEDIUM confidence)
- [LangGraph 2026 Updates](https://www.agentframeworkhub.com/blog/langgraph-news-updates-2026) - A2A/MCP support, 2026 roadmap (WebSearch verified with official roadmap)
- [FastAPI Best Practices GitHub](https://github.com/zhanymkanov/fastapi-best-practices) - Project structure, async patterns (community-vetted, 10k+ stars)
- [Building High-Performance Async APIs with FastAPI](https://leapcell.io/blog/building-high-performance-async-apis-with-fastapi-sqlalchemy-2-0-and-asyncpg) - SQLAlchemy async + asyncpg patterns (2026 article)
- [Celery 2026 Guide](https://www.programming-helper.com/tech/celery-2026-python-distributed-task-queue-redis-rabbitmq) - Celery 5.6, Redis vs RabbitMQ tradeoffs
- [Human-in-the-Loop Patterns](https://www.permit.io/blog/human-in-the-loop-for-ai-agents-best-practices-frameworks-use-cases-and-demo) - HITL approval workflows, frameworks
- [PostgreSQL JSONB Best Practices](https://www.architecture-weekly.com/p/postgresql-jsonb-powerful-storage) - Hybrid storage, indexing, TOAST considerations
- [TanStack Query Overview](https://tanstack.com/query/latest/docs/framework/react/overview) - React server state patterns, caching strategy
- [LLM Hallucination Detection 2026](https://arxiv.org/pdf/2601.09929) - Entity validation, hierarchical semantic approaches (arXiv paper)

### Tertiary (LOW confidence - needs validation)
- LangGraph version 0.2+ - Based on PyPI listing, exact current version unknown
- LiteLLM version 1.50+ - Based on 2025 documentation, exact current version unknown
- Celery version 5.4+ - Based on 2026 guide, verify against PyPI
- React 19 release status - Unclear if released and production-ready as of Feb 2026

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All core libraries verified with official docs; versions approximated but current as of early 2026
- Architecture patterns: HIGH - Patterns verified with official documentation (FastAPI, SQLAlchemy, LiteLLM); HITL patterns confirmed across multiple frameworks
- Pitfalls: HIGH - Based on official documentation warnings (SQLAlchemy implicit I/O, TOAST performance) and established patterns (hallucination validation, provider fallback)
- Code examples: HIGH - All examples sourced from official documentation or verified patterns

**Research date:** 2026-02-05
**Valid until:** 2026-05-05 (90 days - stack is stable, but LangGraph major version may change)

**Recommended validation before Phase 1 execution:**
1. Verify LangGraph current stable version and API stability (check GitHub releases)
2. Confirm LiteLLM Azure OpenAI integration quality (check recent GitHub issues)
3. Check if React 19 is production-ready (official React blog)
4. Validate Celery 5.6 current version (PyPI)
5. Review LangGraph human-in-the-loop examples (official docs)
