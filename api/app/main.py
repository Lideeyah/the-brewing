from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import init_db
from app.routers import (
    admin,
    agents,
    analytics,
    auth,
    feedback,
    health,
    objectives,
    trust,
    validation,
    workspaces,
)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Brewing API",
    description="Governed coordination and settlement infrastructure for autonomous systems.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(objectives.router)
app.include_router(workspaces.router)
app.include_router(agents.router)
app.include_router(trust.router)
app.include_router(validation.router)
app.include_router(analytics.router)
app.include_router(feedback.router)
app.include_router(admin.router)


@app.get("/")
def root() -> dict:
    return {"service": "brewing-api", "docs": "/docs"}
