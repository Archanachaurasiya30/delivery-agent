# Architecture Research

**Domain:** AI-powered delivery management agent with web dashboard
**Researched:** 2026-02-05
**Confidence:** MEDIUM (based on training data and established patterns; WebSearch/WebFetch unavailable for verification)

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                          Web Dashboard (UI Layer)                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │  Sprint View │  │ Standup View │  │ Approval View │              │
│  └──────┬───────┘  └──────┬───────┘  └──────┬────────┘              │
│         │                  │                  │                       │
├─────────┴──────────────────┴──────────────────┴───────────────────────┤
│                         API Layer (REST/GraphQL)                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │
│  │ Sprint API   │  │ Standup API  │  │ Approval API │               │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘               │
│         │                  │                  │                       │
├─────────┴──────────────────┴──────────────────┴───────────────────────┤
│                      Orchestration Layer                              │
│  ┌────────────────────────────────────────────────────────────┐      │
│  │              Workflow Orchestrator                          │      │
│  │  (Manages: Proposal → Review → Approval → Execution)        │      │
│  └─────┬──────────────────────────────────────────────────────┘      │
│        │                                                              │
├────────┴──────────────────────────────────────────────────────────────┤
│                        Agent Layer                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │
│  │ Planning     │  │ Standup      │  │ Blocker      │               │
│  │ Agent        │  │ Agent        │  │ Router Agent │               │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘               │
│         │                  │                  │                       │
│         └──────────────────┴──────────────────┘                       │
│                            │                                          │
│                  ┌─────────┴──────────┐                              │
│                  │  Agent Framework    │                              │
│                  │  (LangGraph/CrewAI) │                              │
│                  └─────────┬──────────┘                              │
│                            │                                          │
├────────────────────────────┴──────────────────────────────────────────┤
│                      Domain Logic Layer                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │
│  │ Sprint       │  │ Capacity     │  │ Task         │               │
│  │ Service      │  │ Calculator   │  │ Analyzer     │               │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘               │
│         │                  │                  │                       │
├─────────┴──────────────────┴──────────────────┴───────────────────────┤
│                    Integration Layer (Pluggable)                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │
│  │ Task Provider│  │ Chat Provider│  │ Notification │               │
│  │ (Mock/ADO)   │  │ (Mock/Webex) │  │ Provider     │               │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘               │
│         │                  │                  │                       │
├─────────┴──────────────────┴──────────────────┴───────────────────────┤
│                         Data Layer                                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐            │
│  │ Sprints  │  │ Tasks    │  │ Approvals│  │ Standups │            │
│  │ Table    │  │ Table    │  │ Table    │  │ Table    │            │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘            │
└─────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| Web Dashboard | User interface for viewing proposals, giving approvals, viewing status | React/Vue SPA or server-rendered HTML (Flask templates, FastAPI + Jinja2) |
| API Layer | REST/GraphQL endpoints, request validation, response formatting | FastAPI or Flask with blueprints |
| Workflow Orchestrator | Manages proposal → review → approval → execution lifecycle | State machine (Python Enum + DB state) or workflow engine |
| Agent Layer | AI reasoning - sprint planning, standup coordination, blocker analysis | LangGraph (graph-based), CrewAI (multi-agent), or custom LLM orchestration |
| Domain Logic | Business logic for sprints, capacity, tasks - pure Python, no AI | Python classes/functions, domain models |
| Integration Layer | Pluggable adapters for external systems (mock vs real) | Abstract base classes with concrete implementations |
| Data Layer | Persistence for sprints, tasks, developers, approvals | SQLAlchemy ORM with PostgreSQL/SQLite |

## Recommended Project Structure

```
src/
├── api/                    # API Layer
│   ├── routes/             # Endpoint definitions
│   │   ├── sprints.py      # Sprint CRUD + proposals
│   │   ├── standups.py     # Standup endpoints
│   │   ├── approvals.py    # Approval workflow endpoints
│   │   └── tasks.py        # Task management
│   ├── schemas/            # Pydantic models for request/response
│   └── dependencies.py     # FastAPI dependencies
├── web/                    # Web Dashboard
│   ├── templates/          # Jinja2 templates (if server-rendered)
│   ├── static/             # CSS, JS, assets
│   └── views.py            # View controllers
├── agents/                 # Agent Layer
│   ├── base.py             # Base agent interface
│   ├── planning_agent.py   # Sprint planning logic
│   ├── standup_agent.py    # Standup coordination
│   ├── blocker_agent.py    # Blocker detection & routing
│   ├── release_agent.py    # Release management
│   └── orchestrator.py     # Multi-agent coordination (if using CrewAI pattern)
├── domain/                 # Domain Logic Layer
│   ├── models.py           # Core domain models (Sprint, Task, Developer, etc.)
│   ├── services/           # Business logic services
│   │   ├── sprint.py       # Sprint planning logic (non-AI)
│   │   ├── capacity.py     # Capacity calculation
│   │   ├── task.py         # Task analysis
│   │   └── blocker.py      # Blocker detection patterns
│   └── workflows.py        # Proposal → Approval state machine
├── integrations/           # Integration Layer (Pluggable)
│   ├── base.py             # Abstract interfaces
│   ├── task_provider/      # Task data source
│   │   ├── mock.py         # Manual entry (v1)
│   │   └── azure_devops.py # Azure DevOps API (v2)
│   ├── chat_provider/      # Communication
│   │   ├── mock.py         # Dashboard only (v1)
│   │   └── webex.py        # Webex integration (v2)
│   └── notification.py     # Notification abstraction
├── data/                   # Data Layer
│   ├── database.py         # DB connection setup
│   ├── models.py           # SQLAlchemy ORM models
│   └── repositories/       # Data access layer
│       ├── sprint.py       # Sprint CRUD
│       ├── task.py         # Task CRUD
│       └── approval.py     # Approval CRUD
├── scheduler/              # Scheduled Tasks
│   ├── jobs.py             # Background job definitions
│   └── triggers.py         # Cron-like scheduling (morning standups)
├── llm/                    # LLM Provider Abstraction
│   ├── base.py             # LLM provider interface
│   ├── openai.py           # OpenAI implementation
│   ├── anthropic.py        # Anthropic implementation
│   └── azure_openai.py     # Azure OpenAI implementation
└── config.py               # Configuration management

tests/
├── unit/                   # Unit tests per layer
├── integration/            # Integration tests
└── fixtures/               # Test data
```

### Structure Rationale

- **agents/ separate from domain/**: Agent layer contains AI reasoning; domain contains deterministic business logic. This separation allows testing domain logic without LLM calls.
- **integrations/ with base.py**: Abstract interfaces make swapping mock → real implementations trivial. Each provider type has its own subdirectory.
- **workflows.py in domain/**: Proposal → Approval workflow is domain logic, not agent logic. Agents produce proposals; workflow manages state transitions.
- **llm/ provider abstraction**: Centralizes LLM provider switching. Agents depend on the interface, not specific providers.
- **scheduler/ separate**: Background jobs (morning standups) need dedicated orchestration, separate from request-response API flow.

## Architectural Patterns

### Pattern 1: Single Coordinator Agent + Specialized Reasoners

**What:** One coordinator agent orchestrates multiple specialized reasoner agents. Each reasoner focuses on one domain (planning, standups, blockers). The coordinator routes requests and composes results.

**When to use:** When you have distinct workflows (sprint planning vs standup vs blocker routing) that share context but need different reasoning strategies.

**Trade-offs:**
- Pros: Clear separation of concerns, easier to test individual reasoners, can swap reasoners independently
- Cons: More complex orchestration logic, need to manage context passing between agents

**Example:**
```python
# agents/orchestrator.py
class DeliveryAgentOrchestrator:
    def __init__(self):
        self.planning_agent = PlanningAgent()
        self.standup_agent = StandupAgent()
        self.blocker_agent = BlockerAgent()

    async def handle_request(self, request_type: str, context: dict):
        if request_type == "plan_sprint":
            return await self.planning_agent.reason(context)
        elif request_type == "run_standup":
            return await self.standup_agent.reason(context)
        elif request_type == "analyze_blockers":
            return await self.blocker_agent.reason(context)

# agents/planning_agent.py
class PlanningAgent:
    def __init__(self, llm_provider: LLMProvider):
        self.llm = llm_provider
        self.tools = [capacity_calculator, task_analyzer]

    async def reason(self, context: dict) -> ProposedSprint:
        # AI reasoning to produce sprint proposal
        prompt = self._build_planning_prompt(context)
        result = await self.llm.generate(prompt, tools=self.tools)
        return ProposedSprint.parse(result)
```

**Recommended for this project:** YES. Distinct workflows (planning, standups, blockers) benefit from specialized agents.

### Pattern 2: Proposal → Review → Approval → Execution Workflow

**What:** Four-stage workflow for human-in-the-loop AI decisions. Agent produces a proposal (structured output), UI presents for human review, human approves/rejects, system executes on approval.

**When to use:** When AI should advise but humans must approve. Critical for trust and safety.

**Trade-offs:**
- Pros: Builds trust incrementally, prevents autonomous errors, clear audit trail
- Cons: Adds latency, requires UI for approval, need to handle rejection/retry

**Example:**
```python
# domain/workflows.py
class ProposalWorkflow:
    """Manages proposal lifecycle: draft → pending_review → approved → executed"""

    @staticmethod
    def create_proposal(agent_output: dict, proposal_type: str) -> Proposal:
        return Proposal(
            id=uuid4(),
            type=proposal_type,
            content=agent_output,
            status=ProposalStatus.DRAFT,
            created_at=datetime.utcnow()
        )

    @staticmethod
    def submit_for_review(proposal: Proposal) -> Proposal:
        proposal.status = ProposalStatus.PENDING_REVIEW
        proposal.submitted_at = datetime.utcnow()
        return proposal

    @staticmethod
    def approve(proposal: Proposal, approver: str) -> Proposal:
        proposal.status = ProposalStatus.APPROVED
        proposal.approver = approver
        proposal.approved_at = datetime.utcnow()
        return proposal

    @staticmethod
    def execute(proposal: Proposal, executor: Callable) -> Proposal:
        try:
            executor(proposal.content)
            proposal.status = ProposalStatus.EXECUTED
            proposal.executed_at = datetime.utcnow()
        except Exception as e:
            proposal.status = ProposalStatus.FAILED
            proposal.error = str(e)
        return proposal

# api/routes/approvals.py
@router.post("/proposals/{proposal_id}/approve")
async def approve_proposal(proposal_id: UUID, current_user: User):
    proposal = proposal_repo.get(proposal_id)

    # State validation
    if proposal.status != ProposalStatus.PENDING_REVIEW:
        raise HTTPException(400, "Proposal not in reviewable state")

    # Approval
    workflow = ProposalWorkflow()
    proposal = workflow.approve(proposal, current_user.email)
    proposal_repo.save(proposal)

    # Trigger execution (async task)
    background_tasks.add_task(execute_proposal, proposal_id)

    return {"status": "approved", "proposal": proposal}
```

**Recommended for this project:** YES. Requirement states "agent proposes, human approves."

### Pattern 3: Pluggable Integration Layer with Abstract Interfaces

**What:** Define abstract interfaces for external systems (TaskProvider, ChatProvider). Implement concrete classes for mock (v1) and real (v2). Domain and agent layers depend only on interfaces.

**When to use:** When you need to swap implementations (mock → real) or support multiple backends (OpenAI, Anthropic, Azure).

**Trade-offs:**
- Pros: Easy to test with mocks, zero code change to swap implementations, supports gradual migration
- Cons: More boilerplate, need dependency injection

**Example:**
```python
# integrations/base.py
from abc import ABC, abstractmethod
from typing import List, Optional

class TaskProvider(ABC):
    """Abstract interface for task data sources"""

    @abstractmethod
    async def get_tasks(self, sprint_id: Optional[str] = None) -> List[Task]:
        """Fetch tasks, optionally filtered by sprint"""
        pass

    @abstractmethod
    async def update_task_status(self, task_id: str, status: TaskStatus) -> Task:
        """Update task status"""
        pass

    @abstractmethod
    async def create_task(self, task: TaskCreate) -> Task:
        """Create new task"""
        pass

# integrations/task_provider/mock.py
class MockTaskProvider(TaskProvider):
    """Manual data entry via dashboard (v1)"""

    def __init__(self, db: Database):
        self.db = db

    async def get_tasks(self, sprint_id: Optional[str] = None) -> List[Task]:
        # Fetch from local database
        query = self.db.tasks.select()
        if sprint_id:
            query = query.where(Task.sprint_id == sprint_id)
        return await query.all()

    async def update_task_status(self, task_id: str, status: TaskStatus) -> Task:
        # Update in local database
        task = await self.db.tasks.get(task_id)
        task.status = status
        await self.db.tasks.save(task)
        return task

    async def create_task(self, task: TaskCreate) -> Task:
        # Insert into local database
        new_task = Task(**task.dict(), id=uuid4())
        await self.db.tasks.insert(new_task)
        return new_task

# integrations/task_provider/azure_devops.py
class AzureDevOpsTaskProvider(TaskProvider):
    """Azure DevOps API integration (v2)"""

    def __init__(self, org_url: str, project: str, pat: str):
        self.client = AzureDevOpsClient(org_url, project, pat)

    async def get_tasks(self, sprint_id: Optional[str] = None) -> List[Task]:
        # Fetch from Azure DevOps API
        work_items = await self.client.get_work_items(sprint=sprint_id)
        return [self._map_to_task(wi) for wi in work_items]

    async def update_task_status(self, task_id: str, status: TaskStatus) -> Task:
        # Update via Azure DevOps API
        await self.client.update_work_item(task_id, {"state": status.value})
        return await self.get_task(task_id)

    async def create_task(self, task: TaskCreate) -> Task:
        # Create via Azure DevOps API
        work_item = await self.client.create_work_item("Task", task.dict())
        return self._map_to_task(work_item)

# Dependency injection in main app
def get_task_provider(config: Config) -> TaskProvider:
    if config.TASK_PROVIDER == "mock":
        return MockTaskProvider(get_database())
    elif config.TASK_PROVIDER == "azure_devops":
        return AzureDevOpsTaskProvider(
            org_url=config.ADO_ORG_URL,
            project=config.ADO_PROJECT,
            pat=config.ADO_PAT
        )
    else:
        raise ValueError(f"Unknown task provider: {config.TASK_PROVIDER}")

# Agents depend on the interface, not the implementation
class PlanningAgent:
    def __init__(self, llm: LLMProvider, task_provider: TaskProvider):
        self.llm = llm
        self.tasks = task_provider  # Abstract interface

    async def reason(self, context: dict) -> ProposedSprint:
        backlog_tasks = await self.tasks.get_tasks(sprint_id=None)
        # AI reasoning...
```

**Recommended for this project:** YES. Critical for v1 (mock) → v2 (real) migration strategy.

### Pattern 4: Scheduled Jobs with Async Processing

**What:** Background job scheduler (APScheduler, Celery, or asyncio tasks) triggers recurring jobs (morning standups). Jobs enqueue async agent tasks.

**When to use:** When you need time-based triggers (daily standup at 9am) independent of user requests.

**Trade-offs:**
- Pros: Decouples scheduling from agent logic, can handle long-running tasks without blocking API
- Cons: Need task queue infrastructure, more complex deployment, need to handle job failures

**Example:**
```python
# scheduler/jobs.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

class SchedulerService:
    def __init__(self, standup_agent: StandupAgent):
        self.scheduler = AsyncIOScheduler()
        self.standup_agent = standup_agent

    def start(self):
        # Trigger morning standup at 9am weekdays
        self.scheduler.add_job(
            self.run_morning_standup,
            CronTrigger(hour=9, minute=0, day_of_week='mon-fri'),
            id='morning_standup'
        )
        self.scheduler.start()

    async def run_morning_standup(self):
        """Background job: Run morning standup"""
        try:
            # Enqueue standup task
            result = await self.standup_agent.initiate_standup()
            # Store result in database for dashboard display
            await standup_repo.save(result)
        except Exception as e:
            logger.error(f"Morning standup failed: {e}")
            # Could send alert to admin

# scheduler/triggers.py
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

def get_standup_trigger(config: ScheduleConfig) -> CronTrigger:
    """Configure standup schedule based on team preferences"""
    return CronTrigger(
        hour=config.STANDUP_HOUR,          # e.g., 9
        minute=config.STANDUP_MINUTE,      # e.g., 0
        day_of_week=config.STANDUP_DAYS,   # e.g., 'mon-fri'
        timezone=config.TEAM_TIMEZONE      # e.g., 'America/New_York'
    )

# main.py
async def startup():
    # Initialize scheduler
    scheduler = SchedulerService(
        standup_agent=get_standup_agent()
    )
    scheduler.start()
```

**Recommended for this project:** YES. Morning standups require scheduled triggers.

### Pattern 5: Agent State Management with Context Windows

**What:** Agents maintain conversation-like state across interactions. Use database to persist context (previous proposals, team history). LLM calls include relevant context from previous interactions.

**When to use:** When agent needs memory across requests (e.g., "Why did you propose this sprint structure?" should reference the actual proposal).

**Trade-offs:**
- Pros: More coherent agent behavior, can reference history, better explanations
- Cons: Context window management complexity, need to summarize or truncate old context

**Example:**
```python
# agents/base.py
from dataclasses import dataclass
from typing import List, Dict

@dataclass
class AgentContext:
    """Maintains agent conversation context"""
    session_id: str
    history: List[Dict[str, str]]  # [{"role": "user", "content": "..."}, ...]
    metadata: Dict[str, any]       # Sprint info, team info, etc.

    def add_message(self, role: str, content: str):
        self.history.append({"role": role, "content": content})

    def get_recent_context(self, max_messages: int = 10) -> List[Dict[str, str]]:
        """Get recent conversation history (avoid exceeding context window)"""
        return self.history[-max_messages:]

    def summarize_old_context(self) -> str:
        """Summarize older context to save tokens"""
        if len(self.history) <= 10:
            return ""
        old_messages = self.history[:-10]
        # Could use LLM to summarize, or simple extraction
        return f"Previous context summary: {len(old_messages)} messages about sprint planning..."

# agents/planning_agent.py
class PlanningAgent:
    async def reason(self, context: AgentContext) -> ProposedSprint:
        # Build prompt with context
        system_prompt = """You are a delivery planning agent.
        Your goal is to propose sprint contents based on capacity and backlog."""

        # Include recent conversation history
        messages = [
            {"role": "system", "content": system_prompt},
        ]

        # Add summarized old context if exists
        old_summary = context.summarize_old_context()
        if old_summary:
            messages.append({"role": "system", "content": old_summary})

        # Add recent conversation
        messages.extend(context.get_recent_context())

        # Add current request
        messages.append({
            "role": "user",
            "content": f"Plan a sprint with capacity: {context.metadata['capacity']}"
        })

        # LLM call with full context
        result = await self.llm.chat_completion(messages)

        # Store assistant response in context
        context.add_message("assistant", result.content)

        return ProposedSprint.parse(result.content)
```

**Recommended for this project:** MAYBE. Useful for conversational interactions ("Why did you propose X?"), but not critical for v1 if keeping workflows simple.

## Data Flow

### Request Flow: Sprint Planning

```
1. User clicks "Plan Sprint" in Dashboard
        ↓
2. API: POST /api/sprints/plan
        ↓
3. Sprint Planning Workflow initiated
        ↓
4. Fetch context:
   - Get backlog tasks (via TaskProvider interface)
   - Get team capacity (from database or manual input)
   - Get team history (recent sprints, velocity)
        ↓
5. Invoke Planning Agent
        ↓
6. Agent reasons with LLM:
   - Analyze tasks (complexity, dependencies)
   - Calculate capacity allocation
   - Propose sprint contents
        ↓
7. Agent returns ProposedSprint
        ↓
8. Create Proposal in database (status: DRAFT)
        ↓
9. Submit for review (status: PENDING_REVIEW)
        ↓
10. API returns proposal to frontend
        ↓
11. Dashboard displays proposal with "Approve" / "Reject" buttons
        ↓
12. User clicks "Approve"
        ↓
13. API: POST /api/proposals/{id}/approve
        ↓
14. Update proposal (status: APPROVED)
        ↓
15. Background job: Execute proposal
    - Create sprint in database
    - Update task assignments
    - Notify team (if notification provider enabled)
        ↓
16. Proposal status: EXECUTED
        ↓
17. Dashboard shows "Sprint created successfully"
```

### Request Flow: Morning Standup

```
1. Scheduler triggers job at 9am
        ↓
2. SchedulerService.run_morning_standup()
        ↓
3. Invoke Standup Agent
        ↓
4. Agent prepares standup for each developer:
   - Fetch assigned tasks (via TaskProvider)
   - Identify blockers (tasks with no recent progress)
   - Generate standup prompt per developer
        ↓
5. In v1 (mock): Store standup questions in database for dashboard display
   In v2 (Webex): Send standup questions via ChatProvider to each dev
        ↓
6. Developers respond (via dashboard in v1, via Webex in v2)
        ↓
7. Agent collects responses, generates team summary
        ↓
8. Summary stored in database
        ↓
9. Dashboard displays team standup summary
        ↓
10. If blockers detected:
    - Blocker Agent analyzes
    - Proposes routing (who can help)
    - Creates proposal for team lead approval
```

### State Management: Proposal Lifecycle

```
Agent produces output
        ↓
Workflow: Create proposal (status: DRAFT)
        ↓
Workflow: Submit for review (status: PENDING_REVIEW)
        ↓
    ┌───────────────────┐
    │  Human Decision   │
    └─────┬─────────┬───┘
          │         │
    Approve     Reject
          │         │
          ↓         ↓
      APPROVED   REJECTED
          │         │
    Execute   Modify & Resubmit
          │
          ↓
      EXECUTED
```

### Key Data Flows

1. **Agent Invocation Flow:** API → Orchestrator → Specialized Agent → LLM Provider → Agent → Orchestrator → API
2. **Approval Flow:** Dashboard → API → Workflow State Machine → Database → Background Executor → Dashboard notification
3. **Integration Flow:** Domain Logic → Integration Interface → Concrete Implementation (Mock or Real) → External System (if v2)

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 1-3 teams (5-15 devs) | Monolith is fine. Single web server, single database, in-process scheduling. Deploy as single Python process. |
| 4-20 teams (20-100 devs) | Separate API server from background job workers. Use Redis for task queue (Celery). Load balance API servers. Cache frequently accessed data (team info, sprint metadata). |
| 20+ teams (100+ devs) | Consider multi-tenancy isolation. Shard by team if needed. Extract agent layer as separate service with job queue. Use distributed tracing (OpenTelemetry). Monitor LLM token usage per team. Consider rate limiting per team. |

### Scaling Priorities

1. **First bottleneck:** LLM API latency. Each agent call takes 2-10 seconds. For many concurrent users, queue agent tasks and provide async responses. Don't block HTTP requests on LLM calls.

2. **Second bottleneck:** Database writes for proposals and task updates. Use read replicas for dashboard queries. Consider event sourcing for audit trail (all proposal state changes as events).

3. **Third bottleneck:** Scheduled job concurrency. If running standups for 20 teams simultaneously, need parallel job processing. Use Celery workers or asyncio task pool.

## Anti-Patterns

### Anti-Pattern 1: Tightly Coupling Agent Logic to LLM Provider

**What people do:** Import OpenAI SDK directly in agent code. Hardcode prompt templates for specific models.

**Why it's wrong:** Vendor lock-in. Can't switch to Anthropic or Azure OpenAI without rewriting agents. Different models require different prompting strategies.

**Do this instead:**
```python
# BAD: Direct OpenAI import in agent
from openai import AsyncOpenAI

class PlanningAgent:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    async def reason(self, context):
        response = await self.client.chat.completions.create(
            model="gpt-4",
            messages=[...]
        )

# GOOD: Abstract LLM provider
from llm.base import LLMProvider

class PlanningAgent:
    def __init__(self, llm_provider: LLMProvider):
        self.llm = llm_provider  # Can be OpenAI, Anthropic, Azure, etc.

    async def reason(self, context):
        response = await self.llm.generate(
            prompt=self._build_prompt(context),
            tools=self.tools
        )

# llm/base.py
class LLMProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str, tools: List[Tool] = None) -> str:
        pass

# Concrete implementations handle provider-specific details
class OpenAIProvider(LLMProvider):
    async def generate(self, prompt: str, tools: List[Tool] = None):
        # OpenAI-specific logic

class AnthropicProvider(LLMProvider):
    async def generate(self, prompt: str, tools: List[Tool] = None):
        # Anthropic-specific logic
```

### Anti-Pattern 2: Agent Makes Decisions Without Approval

**What people do:** Agent directly modifies sprint data, sends messages, or updates tasks without human review.

**Why it's wrong:** Violates trust boundary. Users lose confidence if agent makes mistakes autonomously. Hard to debug when things go wrong. No audit trail.

**Do this instead:**
- Always use Proposal → Approval workflow for consequential actions
- Agent outputs are proposals, not direct changes
- Human explicitly approves before execution
- Store all proposals and approvals in database for audit

### Anti-Pattern 3: Mixing Agent Logic with Domain Logic

**What people do:** Put business rules (capacity calculation, task dependency analysis) inside agent LLM prompts. Agent becomes responsible for both reasoning AND computation.

**Why it's wrong:** Can't test business logic without LLM calls. Expensive to iterate on rules. LLM might calculate incorrectly. Domain logic changes require prompt rewrites.

**Do this instead:**
```python
# BAD: Business logic in LLM prompt
prompt = f"""
Calculate sprint capacity:
Team members: {members}
Each member has 40 hours/week...
Subtract meetings, subtract PTO...
Then select tasks from backlog that fit...
"""

# GOOD: Business logic in deterministic code
class CapacityCalculator:
    def calculate_available_hours(self, members: List[Developer], sprint_duration_weeks: int) -> float:
        total_hours = 0
        for member in members:
            weekly_hours = member.hours_per_week or 40
            pto_hours = member.pto_hours_this_sprint or 0
            meeting_hours = member.recurring_meeting_hours or 8
            available_hours = (weekly_hours - meeting_hours) * sprint_duration_weeks - pto_hours
            total_hours += available_hours
        return total_hours

# Agent uses deterministic result
capacity_hours = capacity_calculator.calculate_available_hours(team, sprint_weeks)
prompt = f"""
Available capacity: {capacity_hours} hours
Backlog tasks: {tasks}
Propose which tasks to include in sprint.
"""
```

### Anti-Pattern 4: Synchronous API Calls to LLM

**What people do:** HTTP endpoint calls agent, agent calls LLM synchronously, HTTP response waits 5-10 seconds.

**Why it's wrong:** Poor UX (slow page loads), ties up web server workers, vulnerable to timeouts, can't handle concurrent requests well.

**Do this instead:**
- Return 202 Accepted immediately with proposal ID
- Enqueue agent task in background (Celery, asyncio)
- Poll for completion or use WebSocket for real-time updates
- Dashboard shows "Generating proposal..." with progress indicator

```python
# GOOD: Async with background task
@router.post("/sprints/plan")
async def plan_sprint(request: SprintPlanRequest, background_tasks: BackgroundTasks):
    # Create proposal in DRAFT state
    proposal = Proposal.create(type="sprint_plan", input=request.dict())
    proposal_repo.save(proposal)

    # Enqueue background task
    background_tasks.add_task(run_planning_agent, proposal.id)

    # Return immediately
    return {
        "proposal_id": proposal.id,
        "status": "processing",
        "message": "Sprint plan is being generated..."
    }

async def run_planning_agent(proposal_id: UUID):
    proposal = proposal_repo.get(proposal_id)
    try:
        result = await planning_agent.reason(proposal.input)
        proposal.content = result
        proposal.status = ProposalStatus.PENDING_REVIEW
    except Exception as e:
        proposal.status = ProposalStatus.FAILED
        proposal.error = str(e)
    proposal_repo.save(proposal)
```

### Anti-Pattern 5: No Observability in Agent Reasoning

**What people do:** Agent calls LLM, returns result, no logging of prompts/responses. When agent misbehaves, can't debug.

**Why it's wrong:** Can't understand why agent made a decision. Can't reproduce bugs. Can't measure token usage or latency. No audit trail for compliance.

**Do this instead:**
- Log all LLM prompts and responses
- Track token usage per request
- Store agent reasoning steps in database
- Provide "Explain this proposal" feature in UI that shows agent's reasoning

```python
# agents/planning_agent.py
class PlanningAgent:
    async def reason(self, context: dict) -> ProposedSprint:
        prompt = self._build_prompt(context)

        # Log prompt before LLM call
        logger.info(f"Planning agent prompt: {prompt[:500]}...")

        # Call LLM with tracing
        start_time = time.time()
        response = await self.llm.generate(prompt, tools=self.tools)
        elapsed = time.time() - start_time

        # Log response and metrics
        logger.info(f"Planning agent response in {elapsed:.2f}s: {response[:500]}...")

        # Store full trace in database for debugging
        await trace_repo.create(
            agent="planning",
            prompt=prompt,
            response=response,
            duration_seconds=elapsed,
            token_count=response.token_count,
            context=context
        )

        return ProposedSprint.parse(response)
```

## Integration Points

### External Services (v2)

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Azure DevOps | REST API via `azure-devops` Python SDK | Use PAT for authentication. Map Work Items to internal Task model. Webhook for real-time updates (optional). |
| Webex | REST API or Bot SDK | Register bot, use webhook for incoming messages. Send messages via Webex API. Handle rate limits. |
| LLM Providers | Provider-specific SDKs behind abstract interface | OpenAI SDK, Anthropic SDK, Azure OpenAI SDK. Implement retry logic and fallback. |
| Notification | Email (SMTP) or Slack webhooks | For alerts (blockers detected, approvals needed). Pluggable like other integrations. |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| API ↔ Agent | Direct function call (same process) or job queue (distributed) | For v1, direct call is fine. For scale, use Celery. |
| Agent ↔ Domain Logic | Direct function call | Agents import domain services. Keep agents thin (reasoning only). |
| Domain ↔ Integration | Dependency injection of interface | Domain calls `task_provider.get_tasks()`, doesn't know if mock or ADO. |
| API ↔ Data Layer | Repository pattern | API calls `sprint_repo.get()`, not direct SQLAlchemy queries. |
| Scheduler ↔ Agent | Job queue or direct async call | Scheduler enqueues agent tasks. Don't block scheduler thread. |

## Build Order Implications

**Phase 1: Core Data Model + Mock Integrations**
- Build: Database models, repositories, mock task provider, mock chat provider
- Rationale: Establish data structure and integration boundaries before AI complexity

**Phase 2: Domain Logic (No AI)**
- Build: Capacity calculator, task analyzer, sprint service, workflow state machine
- Rationale: Can test business rules without LLM. Validates domain model.

**Phase 3: Basic Agent + LLM Provider Abstraction**
- Build: LLM provider interface, OpenAI implementation, basic planning agent (single LLM call)
- Rationale: Proves AI integration works before building full workflows

**Phase 4: Proposal → Approval Workflow**
- Build: Proposal model, workflow state machine, approval API endpoints
- Rationale: Establishes human-in-the-loop pattern before complex agent features

**Phase 5: Dashboard + API**
- Build: Web UI for viewing proposals, approval buttons, basic task CRUD
- Rationale: Makes system usable. Can manually test agent proposals.

**Phase 6: Specialized Agents (Planning, Standup, Blocker)**
- Build: Full agent implementations with tools and context
- Rationale: Now have foundation (data, domain, workflow, UI) to build rich agent features

**Phase 7: Scheduler + Background Jobs**
- Build: APScheduler setup, morning standup job, async task handling
- Rationale: Depends on agent + workflow being stable. Adds automation.

**Phase 8: v2 Real Integrations (Azure DevOps, Webex)**
- Build: ADO task provider, Webex chat provider, webhook handlers
- Rationale: Swap implementations after v1 validates approach with mocks

## Sources

**Confidence Level: MEDIUM**

This research is based on:
- Training data on AI agent architectures (LangGraph, CrewAI patterns)
- Established Python web application patterns (FastAPI, SQLAlchemy)
- Human-in-the-loop workflow patterns from training
- Pluggable architecture patterns (Strategy pattern, Dependency Injection)

**Sources unavailable:**
- WebSearch unavailable (could not verify 2026 current practices)
- WebFetch unavailable (could not access LangGraph/CrewAI official docs)

**Recommendations:**
- Verify LangGraph/CrewAI documentation for latest patterns
- Cross-check multi-agent coordination approaches with recent blog posts
- Validate LLM provider abstraction against current SDK APIs
- Review Azure DevOps + Webex integration docs during Phase 8

---
*Architecture research for: AI-powered delivery management agent*
*Researched: 2026-02-05*
