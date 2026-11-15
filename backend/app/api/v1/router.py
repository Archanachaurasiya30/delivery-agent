"""API v1 router aggregating all endpoints."""

from fastapi import APIRouter

from app.api.v1 import agent, ws
from app.api.v1.autopilot import router as autopilot_router
from app.api.v1.briefs import router as briefs_router
from app.api.v1.coding import router as coding_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.exec import router as exec_router
from app.api.v1.features import router as features_router
from app.api.v1.portfolio import router as portfolio_router
from app.api.v1.sprints import router as sprints_router
from app.api.v1.standup import router as standup_router
from app.api.v1.streams import router as streams_router
from app.api.v1.tasks import router as tasks_router
from app.api.v1.team import router as team_router

router = APIRouter()

# Include sub-routers
router.include_router(team_router)
router.include_router(tasks_router)
router.include_router(sprints_router)
router.include_router(features_router)
router.include_router(agent.router)
router.include_router(standup_router)
router.include_router(portfolio_router)
router.include_router(streams_router)
router.include_router(coding_router)
router.include_router(exec_router)
router.include_router(briefs_router)
router.include_router(autopilot_router)
router.include_router(dashboard_router)
router.include_router(ws.router)


@router.get("/health")
async def health_check() -> dict:
    """
    Health check endpoint.

    Returns the service status and version for monitoring and load balancer checks.
    """
    return {"status": "ok", "version": "0.1.0"}
