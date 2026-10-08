import os
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine
from app.routers import certificates, jobs

# Auto-apply Alembic migrations on startup if running with postgres/persistent database
try:
    alembic_ini = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    if os.path.exists(alembic_ini):
        cfg = Config(alembic_ini)
        command.upgrade(cfg, "head")
    else:
        Base.metadata.create_all(bind=engine)
except Exception:
    # Graceful fallback for test runners or in-memory sqlite
    try:
        Base.metadata.create_all(bind=engine)
    except Exception:
        pass

app = FastAPI(title="Bulk Certificate Generator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs.router)
app.include_router(certificates.router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
