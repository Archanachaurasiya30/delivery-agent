# Project Research Summary

**Project:** AI-Powered Delivery Management Agent
**Domain:** AI-powered delivery/project management for development teams
**Researched:** 2026-02-05
**Confidence:** MEDIUM

## Executive Summary

This project is an AI-powered delivery management agent designed to automate and improve sprint planning, daily standups, and blocker management for development teams (5-15 teams, on-premises deployment). The research reveals that successful systems in this domain follow a "agent proposes, human approves" pattern rather than full autonomy — critical for building trust and preventing AI errors from disrupting delivery processes.

The recommended approach uses Python-based AI orchestration (LangGraph for state-managed workflows) with a FastAPI backend serving a React dashboard. The architecture must support pluggable integrations, starting with mock data sources (v1) before connecting to real systems like Azure DevOps and Webex (v2). This phased integration strategy reduces risk and allows validating the AI approach before committing to complex external API integrations.

The primary risks are: (1) LLM hallucination generating proposals with invalid data, (2) synchronous blocking making the UI unresponsive during agent processing, and (3) tight coupling to single LLM provider creating single point of failure. All three must be addressed in Phase 1 architecture decisions — they cannot be retrofitted later without major rewrites. Success depends on building validation layers, async infrastructure, and provider abstraction from day one.

## Key Findings

### Recommended Stack

The research strongly recommends a modern Python stack optimized for AI agents with async capabilities. The core insight is avoiding heavyweight frameworks (Django, full LangChain orchestration) in favor of purpose-built tools that match the specific use case: a single agent with multiple capabilities, not a multi-agent system.

**Core technologies:**
- **LangGraph (0.2+)**: AI agent orchestration — state machine approach fits the "standup → analyze → escalate" workflow better than role-based multi-agent frameworks like CrewAI
- **FastAPI (0.115+)**: Backend API and dashboard server — async support critical for non-blocking LLM calls, automatic OpenAPI docs simplify frontend integration
- **LiteLLM (1.50+)**: Multi-provider LLM abstraction — single interface for OpenAI, Anthropic, Azure OpenAI prevents vendor lock-in and enables fallback strategies
- **React (18.x) + Vite (6.x)**: Dashboard UI — industry standard with mature ecosystem for complex interactive UIs and real-time updates
- **PostgreSQL (16+)**: Primary database — JSONB for flexible LLM output storage while maintaining relational integrity for sprints/tasks
- **Celery (5.4+) + Redis (7.2+)**: Background job processing — scheduled standups and async agent tasks require robust job queue

**Critical stack decisions:**
- SQLAlchemy 2.0+ with async support (not Django ORM which is sync)
- TanStack Query for frontend server state management (handles real-time agent updates)
- APScheduler for cron-like standup scheduling
- Pydantic 2.x for type-safe request/response validation (integrates with FastAPI)

**What NOT to use:**
- LangChain for orchestration (use LangGraph instead — clearer control flow)
- OpenAI SDK directly (use LiteLLM for provider abstraction)
- Create React App (deprecated — use Vite)
- Flask-SocketIO (use FastAPI's native WebSocket support)

### Expected Features

The feature landscape divides into three categories: table stakes (users expect these from any PM tool), differentiators (AI-powered features that set this apart), and anti-features (commonly requested but problematic).

**Must have (table stakes):**
- Task/issue tracking with status workflow (Backlog → In Progress → Done)
- Sprint/cycle planning with capacity tracking and velocity metrics
- Board views (Kanban/List) for task visualization
- Team member management with roles and permissions
- Comments/discussion with @mentions
- Filters and search functionality
- Sprint burndown charts and retrospectives

**Should have (competitive advantage):**
- Intelligent sprint proposals — agent analyzes backlog + capacity, suggests sprint composition
- Automated standup collection — agent asks team members asynchronously, compiles summaries
- Blocker detection and routing — identifies stuck work, suggests who should unblock
- Approval workflows — clear UI for reviewing and approving AI proposals (core differentiator)
- Release readiness assessment — "here's what's blocking release" analysis
- Predictive sprint completion warnings — early risk detection based on velocity

**Defer (v2+):**
- Alternative sprint scenarios (3 options: aggressive/balanced/conservative) — complex, unclear if needed
- Technical debt tracking from TODO comments — nice-to-have, not core
- Team health metrics (burnout indicators) — sensitive, needs established trust first
- Dependency detection — hard to get right, often wrong
- CI/CD status integration — valuable but integration complexity deferred

**Anti-features to explicitly avoid:**
- Fully autonomous sprints without approval (kills team ownership)
- Auto-assignment of all tasks (creates resentment)
- Real-time notifications for everything (notification fatigue)
- Built-in time tracking/wikis/chat (feature bloat, duplicates existing tools)
- Developer leaderboards (toxic competition)

### Architecture Approach

The architecture follows a five-layer pattern with clear separation between AI reasoning and deterministic business logic. This separation is critical for testing and maintaining the system as agent capabilities evolve.

**Major components:**

1. **Agent Layer (LangGraph orchestration)** — AI reasoning for sprint planning, standup coordination, and blocker analysis. Uses specialized agents (PlanningAgent, StandupAgent, BlockerAgent) coordinated by a central orchestrator. Agents consume context and produce structured proposals, never direct database changes.

2. **Domain Logic Layer (pure Python)** — Deterministic business rules for capacity calculation, task analysis, sprint management. This layer has zero LLM dependencies and can be tested without AI calls. Agents call domain services for computation, then use LLM only for reasoning about results.

3. **Integration Layer (pluggable adapters)** — Abstract interfaces (TaskProvider, ChatProvider, NotificationProvider) with concrete implementations for mock (v1) and real systems (v2). This enables testing with simple mocks while designing for real API complexity (pagination, rate limits, auth expiry).

4. **Proposal → Approval Workflow** — State machine managing proposal lifecycle: DRAFT → PENDING_REVIEW → APPROVED → EXECUTED. All consequential agent actions go through this workflow. Human approval is required before execution, with explicit approve/reject buttons and full audit trail.

5. **Scheduled Job Processing** — Background scheduler (APScheduler/Celery) triggers time-based jobs (morning standups at 9am). Jobs enqueue async agent tasks that don't block the API server. Critical for delivering standups on schedule without manual triggers.

**Key architectural patterns:**
- Single coordinator agent + specialized reasoners (not multi-agent role-playing)
- Async-first design (all LLM calls are background jobs, API returns 202 Accepted immediately)
- Provider abstraction (LLM, TaskProvider, ChatProvider all behind interfaces)
- Context management with memory persistence (decisions stored separately from conversation history)

**Data flow example (Sprint Planning):**
User clicks "Plan Sprint" → API queues background task → Agent fetches backlog, capacity, history → Agent calls LLM with context → Agent produces ProposedSprint → Workflow creates Proposal (PENDING_REVIEW) → Dashboard displays with Approve/Reject buttons → Human approves → Background job executes (creates sprint, updates tasks) → Dashboard shows "Sprint created"

### Critical Pitfalls

The research identified 8 critical pitfalls that must be addressed in Phase 1 architecture or they become impossible to fix later. These are not "nice to have" improvements — they are foundational requirements.

1. **Hallucinated Proposal Data** — Agent generates proposals with non-existent team members, invalid dates, or already-completed features. Prevention: Structured output schemas with validation, two-phase generation (agent creates template, system fills actual data), explicit context injection. Validate all entity references against database before storing proposals.

2. **Context Window Amnesia** — Agent forgets critical decisions made earlier in conversation or between sessions. Prevention: Separate database for "decisions made" always injected into context, structured constraints file loaded into every agent call, session summaries stored separately. Design memory architecture from start — retrofitting is extremely difficult.

3. **Synchronous Agent Blocking UI** — API waits 30-90 seconds for LLM response, UI hangs, users spam-click triggering multiple expensive calls. Prevention: Async by default (all agent calls are background jobs), optimistic UI ("Generating proposal..."), request queuing to limit concurrent LLM calls. Cannot convert sync to async later without major rewrite.

4. **No LLM Provider Fallback** — OpenAI outage makes entire system unusable despite infrastructure being fine. Prevention: Provider abstraction layer, circuit breaker pattern for automatic fallback, cached proposals for reuse when provider down, manual mode for creating proposals without agent. Refactoring tight coupling is expensive — build abstraction from start.

5. **Agent Authority Ambiguity** — Users can't tell what agent decided autonomously vs. what needs approval. Prevention: Action taxonomy documenting autonomous vs. approval-required, visual UI indicators (Approved ✓ vs Pending ⏳ vs Suggestion 💡), explicit approve/reject buttons not just "OK", full audit trail with "proposed by agent, approved by [user]".

6. **Mock Integration Divergence** — v1 mocks are too simple, v2 real APIs have pagination/rate limits/auth expiry that break in production. Prevention: Contract testing to verify mocks match real API, integration tests against real API staging even in v1, mock from recorded traffic (VCR pattern), fail-fast mocks that simulate timeouts and errors.

7. **Over-Confident Recommendations** — Agent states "This is optimal" with high confidence but based on incomplete information, teams follow blindly, trust collapses after wrong recommendations. Prevention: Confidence scoring, reasoning transparency ("I used X data, I don't know Y"), alternative proposals showing tradeoffs, clarifying questions before recommendation, uncertainty prompts in system instructions.

8. **No Audit Trail for Agent Decisions** — Three months later, can't reconstruct why decision was made, can't debug wrong recommendations, compliance issues. Prevention: Full prompt logging, structured reasoning capture, version tracking (model version, timestamp, context state), JSON logs for querying, retention policy. Infrastructure must exist from start or historical data is lost forever.

**Additional high-risk patterns:**
- Loading full project history into context (breaks at ~100 tickets) — summarize old, include recent only
- No caching of agent responses (expensive at ~50 proposals/day) — cache similar inputs with TTL
- Including sensitive data in LLM prompts (sent to external provider) — redact PII, secrets, financial data
- No rate limiting on agent usage (cost explosion) — per-user limits, cost budgets, unusual usage alerts

## Implications for Roadmap

Based on combined research, the roadmap should follow dependency-driven phases that establish foundational patterns before adding complexity. The architecture demands certain decisions early (async, validation, abstraction) that cannot be changed without rewrites.

### Phase 1: Foundation + Core Agent (Mocked Data)
**Rationale:** Must establish async infrastructure, validation layers, and provider abstraction before building features. These are architectural decisions, not features — getting them wrong means Phase 2+ will fail or require rewrites.

**Delivers:**
- Database models (sprints, tasks, developers, proposals) with SQLAlchemy async
- Mock integrations (MockTaskProvider, MockChatProvider) implementing abstract interfaces
- Domain logic services (capacity calculator, task analyzer) — pure Python, no LLM
- LLM provider abstraction (OpenAIProvider, AnthropicProvider behind interface)
- Proposal → Approval workflow state machine (DRAFT → PENDING_REVIEW → APPROVED → EXECUTED)
- Basic Planning Agent with structured output validation
- Async background job infrastructure (Celery + Redis or APScheduler)
- Simple web dashboard (FastAPI + React) for viewing/approving proposals

**Addresses features:**
- Basic task management (CRUD)
- Sprint planning with manual data entry
- Approval workflow (core differentiator)
- AI sprint proposals (basic version — suggest N tasks for sprint)

**Avoids pitfalls:**
- Hallucinated data (validation layer catches invalid references)
- Synchronous blocking (async infrastructure from start)
- No LLM fallback (provider abstraction enables multiple providers)
- No audit trail (full prompt/response logging built in)
- Mock divergence (abstract interfaces designed for real API complexity)

**Success criteria:**
- Agent proposes sprint, user approves, system executes — all async
- Generate 100 proposals, manually verify all entity references valid
- Kill LLM provider connection mid-request, verify graceful degradation
- Multi-turn conversation: mention constraint early, verify respected 20 messages later

### Phase 2: Automated Standups + Blocker Detection
**Rationale:** Standups are the second core differentiator after sprint planning. Blocker detection naturally follows from standup data. Both features validate the agent value proposition before investing in complex external integrations.

**Delivers:**
- Standup Agent that asks team members for updates (via dashboard in v1)
- Scheduled job (9am weekdays) triggering standup collection
- Standup response collection and team summary generation
- Blocker detection from standup text ("blocked by X") and task staleness
- Blocker routing suggestions (who can help) requiring approval
- Dashboard views for standup summaries and active blockers

**Addresses features:**
- Automated daily standups (differentiator)
- Blocker detection and routing (differentiator)
- Scheduled job processing (table stakes)

**Avoids pitfalls:**
- Context amnesia (standups store decisions/blockers in memory database)
- Over-confident recommendations (blocker routing includes confidence scores)
- Notification fatigue (daily digest, not per-event notifications)

**Dependencies:**
- Requires Phase 1 async infrastructure (standups can take 30+ seconds)
- Requires Phase 1 approval workflow (blocker routing needs approval)
- Requires Phase 1 scheduler (cron-like standup triggers)

### Phase 3: Enhanced Sprint Intelligence
**Rationale:** Now that basic sprint planning and standups work, add intelligence that requires historical data. Velocity predictions need 2-3 sprints of history to be useful.

**Delivers:**
- Velocity-based sprint capacity predictions
- Sprint risk assessment (flags risky sprints before start)
- Historical trend analysis for capacity planning
- Sprint completion predictions ("at risk of not finishing")
- Board view (Kanban) for visual task management
- Enhanced filters and search

**Addresses features:**
- Velocity tracking (table stakes)
- Predictive sprint completion (differentiator)
- Sprint risk assessment (differentiator)
- Board views (table stakes)

**Dependencies:**
- Requires Phase 1 + 2 running for 2-3 sprints (need historical data)
- Requires stable sprint planning workflow (build intelligence on top)

### Phase 4: Real Integrations (Azure DevOps + Webex)
**Rationale:** Defer complex integrations until v1 validates the agent approach with mocks. Real APIs introduce rate limits, auth expiry, pagination that would slow early development. Phase 1-3 prove the concept, Phase 4 makes it production-ready.

**Delivers:**
- AzureDevOpsTaskProvider replacing MockTaskProvider
- WebexChatProvider replacing MockChatProvider
- Webhook handlers for real-time updates from Azure DevOps
- OAuth/PAT authentication for external services
- Rate limiting and retry logic for external APIs
- Integration health monitoring and circuit breakers

**Addresses features:**
- Git integration (link PRs to tasks)
- Slack/Teams integration (Webex in this case)
- Real-time notifications via Webex

**Avoids pitfalls:**
- Mock divergence (interface already designed for real API complexity)
- Integration rate limits (circuit breaker and retry logic built in)
- Auth token expiry (token refresh flow implemented)

**Dependencies:**
- Requires Phase 1-3 stable (integration swaps should be config change, not rewrite)
- Integration tests against Azure DevOps staging and Webex sandbox

### Phase 5: Release Management + Advanced Features
**Rationale:** Release features require Git integration from Phase 4. Advanced features (technical debt, team health) deferred until product-market fit established.

**Delivers:**
- Automated changelog generation from commits and PRs
- Release readiness checks (what's blocking release)
- Stakeholder communication summaries
- Modification interface (edit AI proposals inline before approving)
- Rejection with feedback ("No because Y" → agent learns)

**Addresses features:**
- Automated changelog (differentiator)
- Release readiness assessment (differentiator)
- Modification of proposals (table stakes for mature workflow)

**Future consideration (v2+ post-PMF):**
- Alternative sprint scenarios
- Technical debt tracking
- Team health metrics
- Dependency detection

### Phase Ordering Rationale

**Why Foundation first (Phase 1):**
Architecture patterns (async, validation, abstraction) are foundational decisions. Building features first with synchronous architecture means Phase 2+ requires rewrites. Based on PITFALLS.md, async-to-sync conversion is "HIGH recovery cost" — a major architecture change.

**Why Standups before Intelligence (Phase 2 before 3):**
Standups validate agent value proposition quickly (immediate feedback vs. waiting for sprint data). Blocker detection from standups creates fast feedback loop. Intelligence features need historical data anyway — Phase 3 can run while Phase 1-2 collect sprint history.

**Why Real Integrations deferred (Phase 4):**
PITFALLS.md warns of "mock divergence" but recommends it's "acceptable if contract tests in place + plan to test real API soon." Mocks let teams validate agent approach faster. Real APIs introduce rate limits, auth complexity, webhook management that slow development. Phase 1-3 with mocks proves concept, Phase 4 makes production-ready.

**Why Release Management last (Phase 5):**
Requires Git integration (Phase 4). Less critical for MVP than sprint planning and standups. Advanced features deferred until established product-market fit and user trust.

### Research Flags

**Phases likely needing deeper research during planning:**

- **Phase 1:** LangGraph workflow patterns (verify latest docs for state management, checkpointing, error recovery), LiteLLM Azure OpenAI support quality (confirm streaming and function calling work), FastAPI WebSocket scaling (may need Redis adapter for multi-process)

- **Phase 4:** Azure DevOps API pagination and rate limits (official docs for Work Items API), Webex Bot SDK capabilities (verify async message handling), webhook reliability and retry strategies

**Phases with standard patterns (skip research-phase):**

- **Phase 2:** Cron scheduling is well-documented (APScheduler or Celery Beat standard patterns), standup workflows follow established agent patterns from Phase 1

- **Phase 3:** Velocity calculations are deterministic math (no new patterns), dashboard enhancements use established React patterns

- **Phase 5:** Changelog generation from Git is well-documented problem (similar to release-please, semantic-release patterns)

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM | FastAPI/React/PostgreSQL recommendations HIGH confidence (verified FastAPI docs). LangGraph/LiteLLM versions MEDIUM confidence (unable to verify current releases via external sources). Ecosystem solid but need to validate latest versions. |
| Features | MEDIUM | Table stakes features HIGH confidence (standard PM tool expectations). AI differentiators MEDIUM confidence (based on training knowledge of AI tools, not verified with 2026 products). Anti-features based on established UX patterns. |
| Architecture | MEDIUM | Core patterns HIGH confidence (proposal workflow, async jobs, pluggable integrations are established). LangGraph-specific patterns MEDIUM confidence (unable to verify latest framework docs). Phase ordering based on solid dependency analysis. |
| Pitfalls | HIGH | Critical pitfalls (hallucination, sync blocking, provider lock-in) are well-documented in LLM agent literature. Phase-to-pitfall mapping based on established "cannot retrofit async" and "audit data lost forever" principles. Recovery cost assessments sound. |

**Overall confidence:** MEDIUM

### Gaps to Address

Research conducted with limited external verification (WebSearch/WebFetch unavailable). Key gaps requiring validation during implementation:

**Stack gaps:**
- **Current versions:** All version numbers approximate based on training data through January 2025. Validate against PyPI, npm for latest stable releases before installation.
- **LangGraph maturity:** Verify LangGraph 0.2+ stable for production use. Check GitHub issues for blocking bugs or API instability.
- **LiteLLM Azure OpenAI support:** Confirm current integration quality for authentication, streaming, function calling with Azure OpenAI specifically.
- **React 19:** React 19 may have released by now. Check stability and TanStack Query compatibility.

**Features gaps:**
- **Current competitor features:** Linear, Jira automation capabilities as of 2026 unknown. Validate table stakes haven't expanded since January 2025.
- **AI PM tools state:** Stepsize, Sweep, other AI-native tools may have matured. Check current feature sets to ensure differentiators still differentiate.
- **User research:** Feature prioritization based on training knowledge, not user interviews. Validate with dev team leads during Phase 1.

**Architecture gaps:**
- **LangGraph coordination patterns:** Unable to access official LangGraph docs. Verify multi-agent coordination best practices during Phase 1 planning.
- **FastAPI WebSocket scaling:** Confirm best practices for scaling WebSockets in production (may need Redis adapter or sticky sessions).

**Integration gaps:**
- **Azure DevOps API changes:** API may have changed post-January 2025. Review official Work Items API docs in Phase 4 planning.
- **Webex Bot capabilities:** Unable to verify current Webex Bot SDK. Check async message handling, webhook reliability during Phase 4.

**How to handle gaps:**
- Phase 1 planning: Allocate 1-2 days for stack verification (install latest versions, check compatibility)
- Use `/gsd:research-phase` for Phase 1 (LangGraph patterns) and Phase 4 (Azure DevOps/Webex APIs)
- Consider spike tasks in Phase 1 to validate async infrastructure, LLM provider abstraction, and mock integration patterns before full implementation
- User research sprint before Phase 1: Interview 2-3 dev team leads to validate feature prioritization

## Sources

### Primary (HIGH confidence)
- FastAPI Documentation (https://fastapi.tiangolo.com) — verified Feb 2026, confirms async capabilities, WebSocket support, Pydantic integration
- System Python verification — Python 3.12.4 available, confirms runtime compatibility
- Established architectural patterns — Proposal workflow, async jobs, pluggable integrations are language-agnostic patterns with decades of precedent

### Secondary (MEDIUM confidence)
- Training knowledge through January 2025 — LangGraph, LiteLLM, CrewAI patterns; Linear, Jira feature sets; Python ecosystem (SQLAlchemy, Celery, React)
- General knowledge of AI agent pitfalls — hallucination, context amnesia, sync blocking well-documented in AI engineering literature
- Domain patterns for delivery management — sprint planning, standup workflows, blocker escalation based on PM tool conventions

### Tertiary (LOW confidence, needs validation)
- Specific version numbers — LangGraph 0.2+, LiteLLM 1.50+, Celery 5.4+ approximate based on training data
- Current state of AI PM tools — Stepsize, Sweep capabilities as of 2026 unknown
- Azure DevOps and Webex API details — integration patterns need verification against current official documentation

### Recommended validation
Before roadmap finalization:
1. Verify LangGraph 0.2+ documentation for state management patterns
2. Check LiteLLM current Azure OpenAI integration quality (GitHub issues, recent commits)
3. Validate Linear/Jira current automation capabilities (official product pages)
4. Review Azure DevOps Work Items API and Webex Bot SDK official docs
5. User interviews with 2-3 dev team leads to confirm feature prioritization

---
*Research completed: 2026-02-05*
*Ready for roadmap: yes*
