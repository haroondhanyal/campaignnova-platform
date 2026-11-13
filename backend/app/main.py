from contextlib import asynccontextmanager
import hashlib
import os
from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from . import store
from . import database
from .routers import administration, ai, approvals, audiences, authentication, business_rules, campaigns, customers, dashboard, execution, experiments, intelligence, integrations, journeys, offers, reports, scenarios, system, workspaces


@asynccontextmanager
async def lifespan(_: FastAPI):
    store.initialize()
    approvals.bootstrap_approval_queue()
    yield

app = FastAPI(
    title="CampaignNova API",
    version="0.6.0",
    description="CampaignNova APIs with password authentication, department access controls, synthetic development data, and simulation-only execution.",
    lifespan=lifespan,
)


@app.middleware("http")
async def workspace_tenant_scope(request: Request, call_next):
    token = request.cookies.get(authentication.SESSION_COOKIE)
    tenant_id = "campaignnova-demo"
    if token:
        digest = hashlib.sha256(token.encode()).hexdigest()
        sessions = database.list_records("auth_sessions", tenant_id="*")
        session = next((item for item in sessions if item.get("id") == digest), None)
        if session and not session.get("revoked"):
            tenant_id = session.get("tenant_id", tenant_id)
    context_token = database.set_tenant(tenant_id)
    try:
        return await call_next(request)
    finally:
        database.reset_tenant(context_token)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv(
        "CAMPAIGNNOVA_WEB_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    ).split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(system.router, prefix="/api")
app.include_router(authentication.router, prefix="/api")

protected_api = APIRouter(dependencies=[Depends(authentication.require_user)])
protected_api.include_router(dashboard.router)
protected_api.include_router(campaigns.router)
protected_api.include_router(customers.router)
protected_api.include_router(audiences.router)
protected_api.include_router(offers.router)
protected_api.include_router(scenarios.router)
protected_api.include_router(approvals.router)
protected_api.include_router(journeys.router)
protected_api.include_router(business_rules.router)
protected_api.include_router(execution.router)
protected_api.include_router(integrations.router)
protected_api.include_router(ai.router)
protected_api.include_router(reports.router)
protected_api.include_router(intelligence.router)
protected_api.include_router(experiments.router)
protected_api.include_router(administration.router)
protected_api.include_router(workspaces.router)
app.include_router(protected_api, prefix="/api")
