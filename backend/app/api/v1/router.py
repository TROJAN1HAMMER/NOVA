"""
AEKOF — API v1 Router
Aggregates active platform endpoint routers into a single object mounted at `/api/v1`.
"""

from fastapi import APIRouter

from app.api.v1.endpoints.analytics import router as analytics_router
from app.api.v1.endpoints.assistant import router as assistant_router
from app.api.v1.endpoints.executive_intelligence import router as executive_intelligence_router
from app.api.v1.endpoints.faq import router as faq_router
from app.api.v1.endpoints.knowledge import router as knowledge_router
from app.api.v1.endpoints.rag_operations import router as rag_operations_router
from app.api.v1.endpoints.reports import router as reports_router
from app.auth.admin_router import router as auth_admin_router
from app.auth.router import router as auth_router
from app.auth.sso_router import router as auth_sso_router

api_router = APIRouter()
api_router.include_router(analytics_router, tags=["Analytics"])
api_router.include_router(knowledge_router, tags=["Knowledge Base"])
api_router.include_router(assistant_router, tags=["AI Assistant"])
api_router.include_router(faq_router, tags=["FAQ Rules & Gap Inbox"])
api_router.include_router(executive_intelligence_router, tags=["Executive Intelligence"])
api_router.include_router(rag_operations_router, tags=["RAG Operations"])
api_router.include_router(reports_router, tags=["Reports"])
api_router.include_router(auth_router, tags=["Auth"])
api_router.include_router(auth_sso_router, tags=["Auth — SSO"])
api_router.include_router(auth_admin_router, tags=["Auth — Admin"])
