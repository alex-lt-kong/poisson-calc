"""Property-based and unit tests for the authentication module.

Tests cover the TokenStore class and the verify_token FastAPI dependency
in app.auth, verifying both universal properties (via Hypothesis) and
specific known behaviours.
"""

import uuid

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.auth import TokenStore, verify_token
from fastapi import HTTPException

from tests.conftest import VALID_TOKEN

# ---------------------------------------------------------------------------
# Task 5.2 — Property-based test for auth token gate
# ---------------------------------------------------------------------------

# Feature: poisson-calculator, Property 7: Auth token gate


# A small fixed set of "known valid" tokens used by the property test.
_KNOWN_TOKENS = [
    "550e8400-e29b-41d4-a716-446655440000",
    "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
    "12345678-1234-5678-1234-567812345678",
]


@given(token_uuid=st.uuids())
@settings(max_examples=200)
def test_auth_token_gate(token_uuid: uuid.UUID, tmp_path_factory) -> None:
    """**Validates: Requirements 10.3, 10.5, 10.6**

    For any UUID token, access is granted if and only if the token exists
    in the Token Store.  Tokens not in the store are rejected.
    """
    # Use tmp_path_factory (session-scoped) to avoid Hypothesis health check
    base_tmp = tmp_path_factory.getbasetemp()
    token_file = base_tmp / "prop_tokens.txt"
    if not token_file.exists():
        token_file.write_text("\n".join(_KNOWN_TOKENS) + "\n")

    store = TokenStore(str(token_file))

    token_str = str(token_uuid)

    # Normalise for comparison — TokenStore normalises to lowercase
    normalised = str(uuid.UUID(token_str))
    expected_valid = normalised in {str(uuid.UUID(t)) for t in _KNOWN_TOKENS}

    assert store.is_valid(token_str) is expected_valid


# ---------------------------------------------------------------------------
# Task 5.3 — Unit tests for token store
# ---------------------------------------------------------------------------


class TestTokenStoreLoadTokens:
    """Tests for loading tokens from a file."""

    def test_load_valid_tokens(self, token_file) -> None:
        """Tokens are loaded from a file with one valid UUID per line."""
        store = TokenStore(token_file)
        assert store.is_valid(VALID_TOKEN) is True
        assert store.file_available is True

    def test_load_empty_file(self, empty_token_file) -> None:
        """An empty token file results in no valid tokens."""
        store = TokenStore(empty_token_file)
        assert store.is_valid(VALID_TOKEN) is False
        assert store.file_available is True

    def test_missing_file(self, tmp_path) -> None:
        """A non-existent file results in no valid tokens and file_available=False."""
        missing = str(tmp_path / "does_not_exist.txt")
        store = TokenStore(missing)
        assert store.is_valid(VALID_TOKEN) is False
        assert store.file_available is False

    def test_skip_malformed_lines(self, tmp_path) -> None:
        """Malformed lines are skipped; valid tokens are still loaded."""
        token_file = tmp_path / "tokens.txt"
        token_file.write_text(
            "not-a-uuid\n"
            f"{VALID_TOKEN}\n"
            "also bad\n"
            "\n"
            "6ba7b810-9dad-11d1-80b4-00c04fd430c8\n"
        )
        store = TokenStore(str(token_file))
        assert store.is_valid(VALID_TOKEN) is True
        assert store.is_valid("6ba7b810-9dad-11d1-80b4-00c04fd430c8") is True
        assert store.is_valid("not-a-uuid") is False


class TestTokenStoreReload:
    """Tests for reload_if_modified behaviour."""

    def test_reload_picks_up_new_token(self, token_file) -> None:
        """After writing a new token to the file, reload_if_modified loads it."""
        import os

        store = TokenStore(token_file)
        new_token = "6ba7b810-9dad-11d1-80b4-00c04fd430c8"
        assert store.is_valid(new_token) is False

        # Append a new token to the file
        with open(token_file, "a") as fh:
            fh.write(new_token + "\n")

        # Bump the mtime so reload_if_modified detects the change
        stat = os.stat(token_file)
        os.utime(token_file, (stat.st_atime, stat.st_mtime + 1))

        store.reload_if_modified()
        assert store.is_valid(new_token) is True

    def test_reload_keeps_tokens_when_file_disappears(self, token_file) -> None:
        """If the file disappears after initial load, previously loaded tokens are kept."""
        store = TokenStore(token_file)
        assert store.is_valid(VALID_TOKEN) is True

        import os
        os.remove(token_file)

        store.reload_if_modified()
        # Tokens should still be available
        assert store.is_valid(VALID_TOKEN) is True


class TestTokenStoreIsValid:
    """Tests for the is_valid method edge cases."""

    def test_invalid_uuid_format(self, token_file) -> None:
        """Non-UUID strings are rejected."""
        store = TokenStore(token_file)
        assert store.is_valid("not-a-uuid") is False

    def test_uuid_not_in_store(self, token_file) -> None:
        """A valid UUID not in the store is rejected."""
        store = TokenStore(token_file)
        assert store.is_valid("00000000-0000-0000-0000-000000000000") is False

    def test_case_insensitive_lookup(self, token_file) -> None:
        """Token lookup is case-insensitive (UUIDs are normalised)."""
        store = TokenStore(token_file)
        upper = VALID_TOKEN.upper()
        assert store.is_valid(upper) is True


class TestVerifyTokenDependency:
    """Tests for the verify_token FastAPI dependency."""

    @pytest.mark.asyncio
    async def test_missing_header_returns_401(self) -> None:
        """Missing Authorization header raises HTTP 401."""
        with pytest.raises(HTTPException) as exc_info:
            await verify_token(authorization=None)
        assert exc_info.value.status_code == 401
        assert "required" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_invalid_token_returns_401(self, token_file) -> None:
        """An invalid token raises HTTP 401."""
        import app.auth as auth_module

        original_store = auth_module.token_store
        try:
            auth_module.token_store = TokenStore(token_file)
            with pytest.raises(HTTPException) as exc_info:
                await verify_token(authorization="00000000-0000-0000-0000-000000000000")
            assert exc_info.value.status_code == 401
            assert "invalid" in exc_info.value.detail.lower()
        finally:
            auth_module.token_store = original_store

    @pytest.mark.asyncio
    async def test_valid_token_proceeds(self, token_file) -> None:
        """A valid token returns the token string (no exception)."""
        import app.auth as auth_module

        original_store = auth_module.token_store
        try:
            auth_module.token_store = TokenStore(token_file)
            result = await verify_token(authorization=VALID_TOKEN)
            assert result == VALID_TOKEN
        finally:
            auth_module.token_store = original_store
