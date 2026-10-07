import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.database as app_db
import app.tasks as app_tasks
from app.celery_app import celery_app
from app.config import settings
from app.database import get_db
from app.main import app as fastapi_app
from app.models import Base

# Set Celery tasks to execute eagerly (synchronously in-process) during tests.
# This allows testing the full asynchronous lifecycle (job creation -> task execution
# -> recipient status update) in-memory without needing a running Redis broker or Celery worker.
celery_app.conf.update(
    task_always_eager=True,
    task_eager_propagates=True,
)


@pytest.fixture(scope="session")
def test_engine():
    """Create a persistent in-memory SQLite database engine for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    return engine


@pytest.fixture(autouse=True)
def configure_test_directories(tmp_path, monkeypatch):
    """Ensure GENERATED_DIR and TEMPLATES_DIR point to isolated temp directories per test."""
    gen_dir = tmp_path / "generated"
    gen_dir.mkdir(parents=True, exist_ok=True)
    tpl_dir = tmp_path / "templates"
    tpl_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(settings, "GENERATED_DIR", str(gen_dir))
    monkeypatch.setattr(settings, "TEMPLATES_DIR", str(tpl_dir))
    yield


@pytest.fixture
def db_session(test_engine, monkeypatch):
    """Provide a clean database schema and session for each test function."""
    Base.metadata.create_all(bind=test_engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    # Monkeypatch SessionLocal in database and tasks modules so eager Celery tasks use test db
    monkeypatch.setattr(app_db, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(app_tasks, "SessionLocal", TestingSessionLocal)

    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    fastapi_app.dependency_overrides[get_db] = override_get_db

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        fastapi_app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def client(db_session):
    """FastAPI TestClient wired to the test database session."""
    with TestClient(fastapi_app) as test_client:
        yield test_client
