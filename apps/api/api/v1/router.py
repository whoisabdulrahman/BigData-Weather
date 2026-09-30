from fastapi import APIRouter
from apps.api.api.v1.citizen import router as citizen_router
from apps.api.api.v1.incidents import router as incidents_router
from apps.api.api.v1.analytics import router as analytics_router

api_router = APIRouter()
api_router.include_router(citizen_router)
api_router.include_router(incidents_router)
api_router.include_router(analytics_router)
