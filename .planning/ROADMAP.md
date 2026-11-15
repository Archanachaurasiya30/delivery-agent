# Roadmap: Delivery Agent

## Overview

This roadmap delivers an AI-powered delivery manager. Phases 1-5 backend work is complete (implemented outside GSD tracking). Phase 6 completes the frontend UI to make the system fully usable.

## Phases

- [x] **Phase 1: Foundation & Infrastructure** - Core platform with async agent infrastructure (BACKEND COMPLETE)
- [x] **Phase 2: Task & Sprint Management** - Task tracking and sprint workflows (BACKEND COMPLETE)
- [x] **Phase 3: AI Agent Core** - Agent-powered sprint proposals (BACKEND COMPLETE)
- [x] **Phase 4: Standups & Blockers** - Automated standups and blocker detection (BACKEND COMPLETE)
- [x] **Phase 5: Release Management** - Changelog and release readiness (BACKEND COMPLETE)
- [ ] **Phase 6: Frontend Completion** - Rich UI components for all features

## Phase Details

### Phase 1-5: Backend (COMPLETE)

All backend APIs, models, services, and agent logic implemented:

| API Group | Endpoints | Status |
|-----------|-----------|--------|
| Team | GET/POST/PATCH/DELETE /team/members | ✅ |
| Tasks | GET/POST/PATCH/DELETE /tasks | ✅ |
| Sprints | Full CRUD + activate/complete/burndown | ✅ |
| Agent | POST /agent/request, proposals, approve/reject | ✅ |
| WebSocket | /ws/updates for real-time | ✅ |

### Phase 6: Frontend Completion
**Goal**: Complete all frontend UI components to make the delivery agent fully usable
**Depends on**: Phases 1-5 (complete)
**Status**: Ready to plan

**Success Criteria** (what must be TRUE):
  1. User can view and manage tasks in a Kanban board with drag-drop between columns
  2. User can view sprint burndown chart showing progress over time
  3. User can view agent proposals with reasoning and approve/reject/modify them
  4. User can participate in standup flow and view team standup summaries
  5. User can view release readiness dashboard with changelog preview

**Frontend Components Needed:**

| Component | Backend API | Priority |
|-----------|-------------|----------|
| Kanban Board | GET/PATCH /tasks | High |
| Burndown Chart | GET /sprints/{id}/burndown | High |
| Sprint Management | Full sprint CRUD | High |
| Agent Proposals | GET/POST /agent/* | Medium |
| Standup Interface | POST /agent/request (standup) | Medium |
| Release Dashboard | POST /agent/request (release) | Medium |

Plans:
- [ ] 06-01: TBD during phase planning

## Progress

| Phase | Status | Completed |
|-------|--------|-----------|
| 1. Foundation & Infrastructure | ✅ Backend complete | 2026-02-08 |
| 2. Task & Sprint Management | ✅ Backend complete | 2026-02-08 |
| 3. AI Agent Core | ✅ Backend complete | 2026-02-08 |
| 4. Standups & Blockers | ✅ Backend complete | 2026-02-08 |
| 5. Release Management | ✅ Backend complete | 2026-02-08 |
| 6. Frontend Completion | Not started | - |

---
*Roadmap created: 2026-02-05*
*Last updated: 2026-02-08 — Synced to match actual implementation*
