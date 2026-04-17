"""Shared test fixtures for the Poisson Calculator test suite."""

import pytest
import pytest_asyncio
import httpx


VALID_TOKEN = "550e8400-e29b-41d4-a716-446655440000"
INVALID_TOKEN = "00000000-0000-0000-0000-000000000000"


@pytest.fixture()
def valid_token() -> str:
    """Return a known-valid auth token."""
    return VALID_TOKEN


@pytest.fixture()
def invalid_token() -> str:
    """Return a token that is not in the token store."""
    return INVALID_TOKEN


@pytest.fixture()
def token_file(tmp_path):
    """Create a temporary token file with one valid token.

    Yields the path to the temp file. The file is cleaned up automatically
    by pytest's tmp_path fixture.
    """
    token_path = tmp_path / "tokens.txt"
    token_path.write_text(VALID_TOKEN + "\n")
    return str(token_path)


@pytest.fixture()
def empty_token_file(tmp_path):
    """Create an empty temporary token file (no valid tokens)."""
    token_path = tmp_path / "tokens_empty.txt"
    token_path.write_text("")
    return str(token_path)


@pytest_asyncio.fixture()
async def async_client(token_file):
    """Provide an async HTTP test client wired to the FastAPI app.

    Patches the module-level token_store in app.auth so the app uses
    the temporary token file, then yields an httpx.AsyncClient configured
    with the app's ASGI transport.
    """
    import app.auth as auth_module
    from app.auth import TokenStore
    from app.main import app  # noqa: WPS433

    original_store = auth_module.token_store
    auth_module.token_store = TokenStore(token_file)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            yield client
    finally:
        auth_module.token_store = original_store
