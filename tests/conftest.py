from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.dependencies.auth import get_current_user
from app.main import app

TEST_USER_UUID = UUID("00000000-dead-beef-0000-000000000001")


@pytest.fixture(scope="session")
def client() -> TestClient:
    app.dependency_overrides[get_current_user] = lambda: TEST_USER_UUID
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_current_user, None)
