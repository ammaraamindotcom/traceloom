"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.routes.activities import router as activities_router
from app.routes.analysis import router as analysis_router
from app.routes.intent import router as intent_router
from app.routes.incidents import router as incidents_router
from app.routes.policy import router as policy_router
from app.routes.evaluation import router as evaluation_router
from app.routes.simulator import router as simulator_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Migrations can replace this bootstrap step once the schema evolves.
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="IntentShield API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.include_router(activities_router)
app.include_router(simulator_router)
app.include_router(analysis_router)
app.include_router(intent_router)
app.include_router(incidents_router)
app.include_router(policy_router)
app.include_router(evaluation_router)


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}
