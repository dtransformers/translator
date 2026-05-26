import pytest
import pytest_asyncio
from httpx import AsyncClient, BasicAuth
from typing import AsyncGenerator

from app.main import app
from app.db.session import get_db


class MockAsyncSession:
    """A dummy session to avoid real DB connections during mocked tests."""
    pass


# Test credentials matching the defaults in config
TEST_AUTH = BasicAuth(username="admin", password="changeme")


@pytest.fixture
def mock_db_session():
    return MockAsyncSession()


@pytest_asyncio.fixture()
async def client(mock_db_session) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield mock_db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(app=app, base_url="http://test", auth=TEST_AUTH) as ac:
        yield ac

    app.dependency_overrides.clear()
