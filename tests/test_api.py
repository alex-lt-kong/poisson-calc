"""Integration tests for the Event Horizon API endpoints.

Tests cover end-to-end calculation, validation error responses,
authentication enforcement, static file serving, and API docs.
"""

import math

import pytest
import httpx

from tests.conftest import VALID_TOKEN, INVALID_TOKEN


class TestEndToEndCalculation:
    """Test valid calculation requests return full response structure."""

    @pytest.mark.asyncio
    async def test_valid_request_returns_calculation_response(
        self, async_client: httpx.AsyncClient
    ) -> None:
        """Valid request with auth token returns 200 with full response structure."""
        # 2024-01-01 to 2024-01-02 = exactly 24 hours
        payload = {
            "time_range": {
                "start": "2024-01-01T00:00:00+00:00",
                "end": "2024-01-02T00:00:00+00:00",
            },
            "probability": 50.0,
        }

        resp = await async_client.post(
            "/api/calculate",
            json=payload,
            headers={"Authorization": f"Bearer {VALID_TOKEN}"},
        )

        assert resp.status_code == 200
        data = resp.json()

        assert data["mode"] == "poisson"
        assert "time_range_utc" in data
        assert "steps" in data
        assert "survival" in data

        steps = data["steps"]
        assert "lambda_value" in steps
        assert "window_hours" in steps
        assert "scaling_factor" in steps
        assert "annualized_frequency" in steps

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
        """Timestamps with non-UTC offsets are converted to UTC in the response."""
        payload = {
            "time_range": {
                "start": "2024-01-01T05:00:00+05:00",
                "end": "2024-06-01T05:00:00+05:00",
            },
            "probability": 25.0,
        }

        resp = await async_client.post(
            "/api/calculate",
            json=payload,
            headers={"Authorization": f"Bearer {VALID_TOKEN}"},
        )

        assert resp.status_code == 200
        data = resp.json()
        start_utc = data["time_range_utc"]["start"]
        assert "2024-01-01T00:00:00" in start_utc


class TestValidationErrors:
    """Test that invalid inputs return structured error responses."""

    @pytest.mark.asyncio
    async def test_invalid_probability_returns_422(
        self, async_client: httpx.AsyncClient
    ) -> None:
        """Out-of-range probability returns 422 with structured errors."""
        payload = {
            "time_range": {
                "start": "2024-01-01T00:00:00+00:00",
                "end": "2024-06-01T00:00:00+00:00",
            },
            "probability": 0.0,
        }

        resp = await async_client.post(
            "/api/calculate",
            json=payload,
            headers={"Authorization": f"Bearer {VALID_TOKEN}"},
        )

        assert resp.status_code == 422
        data = resp.json()
        assert "errors" in data
        assert len(data["errors"]) > 0
        fields = [e["field"] for e in data["errors"]]
        assert any("probability" in f for f in fields)

    @pytest.mark.asyncio
    async def test_start_equals_end_returns_422(
        self, async_client: httpx.AsyncClient
    ) -> None:
        """Start == End (zero duration) returns 422."""
        payload = {
            "time_range": {
                "start": "2024-01-01T00:00:00+00:00",
                "end": "2024-01-01T00:00:00+00:00",
            },
            "probability": 50.0,
        }

        resp = await async_client.post(
            "/api/calculate",
            json=payload,
            headers={"Authorization": f"Bearer {VALID_TOKEN}"},
        )

        assert resp.status_code == 422
        data = resp.json()
        assert "errors" in data
        fields = [e["field"] for e in data["errors"]]
        assert any("time_range" in f for f in fields)

    @pytest.mark.asyncio
    async def test_start_after_end_returns_422(
        self, async_client: httpx.AsyncClient
    ) -> None:
        """Start > End returns 422 with structured errors."""
        payload = {
            "time_range": {
                "start": "2024-06-01T00:00:00+00:00",
                "end": "2024-01-01T00:00:00+00:00",
            },
            "probability": 50.0,
        }

        resp = await async_client.post(
            "/api/calculate",
            json=payload,
            headers={"Authorization": f"Bearer {VALID_TOKEN}"},
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
            headers={"Authorization": f"Bearer {VALID_TOKEN}"},
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
        """Request without Authorization header returns 401."""
        payload = {
            "time_range": {
                "start": "2024-01-01T00:00:00+00:00",
                "end": "2024-06-01T00:00:00+00:00",
            },
            "probability": 50.0,
        }

        resp = await async_client.post("/api/calculate", json=payload)
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_token_returns_401(
        self, async_client: httpx.AsyncClient
    ) -> None:
        """Request with invalid token returns 401."""
        payload = {
            "time_range": {
                "start": "2024-01-01T00:00:00+00:00",
                "end": "2024-06-01T00:00:00+00:00",
            },
            "probability": 50.0,
        }

        resp = await async_client.post(
            "/api/calculate",
            json=payload,
            headers={"Authorization": f"Bearer {INVALID_TOKEN}"},
        )
        assert resp.status_code == 401


class TestStaticFileServing:
    """Test static file serving and root route."""

    @pytest.mark.asyncio
    async def test_root_returns_401(self, async_client: httpx.AsyncClient) -> None:
        """GET / returns 401 when no token provided."""
        resp = await async_client.get("/")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_token_url_returns_html(self, async_client: httpx.AsyncClient) -> None:
        """GET /{valid_token} returns the frontend HTML."""
        resp = await async_client.get(f"/{VALID_TOKEN}")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")
        assert "Event Horizon" in resp.text

    @pytest.mark.asyncio
    async def test_invalid_token_url_returns_401(self, async_client: httpx.AsyncClient) -> None:
        """GET /{invalid_token} returns 401."""
        resp = await async_client.get(f"/{INVALID_TOKEN}")
        assert resp.status_code == 401


class TestAPIDocs:
    """Test auto-generated API documentation."""

    @pytest.mark.asyncio
    async def test_docs_returns_200(self, async_client: httpx.AsyncClient) -> None:
        """GET /docs returns 200."""
        resp = await async_client.get("/docs")
        assert resp.status_code == 200
