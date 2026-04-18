"""Authentication module for the Poisson Calculator API.

Manages token loading from a JSON config file, file-change detection, and
request authentication via a FastAPI dependency.

Config file format (JSON):
    {
        "users": {
            "alice": "550e8400-e29b-41d4-a716-446655440000",
            "bob":   "6ba7b810-9dad-11d1-80b4-00c04fd430c8"
        }
    }
"""

import json
import logging
import os
import uuid
from typing import Optional

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)


class TokenStore:
    """Loads user tokens from a JSON config file and watches for changes.

    The config file maps usernames to UUID tokens.  Tokens are stored in
    a ``dict`` (token → username) for O(1) lookup.  The file's
    last-modified timestamp is tracked so the store can be reloaded
    automatically when the file changes on disk.
    """

    def __init__(self, config_file_path: str) -> None:
        self._path = config_file_path
        self._token_to_user: dict[str, str] = {}
        self._last_mtime: Optional[float] = None
        self._file_available: bool = False
        self.load_tokens()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_tokens(self) -> None:
        """Read the JSON config file and populate the internal token map.

        Expected structure: ``{"users": {"username": "uuid-token", ...}}``.
        Entries with invalid UUID values are skipped with a warning log.
        If the file is missing, unreadable, or malformed the token map is
        cleared and all subsequent ``is_valid`` calls will return ``False``.
        """
        try:
            with open(self._path, "r") as fh:
                data = json.load(fh)
        except (OSError, IOError) as exc:
            logger.error("Unable to read config file '%s': %s", self._path, exc)
            self._token_to_user = {}
            self._file_available = False
            self._last_mtime = None
            return
        except json.JSONDecodeError as exc:
            logger.error("Invalid JSON in config file '%s': %s", self._path, exc)
            self._token_to_user = {}
            self._file_available = False
            self._last_mtime = None
            return

        users = data.get("users", {})
        if not isinstance(users, dict):
            logger.error(
                "Config file '%s': 'users' must be an object, got %s",
                self._path,
                type(users).__name__,
            )
            self._token_to_user = {}
            self._file_available = False
            return

        token_to_user: dict[str, str] = {}
        for username, token_value in users.items():
            try:
                normalised = str(uuid.UUID(str(token_value)))
                token_to_user[normalised] = str(username)
            except (ValueError, AttributeError):
                logger.warning(
                    "Skipping user '%s' in '%s': invalid UUID token '%s'",
                    username,
                    self._path,
                    token_value,
                )

        self._token_to_user = token_to_user
        self._file_available = True

        try:
            self._last_mtime = os.path.getmtime(self._path)
        except OSError:
            self._last_mtime = None

    def is_valid(self, token: str) -> bool:
        """Return ``True`` if *token* exists in the store (O(1) lookup)."""
        if not self._file_available:
            return False
        try:
            normalised = str(uuid.UUID(token))
        except (ValueError, AttributeError):
            return False
        return normalised in self._token_to_user

    def get_username(self, token: str) -> Optional[str]:
        """Return the username associated with *token*, or ``None``."""
        if not self._file_available:
            return None
        try:
            normalised = str(uuid.UUID(token))
        except (ValueError, AttributeError):
            return None
        return self._token_to_user.get(normalised)

    def reload_if_modified(self) -> None:
        """Reload the config file if its modification time has changed.

        If the file has become unreadable since the last successful load
        the previously loaded tokens are kept and a warning is logged.
        """
        try:
            current_mtime = os.path.getmtime(self._path)
        except OSError:
            if self._file_available:
                logger.warning(
                    "Config file '%s' is no longer accessible; "
                    "keeping previously loaded tokens.",
                    self._path,
                )
            return

        if self._last_mtime is None or current_mtime != self._last_mtime:
            self.load_tokens()

    @property
    def file_available(self) -> bool:
        """Whether the config file was successfully loaded at least once."""
        return self._file_available


# ------------------------------------------------------------------
# Module-level singleton
# ------------------------------------------------------------------

_config_file_path: str = os.environ.get("CONFIG_FILE_PATH", "config.json")
token_store: TokenStore = TokenStore(_config_file_path)


# ------------------------------------------------------------------
# FastAPI dependency
# ------------------------------------------------------------------


_bearer_scheme = HTTPBearer(description="Enter your UUID auth token")


async def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> str:
    """FastAPI dependency that validates the Bearer token.

    Extracts the token from the Authorization: Bearer <token> header,
    triggers a file-change check on the store, and verifies the token.
    Raises HTTP 401/403 for missing, invalid, or unverifiable tokens.

    Returns:
        The validated token string on success.
    """
    token = credentials.credentials

    token_store.reload_if_modified()

    if not token_store.file_available:
        raise HTTPException(
            status_code=401, detail="Authentication service unavailable"
        )

    if not token_store.is_valid(token):
        raise HTTPException(status_code=401, detail="Auth token is invalid")

    return token
