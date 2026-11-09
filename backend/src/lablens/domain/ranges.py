"""Deterministic comparison against a report-provided reference interval."""

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, model_validator


class RangeStatus(StrEnum):
    LOW = "low"
    WITHIN_RANGE = "within_range"
    HIGH = "high"
    NOT_ASSESSABLE = "not_assessable"


class NumericRangeComparison(BaseModel):
    """A numeric measurement and inclusive interval from the same report."""

    model_config = ConfigDict(frozen=True)

    value: Decimal
    low: Decimal
    high: Decimal

    @model_validator(mode="after")
    def validate_interval(self) -> "NumericRangeComparison":
        if not all(number.is_finite() for number in (self.value, self.low, self.high)):
            raise ValueError("Result and interval bounds must be finite numbers")
        if self.low > self.high:
            raise ValueError("Reference lower bound exceeds upper bound")
        return self


def compare_to_reference_range(
    comparison: NumericRangeComparison | None,
) -> RangeStatus:
    """Return a neutral status; never infer a diagnosis or clinical urgency."""
    if comparison is None:
        return RangeStatus.NOT_ASSESSABLE
    if comparison.value < comparison.low:
        return RangeStatus.LOW
    if comparison.value > comparison.high:
        return RangeStatus.HIGH
    return RangeStatus.WITHIN_RANGE
