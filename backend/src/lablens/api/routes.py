"""Versioned API routes."""

from fastapi import APIRouter, Depends

from lablens.api.schemas import RangeComparisonRequest, RangeComparisonResponse
from lablens.db.models import User
from lablens.domain.ranges import NumericRangeComparison, compare_to_reference_range
from lablens.security.identity import get_current_user

router = APIRouter()


@router.post("/range-comparisons", response_model=RangeComparisonResponse)
def create_range_comparison(
    payload: RangeComparisonRequest,
    _: User = Depends(get_current_user),
) -> RangeComparisonResponse:
    """Compare a supplied result to its report interval without storing it."""
    comparison = NumericRangeComparison(
        value=payload.value,
        low=payload.reference_low,
        high=payload.reference_high,
    )
    return RangeComparisonResponse(
        status=compare_to_reference_range(comparison),
        reference_low=payload.reference_low,
        reference_high=payload.reference_high,
        unit=payload.unit,
    )
