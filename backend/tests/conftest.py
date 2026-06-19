import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from app.config import settings
from app.db import Base, get_db
from app.main import app as fastapi_app
import app.models  # registra todos los modelos en Base.metadata

TEST_DB_URL = settings.database_url + "_test"

@pytest.fixture(scope="session")
def engine():
    from sqlalchemy_utils import create_database, database_exists, drop_database
    if database_exists(TEST_DB_URL):
        drop_database(TEST_DB_URL)
    create_database(TEST_DB_URL)
    eng = create_engine(TEST_DB_URL)
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()
    drop_database(TEST_DB_URL)

@pytest.fixture
def db_session(engine):
    conn = engine.connect()
    txn = conn.begin()
    TestingSession = sessionmaker(bind=conn, join_transaction_mode="create_savepoint")
    session = TestingSession()
    yield session
    session.close()
    txn.rollback()
    conn.close()

@pytest.fixture
def client(db_session):
    fastapi_app.dependency_overrides[get_db] = lambda: db_session
    yield TestClient(fastapi_app)
    fastapi_app.dependency_overrides.clear()
