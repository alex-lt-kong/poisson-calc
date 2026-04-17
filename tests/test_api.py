"""Integration tests for the Poisson Calculator API endpoints.

Tests cover end-to-end calculation, validation error responses,
authentication enforcement, static file serving, and API docs.
"""

import math

import pytest
import httpx

from tests.conftest import VALID_TOKEN, INVALID_TOKEN


# ---------------------------------------------------------------------------
# Task 6.3 — Integration tests for API endpoints
# ---------------------------------------------------------------------------


class TestEndToEndCalculation:
    """Test valid calculation requests return full response structure."""

    @pytest.mark.asyncio
    async def test_valid_request_returns_calculation_response(
        self, async_client: httpx.AsyncClient
    ) -> None:
        """Valid request with auth token returns 200 with full response structure.

        Validates: Requirements 4.5, 5.1, 8.2
        """
        payload = {
            "time_range": {
                "start": "2024-01-01T00:00:00+00:00",
                "end": "2024-06-01T00:00:00+00:00",
            },
            "window": {"days": 1, "hours": 0},
            "probability": 50.0,
            "mode": "poisson",
        }

        resp = await async_client.post(
            "/api/calculate",
            json=payload,
            headers={"Authorization": VALID_TOKEN},
        )

        assert resp.status_code == 200
        data = resp.json()

        # Verify top-level structure
        assert data["mode"] == "poisson"
        assert "time_range_utc" in data
        assert "steps" in data

        # Verify time_range_utc
        assert "start" in data["time_range_utc"]
        assert "end" in data["time_range_utc"]

        # Verify steps structure and values
        steps = data["steps"]
        assert "lambda_value" in steps
        assert "window_hours" in steps
        assert "scaling_factor" in steps
        assert "annualized_frequency" in steps

        # Verify computed values
        expected_lambda = -math.log(1 - 50.0 / 100)
        assert steps["lambda_value"] == pytest.approx(expected_lambda)
        assert steps["window_hours"] == pytest.approx(24.0)
        assert steps["scaling_factor"] == pytest.approx(8766.0 / 24.0)
        expected_freq = round(expected_lambda * (8766.0 / 24.0), 2)
        assert steps["annualized_frequency"] == pytest.approx(expected_freq)

    @pytest.mark.asyncio
    async def test_timezone_offset_converted_to_utc(
        self, async_client: httpx.AsyncClient
    ) -> None:
        """Timestamps with non-UTC offsets are converted to UTC in the response.

        Validates: Requirements 9.2, 9.3
        """
        payload = {
            "time_range": {
                "start": "2024-01-01T05:00:00+05:00",
                "end": "2024-06-01T05:00:00+05:00",
            },
            "window": {"days": 0, "hours": 12},
            "probability": 25.0,
        }

        resp = await async_client.post(
            "/api/calculate",
            json=payload,
            headers={"Authorization": VALID_TOKEN},
        )

        assert resp.status_code == 200
        data = resp.json()

        # +05:00 at 05:00 -> 00:00 UTC
        start_utc = data["time_range_utc"]["start"]
        assert "2024-01-01T00:00:00" in start_utc


class TestValidationErrors:
    """Test that invalid inputs return structured error responses."""

    @pytest.mark.asyncio
    async def test_invalid_probability_returns_422(
        self, async_client: httpx.AsyncClient
    ) -> None:
        """Out-of-range probability returns 422 with structured errors.

        Validates: Requirements 5.1, 8.3
        """
        payload = {
            "time_range": {
                "start": "2024-01-01T00:00:00+00:00",
                "end": "2024-06-01T00:00:00+00:00",
            },
            "window": {"days": 1, "hours": 0},
            "probability": 0.0,
        }

        resp = await async_client.post(
            "/api/calculate",
            json=payload,
            headers={"Authorization": VALID_TOKEN},
        )

        assert resp.status_code == 422
        data = resp.json()
        assert "errors" in data
        assert len(data["errors"]) > 0

        # Each error should have field and message
        for error in data["errors"]:
            assert "field" in error
            assert "message" in error

        # At least one error should reference probability
        fields = [e["field"] for e in data["errors"]]
        assert any("probability" in f for f in fields)

    @pytest.mark.asyncio
    async def test_invalid_window_zero_duration_returns_422(
        self, async_client: httpx.AsyncClient
    ) -> None:
        """Zero-duration window returns 422 with structured errors."""
        payload = {
            "time_range": {
                "start": "2024-01-01T00:00:00+00:00",
                "end": "2024-06-01T00:00:00+00:00",
            },
            "window": {"days": 0, "hours": 0},
            "probability": 50.0,
        }

        resp = await async_client.post(
            "/api/calculate",
            json=payload,
            headers={"Authorization": VALID_TOKEN},
        )

        assert resp.status_code == 422
        data = resp.json()
        assert "errors" in data
        fields = [e["field"] for e in data["errors"]]
        assert any("window" in f for f in fields)

    @pytest.mark.asyncio
    async def test_start_after_end_returns_422(
        self, async_client: httpx.AsyncClient
    ) -> None:
        """Start >= End returns 422 with structured errors."""
        payload = {
            "time_range": {
                "start": "2024-06-01T00:00:00+00:00",
                "end": "2024-01-01T00:00:00+00:00",
            },
            "window": {"days": 1, "hours": 0},
            "probability": 50.0,
        }

        resp = await async_client.post(
            "/api/calculate",
            json=payload,
            headers={"Authorization": VALID_TOKEN},
        )

        assert resp.status_code == 422
        data = resp.json()
        assert "errors" in data
        fields = [e["field"] for e in data["errors"]]
        assert any("time_range" in f for f in fields)

    @pytest.mark.asyncio
    async def test_missing_required_fields_returns_422(
        self, async_client: httpx.AsyncClient
    ) -> None:
        """Missing required fields return 422 with structured errors."""
        resp = await async_client.post(
            "/api/calculate",
            json={},
            headers={"Authorization": VALID_TOKEN},
        )

        assert resp.status_code == 422
        data = resp.json()
        assert "errors" in data
        assert len(data["errors"]) > 0


class TestAuthEnforcement:
    """Test authentication enforcement on the API endpoint."""

    @pytest.mark.asyncio
    async def test_missing_token_returns_401(
        self, async_client: httpx.AsyncClient
    ) -> None:
        """Request without Authorization header returns 401.

        Validates: Requirements 10.3, 10.4
        """
        payload = {
            "time_range": {
                "start": "2024-01-01T00:00:00+00:00",
                "end": "2024-06-01T00:00:00+00:00",
            },
            "window": {"days": 1, "hours": 0},
            "probability": 50.0,
        }

        resp = await async_client.post("/api/calculate", json=payload)

        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_token_returns_401(
        self, async_client: httpx.AsyncClient
    ) -> None:
        """Request with invalid token returns 401.

        Validates: Requirements 10.5
        """
        payload = {
            "time_range": {
                "start": "2024-01-01T00:00:00+00:00",
                "end": "2024-06-01T00:00:00+00:00",
            },
            "window": {"days": 1, "hours": 0},
            "probability": 50.0,
        }

        resp = await async_client.post(
            "/api/calculate",
            json=payload,
            headers={"Authorization": INVALID_TOKEN},
        )

        assert resp.status_code == 401


class TestStaticFileServing:
    """Test static file serving and root route."""

    @pytest.mark.asyncio
    async def test_root_returns_html(
        self, async_client: httpx.AsyncClient
    ) -> None:
        """GET / returns HTML content.

        Validates: Requirements 8.4, 8.5
        """
        resp = await async_client.get("/")

        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")
        assert "Poisson Calculator" in resp.text


class TestAPIDocs:
    """Test auto-generated API documentation."""

    @pytest.mark.asyncio
    async def test_docs_returns_200(
        self, async_client: httpx.AsyncClient
    ) -> None:
        """GET /docs returns 200.

        Validates: Requirements 8.4
        """
        resp = await async_client.get("/docs")

        assert resp.status_code == 200
