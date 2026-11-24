"""Тесты работают с отдельной базой PostgreSQL (TEST_DATABASE_URL), которая пересоздаётся для каждого теста."""
import os

import pytest

TEST_URL = os.environ.get("TEST_DATABASE_URL", "postgresql+psycopg://postgres@localhost:5432/nedro_test")
os.environ["DATABASE_URL"] = TEST_URL
os.environ["SEED_PASSWORD"] = "test-password"

from fastapi.testclient import TestClient  # noqa: E402

from app import models  # noqa: E402,F401
from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import seed_demo, seed_reference, seed_users  # noqa: E402


@pytest.fixture()
def db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as s:
        seed_reference(s)
        seed_users(s)
        seed_demo(s)
        s.commit()
    with SessionLocal() as s:
        yield s


@pytest.fixture()
def client(db):
    return TestClient(app)


def login(client, who):
    r = client.post("/api/auth/login", data={"username": who, "password": "test-password"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture()
def manager(client):
    return login(client, "manager")
