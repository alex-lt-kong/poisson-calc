# Implementation Plan: Poisson Calculator

## Overview

Build a FastAPI-based Poisson calculator web application with token-based authentication, structured validation, timezone-aware timestamp handling, and a single-page HTML frontend. The implementation proceeds bottom-up: pure calculation logic first, then models and validation, authentication, API wiring, frontend, and finally integration testing.

## Tasks

- [ ] 1. Set up project structure and dependencies
  - Create the project directory layout: `app/` for backend modules, `static/` for frontend, `tests/` for test files
  - Create `requirements.txt` with dependencies: `fastapi`, `uvicorn`, `httpx`, `pytest`, `pytest-asyncio`, `hypothesis`
  - Create an empty `tokens.txt` file with one sample UUID token for development
  - Create `tests/conftest.py` with shared fixtures: async test client, temporary token file setup, valid/invalid token helpers
  - _Requirements: 8.1, 8.5, 10.2_

- [ ] 2. Implement calculation logic
  - [ ] 2.1 Create `app/calculator.py` with pure calculation functions
    - Implement `compute_lambda(probability_pct)` → `−ln(1 − probability_pct / 100)`
    - Implement `compute_window_hours(days, hours)` → `(days × 24) + hours`
    - Implement `compute_scaling_factor(window_hours, hours_in_year=8766.0)` → `hours_in_year / window_hours`
    - Implement `compute_annualized_frequency(lambda_val, scaling_factor)` → `round(lambda_val × scaling_factor, 2)`
    - Implement `calculate_poisson(probability_pct, days, hours)` that calls all step functions and returns a result object
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [ ]* 2.2 Write property test for calculation pipeline correctness
    - **Property 1: Calculation pipeline correctness**
    - Generate random valid probability in (0, 100) and valid window (days ≥ 0, hours 0–23, total > 0)
    - Verify `lambda_value == −ln(1 − probability / 100)`, `window_hours == (days × 24) + hours`, `scaling_factor == 8766 / window_hours`, `annualized_frequency == round(lambda_value × scaling_factor, 2)`
    - Use `hypothesis` with `st.floats(min_value=0.001, max_value=99.999)` for probability, `st.integers(0, 365)` for days, `st.integers(0, 23)` for hours, filter total > 0
    - Place in `tests/test_calculator.py`
    - **Validates: Requirements 4.1, 4.2, 4.3, 4.4**

  - [ ]* 2.3 Write unit tests for calculation functions
    - Test known input/output pairs: e.g., probability=50%, window=24h → verify exact lambda, scaling_factor, annualized_frequency
    - Test edge values near boundaries (probability close to 0, close to 100, window of 1 hour, large windows)
    - Place in `tests/test_calculator.py`
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

- [ ] 3. Implement Pydantic models and validation
  - [ ] 3.1 Create `app/models.py` with request/response Pydantic models
    - Define `TimestampRange` with `start: datetime` and `end: datetime` (both timezone-aware)
    - Define `WindowDuration` with `days: int` (≥ 0) and `hours: int` (0–23)
    - Define `CalculationRequest` with `time_range`, `window`, `probability` (0, 100 exclusive), and `mode` (default "poisson")
    - Define `CalculationSteps` with `lambda_value`, `window_hours`, `scaling_factor`, `annualized_frequency`
    - Define `CalculationResponse` with `mode`, `time_range_utc`, and `steps`
    - Define `ErrorDetail` with `field` and `message`, and `ErrorResponse` with `errors: list[ErrorDetail]`
    - Add Pydantic `model_validator` for cross-field rules: start < end (after UTC conversion), window total > 0
    - _Requirements: 1.6, 2.2, 2.3, 2.4, 3.2, 3.3, 5.1, 8.3_

  - [ ]* 3.2 Write property tests for input validation
    - **Property 2: Time range validation rejects invalid ranges**
    - Generate datetime pairs where start ≥ end (after UTC conversion), verify validation error on `time_range` field
    - Place in `tests/test_validation.py`
    - **Validates: Requirements 1.6**

  - [ ]* 3.3 Write property test for window validation
    - **Property 3: Window validation rejects invalid inputs**
    - Generate invalid window inputs: negative days, hours outside 0–23, zero total duration
    - Verify validation error on `window` field
    - Place in `tests/test_validation.py`
    - **Validates: Requirements 2.2, 2.3, 2.4**

  - [ ]* 3.4 Write property test for probability validation
    - **Property 4: Probability validation rejects out-of-range values**
    - Generate probability values ≤ 0 or ≥ 100, verify validation error on `probability` field
    - Place in `tests/test_validation.py`
    - **Validates: Requirements 3.2, 3.3**

  - [ ]* 3.5 Write property test for structured validation errors
    - **Property 5: Structured validation errors identify all invalid fields**
    - Generate requests with random combinations of invalid fields
    - Verify error response identifies exactly the set of invalid fields with human-readable messages
    - Place in `tests/test_validation.py`
    - **Validates: Requirements 5.1, 8.3**

  - [ ]* 3.6 Write property test for UTC timezone conversion
    - **Property 6: UTC timezone conversion preserves absolute time**
    - Generate timestamps with random timezone offsets, verify UTC conversion preserves absolute time
    - Verify all response timestamps have UTC offset
    - Place in `tests/test_timezone.py`
    - **Validates: Requirements 9.2, 9.3**

- [ ] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Implement authentication module
  - [ ] 5.1 Create `app/auth.py` with `TokenStore` class and `verify_token` dependency
    - Implement `TokenStore.__init__` to accept a token file path
    - Implement `TokenStore.load_tokens` to read the file, parse one UUID per line, skip blank/invalid lines, store in a `set`
    - Implement `TokenStore.is_valid(token)` for O(1) lookup
    - Implement `TokenStore.reload_if_modified` to check file mtime and reload if changed
    - Handle missing/unreadable file: log error, set empty token set, reject all requests
    - Implement `verify_token` as a FastAPI dependency that extracts token from `Authorization` header, calls `reload_if_modified`, then validates
    - Return HTTP 401 with appropriate message for missing token, invalid token, or unavailable token store
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7, 10.8_

  - [ ]* 5.2 Write property test for auth token gate
    - **Property 7: Auth token gate**
    - Generate random UUID strings, some in the store and some not
    - Verify access granted iff token is valid; missing/invalid tokens get HTTP 401
    - Place in `tests/test_auth.py`
    - **Validates: Requirements 10.3, 10.5, 10.6**

  - [ ]* 5.3 Write unit tests for token store
    - Test loading tokens from file, reloading on modification, handling missing file, skipping malformed lines
    - Test `verify_token` dependency: missing header → 401, invalid UUID → 401, valid UUID → proceeds
    - Place in `tests/test_auth.py`
    - _Requirements: 10.2, 10.4, 10.5, 10.7, 10.8_

- [ ] 6. Implement API routes and application entry point
  - [ ] 6.1 Create `app/routes.py` with the POST `/api/calculate` endpoint
    - Wire up `verify_token` as a dependency on the endpoint
    - Accept `CalculationRequest` body, validate inputs
    - Convert timestamps to UTC, run `calculate_poisson`, build `CalculationResponse`
    - Add custom exception handler to transform Pydantic `ValidationError` into structured `ErrorResponse` (422)
    - Return structured `ErrorResponse` for validation failures, `CalculationResponse` for success
    - _Requirements: 4.5, 5.1, 8.2, 8.3, 9.2, 9.3_

  - [ ] 6.2 Create `app/main.py` as the application entry point
    - Create FastAPI app instance
    - Mount `/static` directory for serving frontend files
    - Add CORS middleware with permissive settings for development
    - Include the API router from `routes.py`
    - Add a root route (`GET /`) that serves `index.html`
    - Ensure `/docs` auto-generated documentation is available
    - _Requirements: 8.1, 8.4, 8.5, 8.6_

  - [ ]* 6.3 Write integration tests for API endpoints
    - Test end-to-end calculation: valid request with auth token → verify full response structure and values
    - Test validation error responses: invalid inputs → verify structured error format
    - Test auth enforcement: missing token → 401, invalid token → 401
    - Test static file serving: `GET /` returns HTML content
    - Test `/docs` returns 200
    - Place in `tests/test_api.py`
    - _Requirements: 4.5, 5.1, 8.2, 8.4, 8.5, 10.3, 10.4, 10.5_

- [ ] 7. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 8. Implement the frontend
  - [ ] 8.1 Create `static/index.html` with the single-page layout
    - Add Mode Selector dropdown with "Poisson" as default and only option
    - Add Time Range section: two timestamp selectors (Start, End) with date, time, and timezone inputs
    - Default Start to "Now" in browser local timezone; default End timezone to US Eastern
    - Add "Now" button for Start to populate current date/time
    - Add Window Duration section: two numeric inputs for days (≥ 0) and hours (0–23)
    - Add Probability section: single numeric input for percentage
    - Add Calculate button
    - Add Results section (hidden by default) to display all Calculation_Steps and Annualized_Frequency
    - Add per-field error display areas adjacent to each input
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 3.1, 4.6, 5.2, 5.3, 5.4, 6.1, 6.2, 7.2_

  - [ ] 8.2 Implement inline JavaScript for API communication and UI logic
    - Collect all inputs, format timestamps as ISO 8601 with timezone offset
    - POST to `/api/calculate` with `Authorization` header containing the auth token
    - On success: clear errors, display Calculation_Steps and Annualized_Frequency in the results section
    - On 422: parse `ErrorResponse`, display per-field error messages adjacent to inputs, hide results
    - On 401: display auth error message
    - On network error: display general error banner
    - Implement per-mode input state preservation in a JS object
    - _Requirements: 5.2, 5.3, 5.4, 6.3, 9.1_

  - [ ] 8.3 Add responsive and accessible styling with inline CSS
    - Use classless or minimal CSS for clean, readable design
    - Ensure layout adapts from 320px to 1920px without horizontal scrolling
    - Ensure all interactive controls are keyboard-navigable and screen-reader compatible (labels, ARIA attributes)
    - _Requirements: 7.1, 7.3, 7.4, 7.5_

- [ ] 9. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation of working code
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The implementation language is Python, matching the design document
