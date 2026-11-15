# Pitfalls Research

**Domain:** AI-Powered Delivery Management Agent
**Researched:** 2026-02-05
**Confidence:** MEDIUM (based on training knowledge + project context, WebSearch unavailable)

---

## Critical Pitfalls

### Pitfall 1: Hallucinated Proposal Data

**What goes wrong:**
Agent generates delivery proposals with plausible-sounding but factually incorrect information: non-existent team members assigned to tasks, dates that don't account for holidays/weekends, dependencies that don't exist, or features already completed being proposed again.

**Why it happens:**
LLMs are trained to generate coherent text, not accurate database queries. Without grounding in actual project state, the agent fills gaps with plausible but wrong data. Particularly dangerous in delivery management where incorrect assignments waste time or create team confusion.

**How to avoid:**
- **Structured output validation:** Parse agent responses into schemas, validate all entity references against actual data
- **Two-phase generation:** Agent generates proposal template, system fills in actual data from database
- **Explicit context injection:** Prefix every prompt with current project state (teams, dates, completed work)
- **Confidence scores:** Agent marks which parts of proposal are inferred vs. factual

**Warning signs:**
- Proposals reference people who left the company months ago
- Dates fall on weekends or known holidays
- Feature dependencies contradict actual code structure
- Same proposals generated despite changed project state

**Phase to address:**
Phase 1 (Core Agent) - Build validation layer between agent output and proposal storage. Never trust raw agent output.

---

### Pitfall 2: Context Window Amnesia

**What goes wrong:**
Agent "forgets" critical decisions made earlier in the conversation. Team lead approves a 3-sprint plan, agent later proposes conflicting timeline ignoring that approval. Or agent loses track of project constraints mentioned 10 messages ago, making recommendations that violate those constraints.

**Why it happens:**
LLM context windows are finite. Even with 100k+ token windows, summarization or truncation happens. Critical project constraints get dropped while preserving conversational fluff. Stateless agent calls lose all context between sessions.

**How to avoid:**
- **Explicit memory store:** Separate database for "decisions made" that's always injected into context
- **Structured constraints file:** Project constraints documented in structured format (JSON/YAML), loaded into every agent call
- **Session summaries:** End each session by having agent summarize decisions/constraints, store separately
- **Context prioritization:** Keep constraints and decisions in context, drop conversational niceties first

**Warning signs:**
- Agent proposes dates that contradict earlier agreed deadline
- Recommendations ignore constraints mentioned previously ("we can't use AWS")
- Agent asks for information already provided in same conversation
- Proposals become inconsistent across conversation

**Phase to address:**
Phase 1 (Core Agent) - Design memory architecture from start. Retrofitting memory is extremely difficult.

---

### Pitfall 3: Synchronous Agent Blocking UI

**What goes wrong:**
User clicks "Generate Proposal", UI hangs for 30-90 seconds while agent thinks. UI becomes unresponsive. Users spam-click the button, triggering multiple expensive LLM calls. On-prem deployment with slower hardware makes this worse.

**Why it happens:**
LLM calls take seconds to minutes. Developers default to synchronous request-response pattern from traditional APIs. With 5-15 teams using the system, concurrent agent calls pile up, degrading performance for everyone.

**How to avoid:**
- **Async by default:** All agent calls are background jobs from day 1
- **Optimistic UI updates:** Show "Generating proposal..." with spinner immediately
- **Streaming responses:** Stream partial results as agent generates (if provider supports)
- **Request queuing:** Cap concurrent LLM calls, queue excess requests
- **Timeout and fallback:** Hard timeout on agent calls (e.g., 60s), show partial results or error

**Warning signs:**
- Users complain UI "feels slow"
- Backend logs show 30s+ response times
- Multiple identical requests from same user (spam clicking)
- System resource usage spikes block other operations

**Phase to address:**
Phase 1 (Core Agent) - Architecture decision. Cannot easily convert sync to async later.

---

### Pitfall 4: No LLM Provider Fallback

**What goes wrong:**
OpenAI (or chosen provider) has outage or rate limiting. Entire delivery management system becomes unusable. Teams can't create proposals, can't get recommendations, system is effectively down even though your infrastructure is fine.

**Why it happens:**
Tight coupling to single provider API. No degraded mode. System assumes LLM is always available. On-prem deployment means you can't just "upgrade to enterprise tier" for better reliability.

**How to avoid:**
- **Provider abstraction layer:** Interface that multiple LLM providers can implement (OpenAI, Anthropic, local model)
- **Circuit breaker pattern:** Detect provider failure, automatically fallback to secondary or cached responses
- **Cached proposals:** Store recently generated proposals, reuse similar when provider down
- **Manual mode:** UI allows creating proposals manually when agent unavailable
- **Health checks:** Proactive monitoring of provider API, warn users before they try to use agent

**Warning signs:**
- Single provider API client used throughout codebase
- No error handling for LLM timeout/failure
- No manual workflow as backup
- Tests mock LLM but never test actual provider failures

**Phase to address:**
Phase 1 (Core Agent) - Build abstraction layer from start. Refactoring tight coupling later is expensive.

---

### Pitfall 5: Agent Authority Ambiguity

**What goes wrong:**
Users can't tell what the agent decided autonomously vs. what it's suggesting for approval. Agent generates proposal with "Proposed deadline: March 15", user thinks it's a suggestion but system already blocked calendar. Or vice versa: user thinks agent has taken action but it's waiting for approval.

**Why it happens:**
"Agent proposes, human approves" sounds clear but gets blurry in implementation. Some actions are safe to automate (data lookup), others need approval (deadline changes). Without clear UI distinction, users either distrust everything or trust too much.

**How to avoid:**
- **Action taxonomy:** Document which actions are autonomous vs. requiring approval
- **Visual distinction:** Clear UI indicators (e.g., "Approved ✓" vs "Pending Review ⏳" vs "Agent Suggestion 💡")
- **Approval workflows:** Explicit approve/reject buttons, not just "OK"
- **Audit trail:** Every agent action logged with "proposed by agent, approved by [user]" or "autonomous action"
- **Progressive trust:** Start with all actions requiring approval, enable auto-approval per-team as trust builds

**Warning signs:**
- Users ask "did the agent already do this or is it asking me?"
- Confusion about whether deadline is set or proposed
- Approval workflows inconsistent across actions
- No way to see what agent did vs. what's pending

**Phase to address:**
Phase 1 (Core Agent) - Design trust model early. Influences all UX decisions.

---

### Pitfall 6: Mock Integration Divergence

**What goes wrong:**
v1 mocks Jira/GitHub/etc with simple stubs. v2 integrates real APIs. Real APIs have pagination, rate limits, auth expiry, partial failures that mocks didn't simulate. Code breaks in production because mocks were too simple.

**Why it happens:**
Mocks start simple ("just return static data"), diverge from real API behavior over time. No forcing function to keep mocks accurate. Real APIs are complex (webhooks, eventual consistency, partial errors) and developers don't anticipate this in mocks.

**How to avoid:**
- **Contract testing:** Use tools like Pact to verify mocks match real API contracts
- **Real API in tests:** Even in v1, run integration tests against real API staging/sandbox
- **Mock from recorded traffic:** Record real API responses, replay in mocks (VCR pattern)
- **Fail-fast mocks:** Mocks intentionally include failure modes (timeouts, 429s, partial data)
- **Interface-first design:** Define integration interface based on real API docs, implement mocks and real clients against same interface

**Warning signs:**
- Mocks never fail or timeout
- Mocks return perfectly structured data always
- No pagination in mock responses
- Test suite only uses mocks, never real staging APIs
- Integration interface designed around mock capabilities not real API

**Phase to address:**
Phase 1 (Mocked Integrations) - Design integration abstraction to accommodate real API complexity from start.

---

### Pitfall 7: Over-Confident Recommendations

**What goes wrong:**
Agent states "This approach is optimal" or "You should definitely do X" with high confidence but based on incomplete information. Team follows recommendation, discovers major issues the agent didn't consider. Trust in agent collapses after 2-3 wrong recommendations.

**Why it happens:**
LLMs are trained to sound confident. "I think this might work" feels less authoritative than "This is the best approach." Agents don't have mechanisms to express uncertainty or ask clarifying questions. Training doesn't emphasize epistemic humility.

**How to avoid:**
- **Confidence scoring:** Agent explicitly states confidence level for each recommendation
- **Reasoning transparency:** Agent explains what information it used and what it doesn't know
- **Alternative proposals:** Agent presents 2-3 options with tradeoffs, not single "best" answer
- **Clarifying questions:** Agent asks follow-up questions before making recommendation
- **Uncertainty prompts:** System prompt explicitly instructs agent to express uncertainty when appropriate

**Warning signs:**
- All recommendations stated with equal confidence
- No "I don't have enough information" responses
- No alternative options presented
- Agent doesn't ask clarifying questions
- Recommendations contradict known constraints

**Phase to address:**
Phase 1 (Core Agent) - Build into system prompts and response schemas from start.

---

### Pitfall 8: No Audit Trail for Agent Decisions

**What goes wrong:**
Three months later, team asks "why did we decide to do X?". No record of agent's reasoning. Can't reconstruct decision-making process. Can't debug when agent recommendations go wrong. Compliance issues in regulated environments.

**Why it happens:**
Developers store agent outputs (proposals) but not inputs (prompts, context, reasoning). Logging feels like overhead. Storage costs for full conversation history seem wasteful. Audit trail not required for MVP so deferred.

**How to avoid:**
- **Full prompt logging:** Store complete prompt sent to LLM, including context and constraints
- **Reasoning capture:** Have agent output step-by-step reasoning before conclusion
- **Version tracking:** Tag each agent decision with model version, timestamp, context state
- **Structured logs:** JSON format for easy querying later
- **Retention policy:** Keep audit data for minimum required period (e.g., 1 year)

**Warning signs:**
- Only final proposal stored, not how agent arrived there
- Can't reproduce agent output for same inputs
- No logs of what context was provided to agent
- No way to see agent reasoning
- Compliance questions can't be answered

**Phase to address:**
Phase 1 (Core Agent) - Audit infrastructure must exist from start or data is lost forever.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Single provider (OpenAI only) | Faster initial development | Vendor lock-in, no fallback on outage | Only in prototype/demo, not production |
| Synchronous agent calls | Simpler code, no job queue needed | UI blocks, poor UX, doesn't scale | Never - async infrastructure is foundational |
| String-based agent responses | Easy to start, no schema needed | Can't validate, can't parse reliably, hallucination undetectable | Never - structured output is critical |
| In-memory context only | No database complexity | Context lost between sessions, can't audit | Only for stateless operations (data lookup) |
| Mocks without real API testing | v1 ships faster | v2 rewrite required, surprises in production | Only if contract tests in place + plan to test real API soon |
| Agent generates final decision | No approval workflow needed | Trust breaks on first mistake, compliance issues | Never for production, OK for internal tools |
| No reasoning capture | Less storage, simpler code | Can't debug wrong recommendations, no learning | Never - debugging without reasoning is impossible |
| Manual prompt engineering | No framework dependencies | Prompts become unmaintainable, inconsistent | Only for first prototype, move to prompt framework quickly |

---

## Integration Gotchas

Common mistakes when connecting to external services (Jira, GitHub, Slack, etc.)

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Jira API | Assuming all fields are present in all projects | Query project schema, handle missing custom fields gracefully |
| GitHub API | Not handling rate limits (5000 req/hr) | Implement exponential backoff, cache aggressively, use GraphQL not REST |
| Slack webhooks | Sending notifications for every event | Batch notifications, use threading, respect user quiet hours |
| Calendar APIs | Assuming single calendar per user | Handle multiple calendars, check availability across all |
| Auth tokens | Storing tokens without expiry handling | Implement token refresh flow, handle auth failures gracefully |
| Webhooks (inbound) | No retry or idempotency | Webhook receiver must be idempotent, handle duplicate deliveries |
| Pagination | Only fetching first page | Detect pagination, fetch all pages, handle cursor/offset differences |
| Timezones | Storing times in user timezone | Always store UTC, convert to user timezone only for display |

---

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Loading full project history into context | Agent has "complete" context | Summarize older history, only include recent in detail | ~100 tickets or 6+ months of data |
| Synchronous LLM call per API request | Simple request-response | Background jobs, batch multiple requests | ~5 concurrent users |
| No caching of agent responses | Always fresh data | Cache proposals for similar inputs, TTL 1-24hrs | ~50 proposals/day |
| Fetching all integration data on every agent call | Always up-to-date | Incremental sync, webhook-based updates | ~1000 Jira tickets or GitHub issues |
| Storing entire conversation history in database | Complete audit trail | Summarize old conversations, archive to object storage | ~10k messages or ~6 months |
| No request queuing | Fair resource usage | Queue agent requests, limit concurrent LLM calls | ~10 concurrent users |
| Loading all teams/projects for context | Agent sees everything | Scope context to relevant teams only | ~15 teams |

---

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Including sensitive data in LLM prompts | Data sent to external LLM provider (OpenAI, etc.) | Redact PII, secrets, financial data before sending to LLM |
| No access control on agent actions | Agent can access/modify any project | Implement same RBAC as human users, agent inherits user permissions |
| Storing LLM API keys in code | Keys leaked in version control | Use environment variables, secrets management (Vault, etc.) |
| Agent can execute arbitrary actions | Malicious prompt injection could cause damage | Whitelist allowed actions, require approval for destructive operations |
| No rate limiting on agent usage | Cost explosion from abuse or bugs | Per-user rate limits, cost budgets, alerts on unusual usage |
| Logging prompts with secrets | Secrets exposed in logs | Sanitize logs, never log full prompts without redaction |
| Prompt injection vulnerabilities | User input manipulates agent behavior | Sanitize user input, separate instructions from data in prompts |
| No model output validation | Agent could return malicious content | Validate and sanitize all agent outputs before use |

---

## UX Pitfalls

Common user experience mistakes in this domain.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Agent feels like a chatbot | Users treat it conversationally, waste time | Tool-first UI: buttons/forms for common tasks, chat for exploration |
| No loading time expectations | Users don't know how long to wait | Show estimated time: "Analyzing project... ~30 seconds" |
| Agent speaks in AI jargon | "Based on the embedding similarity..." confuses users | Plain language: "Similar to the authentication project last quarter" |
| No way to edit agent proposal | Must regenerate from scratch if 90% right | Inline editing of proposals, "regenerate section" not whole proposal |
| Notification fatigue | Agent suggests things constantly | Batch suggestions, user controls frequency, "do not disturb" mode |
| No diff view for changes | Can't see what agent changed | Show before/after comparison, highlight changed fields |
| Agent replaces human judgment | Team stops thinking, blindly follows agent | Frame as "recommendations" not "decisions", encourage human judgment |
| No feedback mechanism | Can't tell agent recommendation was wrong | Thumbs up/down on recommendations, "this didn't work because..." |
| Generic error messages | "Agent failed" is not actionable | Specific errors: "GitHub API rate limit, try again in 15 minutes" |
| No progressive disclosure | All agent features shown at once | Start simple (basic proposals), reveal advanced features as user learns |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Agent proposals:** Often missing validation that referenced entities exist — verify team members, projects, dates against actual data
- [ ] **Context management:** Often missing memory persistence between sessions — verify decisions survive session restart
- [ ] **Error handling:** Often missing LLM provider timeout/failure handling — verify system works when LLM is down
- [ ] **Audit trail:** Often missing prompt and reasoning capture — verify can reconstruct why agent made decision
- [ ] **Access control:** Often missing permission checks on agent actions — verify agent respects user RBAC
- [ ] **Cost controls:** Often missing rate limits and budgets — verify can't accidentally spend $10k on LLM calls
- [ ] **Async operations:** Often missing job status tracking — verify user can see progress and cancel long operations
- [ ] **Integration resilience:** Often missing retry/fallback logic — verify handles API rate limits, timeouts, partial failures
- [ ] **Output validation:** Often missing schema validation on agent responses — verify agent output parseable and safe
- [ ] **Confidence communication:** Often missing uncertainty expression — verify agent indicates when not confident

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Hallucinated data in proposals | LOW | Add validation layer, migrate existing proposals to mark unvalidated data |
| Context amnesia | MEDIUM | Add memory store, retrain users to verify constraints before accepting proposals |
| Synchronous blocking | HIGH | Rewrite to async (major architecture change), add job queue infrastructure |
| No LLM fallback | MEDIUM | Add provider abstraction layer, implement circuit breaker, add manual mode |
| Authority ambiguity | LOW | Add visual indicators, update documentation, implement explicit approval flows |
| Mock divergence | HIGH | Rewrite integrations against real API, add contract tests, audit all integration code |
| Over-confident recommendations | LOW | Update prompts to express uncertainty, add confidence scores to existing data |
| No audit trail | HIGH (data lost) | Add logging going forward, historical decisions unrecoverable |

---

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Hallucinated proposal data | Phase 1: Core Agent | Run agent 100 times, manually verify all entity references are valid |
| Context window amnesia | Phase 1: Core Agent | Multi-turn conversation test: mention constraint early, verify respected 20 messages later |
| Synchronous agent blocking | Phase 1: Core Agent | Load test: 10 concurrent agent requests, verify UI remains responsive |
| No LLM provider fallback | Phase 1: Core Agent | Kill provider connection mid-request, verify graceful degradation |
| Agent authority ambiguity | Phase 1: Core Agent | User study: show proposals, ask "what did agent already do vs suggest?" |
| Mock integration divergence | Phase 1: Mocked Integrations | Contract tests pass, integration tests against real API staging |
| Over-confident recommendations | Phase 1: Core Agent | Review 50 agent outputs, verify confidence expressed appropriately |
| No audit trail | Phase 1: Core Agent | Query logs for proposal from last week, verify full prompt/reasoning retrievable |
| Notification fatigue | Phase 2: Real Integrations | User feedback after 1 week: notifications helpful or annoying? |
| Integration rate limits | Phase 2: Real Integrations | Hit Jira/GitHub rate limit intentionally, verify graceful handling |
| Cost explosion | Phase 1: Core Agent | Run 1000 agent requests, calculate monthly cost, verify under budget |
| Prompt injection | Phase 2: Real Integrations | Security test: attempt to manipulate agent via user input |

---

## Phase-Specific Warnings

### Phase 1: Core Agent (Mocked Data)

**High Risk:**
- Designing for synchronous calls (cannot easily convert to async later)
- No structured output schemas (hallucination detection impossible)
- Tight coupling to LLM provider (no fallback, vendor lock-in)
- No audit trail infrastructure (historical data unrecoverable)

**Medium Risk:**
- Mocks too simple (diverge from real APIs)
- No memory architecture (context lost between sessions)
- Generic error handling (users can't act on errors)

**Mitigation:**
- Build async infrastructure from day 1 even if slower to develop
- Define structured schemas before writing agent code
- Abstract LLM provider behind interface
- Log full prompts/responses with structured metadata

### Phase 2: Real Integrations

**High Risk:**
- Assuming real APIs behave like mocks (surprise failures in production)
- No rate limiting (cost explosion, provider bans)
- Notification spam (user complaints, decreased trust)

**Medium Risk:**
- Insufficient error handling for partial failures
- No integration health monitoring
- Auth token expiry not handled

**Mitigation:**
- Run integration tests against real API staging environments
- Implement rate limits and cost budgets before production
- User controls for notification frequency
- Circuit breaker pattern for integration failures

### Phase 3+: Production Hardening

**High Risk:**
- No monitoring/alerting on agent failures (silent degradation)
- No cost controls as usage scales (budget surprises)
- No performance testing (agent becomes bottleneck)

**Mitigation:**
- Monitor agent success rate, latency, cost per request
- Set up cost alerts and automatic cutoffs
- Load test with realistic concurrent users

---

## Sources

**Confidence Note:** WebSearch was unavailable during research. Findings based on:
- Training knowledge of LLM agent architectures (as of Jan 2025)
- Common patterns in AI agent systems and delivery management tools
- Project context provided (on-prem, Python, 5-15 teams, trust model)
- Best practices for production LLM systems

**Verification recommended for:**
- Current state of LLM provider reliability (2026)
- Latest prompt injection mitigation techniques
- Python LLM framework best practices (LangChain, LlamaIndex, etc.)
- Specific integration API changes (Jira, GitHub, Slack)

**Higher confidence areas:**
- LLM hallucination patterns (well-documented)
- Context window limitations (architectural constraint)
- Synchronous vs async design tradeoffs (general software architecture)
- Mock divergence problems (common in all integration projects)

---

*Pitfalls research for: AI-Powered Delivery Management Agent*
*Researched: 2026-02-05*
*Confidence: MEDIUM - Training knowledge + project context, verification with current sources recommended*
