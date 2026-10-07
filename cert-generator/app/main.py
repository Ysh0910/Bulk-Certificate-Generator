from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.routers import certificates, jobs

try:
    Base.metadata.create_all(bind=engine)
except Exception:
    # Ignored during test imports or when DB connects asynchronously
    pass

app = FastAPI(title="Bulk Certificate Generator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs.router)
app.include_router(certificates.router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
