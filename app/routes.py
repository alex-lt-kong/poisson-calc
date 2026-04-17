"""API route handlers for the Poisson Calculator.

Defines the POST /api/calculate endpoint, wires up authentication,
and provides a custom exception handler to transform Pydantic
validation errors into structured ErrorResponse format.
"""

from datetime import timezone

from fastapi import APIRouter, Depends, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.auth import verify_token
from app.calculator import calculate_poisson
from app.models import (
    CalculationRequest,
    CalculationResponse,
    CalculationSteps,
    ErrorDetail,
    ErrorResponse,
    TimestampRange,
)

router = APIRouter()


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Transform FastAPI/Pydantic validation errors into structured ErrorResponse.

    Maps each Pydantic error to an ErrorDetail with a dot-joined field path
    and a human-readable message.
    """
    errors: list[ErrorDetail] = []
    for err in exc.errors():
        loc = err.get("loc", ())
        # Skip the leading "body" segment that FastAPI adds
        field_parts = [str(part) for part in loc if part != "body"]
        field = ".".join(field_parts) if field_parts else "unknown"
        message = err.get("msg", "Validation error")
        errors.append(ErrorDetail(field=field, message=message))

    response = ErrorResponse(errors=errors)
    return JSONResponse(status_code=422, content=response.model_dump())


@router.post("/api/calculate", response_model=CalculationResponse)
async def calculate(
    request: CalculationRequest,
    token: str = Depends(verify_token),
) -> CalculationResponse:
    """Validate inputs, run Poisson calculation, and return all steps.

    - Converts timestamps to UTC
    - Runs the calculation pipeline
    - Returns structured CalculationResponse with UTC time range and steps
    """
    # Convert timestamps to UTC
    start_utc = request.time_range.start.astimezone(timezone.utc)
    end_utc = request.time_range.end.astimezone(timezone.utc)

    # Run the Poisson calculation
    result = calculate_poisson(
        probability_pct=request.probability,
        days=request.window.days,
        hours=request.window.hours,
    )

    # Build the response — convert dataclass CalculationSteps to Pydantic model
    steps = CalculationSteps(
        lambda_value=result.lambda_value,
        window_hours=result.window_hours,
        scaling_factor=result.scaling_factor,
        annualized_frequency=result.annualized_frequency,
    )

    return CalculationResponse(
        mode=request.mode,
        time_range_utc=TimestampRange(start=start_utc, end=end_utc),
        steps=steps,
    )
