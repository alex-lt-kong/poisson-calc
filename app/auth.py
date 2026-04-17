"""Authentication module for the Poisson Calculator API.

Manages token loading from a flat file, file-change detection, and
request authentication via a FastAPI dependency.
"""

import logging
import os
import uuid
from typing import Optional

from fastapi import Header, HTTPException

logger = logging.getLogger(__name__)


class TokenStore:
    """Loads UUID tokens from a plain-text file and watches for changes.

    Tokens are stored in a ``set`` for O(1) lookup.  The file's last-modified
    timestamp is tracked so the store can be reloaded automatically when the
    file changes on disk.
    """

    def __init__(self, token_file_path: str) -> None:
        self._path = token_file_path
        self._tokens: set[str] = set()
        self._last_mtime: Optional[float] = None
        self._file_available: bool = False
        self.load_tokens()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_tokens(self) -> None:
        """Read the token file and populate the internal token set.

        Each line is expected to contain a single UUID.  Blank lines and
        lines that are not valid UUIDs are skipped with a warning log.
        If the file is missing or unreadable the token set is cleared and
        all subsequent ``is_valid`` calls will return ``False``.
        """
        try:
            with open(self._path, "r") as fh:
                raw_lines = fh.readlines()
        except (OSError, IOError) as exc:
            logger.error("Unable to read token file '%s': %s", self._path, exc)
            self._tokens = set()
            self._file_available = False
            self._last_mtime = None
            return

        tokens: set[str] = set()
        for lineno, line in enumerate(raw_lines, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                # Validate UUID format and normalise to lowercase string
                parsed = uuid.UUID(stripped)
                tokens.add(str(parsed))
            except ValueError:
                logger.warning(
                    "Skipping invalid token on line %d of '%s': %s",
                    lineno,
                    self._path,
                    stripped,
                )

        self._tokens = tokens
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
        return normalised in self._tokens

    def reload_if_modified(self) -> None:
        """Reload the token file if its modification time has changed.

        If the file has become unreadable since the last successful load
        the previously loaded tokens are kept and a warning is logged.
        """
        try:
            current_mtime = os.path.getmtime(self._path)
        except OSError:
            if self._file_available:
                logger.warning(
                    "Token file '%s' is no longer accessible; "
                    "keeping previously loaded tokens.",
                    self._path,
                )
            return

        if self._last_mtime is None or current_mtime != self._last_mtime:
            self.load_tokens()

    @property
    def file_available(self) -> bool:
        """Whether the token file was successfully loaded at least once."""
        return self._file_available


# ------------------------------------------------------------------
# Module-level singleton
# ------------------------------------------------------------------

_token_file_path: str = os.environ.get("TOKEN_FILE_PATH", "tokens.txt")
token_store: TokenStore = TokenStore(_token_file_path)


# ------------------------------------------------------------------
# FastAPI dependency
# ------------------------------------------------------------------


async def verify_token(authorization: str = Header(default=None)) -> str:
    """FastAPI dependency that validates the ``Authorization`` header.

    Extracts the token, triggers a file-change check on the store, and
    verifies the token.  Raises HTTP 401 for missing, invalid, or
    unverifiable tokens.

    Returns:
        The validated token string on success.
    """
    if authorization is None:
        raise HTTPException(status_code=401, detail="Auth token is required")

    token_store.reload_if_modified()

    if not token_store.file_available:
        raise HTTPException(
            status_code=401, detail="Authentication service unavailable"
        )

    if not token_store.is_valid(authorization):
        raise HTTPException(status_code=401, detail="Auth token is invalid")

    return authorization
