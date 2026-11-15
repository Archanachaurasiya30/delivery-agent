"""Feature API endpoints.

A Feature is a deliverable grouping of tasks within a stream (the "what" a user
story belongs to). Kept deliberately small: list (optionally by stream) + create
so the authoring form can offer a Feature dropdown with inline "add".
"""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.feature import Feature
from app.schemas.feature import FeatureCreate, FeatureListResponse, FeatureResponse

router = APIRouter(prefix="/features", tags=["features"])
logger = logging.getLogger(__name__)


@router.get("", response_model=FeatureListResponse)
async def list_features(
    stream_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
) -> FeatureListResponse:
    """List features, optionally scoped to a single stream."""
    query = select(Feature).order_by(Feature.name)
    if stream_id is not None:
        query = query.where(Feature.stream_id == str(stream_id))
    res = await db.execute(query)
    features = res.scalars().all()
    return FeatureListResponse(
        features=[FeatureResponse.model_validate(f) for f in features],
        total=len(features),
    )


@router.post("", response_model=FeatureResponse, status_code=status.HTTP_201_CREATED)
async def create_feature(
    data: FeatureCreate,
    db: AsyncSession = Depends(get_db),
) -> FeatureResponse:
    """Create a new feature (used by the form's inline '+ New feature')."""
    feature = Feature(
        name=data.name,
        description=data.description,
        stream_id=str(data.stream_id) if data.stream_id else None,
    )
    db.add(feature)
    await db.commit()
    await db.refresh(feature)
    return FeatureResponse.model_validate(feature)
