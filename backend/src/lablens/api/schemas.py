"""Public API request and response schemas."""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from lablens.domain.ranges import RangeStatus


class RangeComparisonRequest(BaseModel):
    """A caller-supplied value and the interval printed on its report."""

    model_config = ConfigDict(extra="forbid")

    value: Decimal = Field(description="Numeric value reported by the laboratory")
    reference_low: Decimal
    reference_high: Decimal
    unit: str | None = Field(default=None, max_length=64)

    @model_validator(mode="after")
    def validate_reference_interval(self) -> "RangeComparisonRequest":
        values = (self.value, self.reference_low, self.reference_high)
        if not all(value.is_finite() for value in values):
            raise ValueError("Result and interval bounds must be finite numbers")
        if self.reference_low > self.reference_high:
            raise ValueError("Reference lower bound exceeds upper bound")
        return self


class RangeComparisonResponse(BaseModel):
    status: RangeStatus
    reference_low: Decimal
    reference_high: Decimal
    unit: str | None = None
    note: str = (
        "This compares the number with the interval supplied in the request. "
        "It does not diagnose a condition or determine clinical urgency."
    )


class ReportResponse(BaseModel):
    id: str
    status: str
    media_type: str
    byte_size: int
    page_count: int | None
    created_at: str


class LabResultInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    test_name: str = Field(min_length=1, max_length=256)
    value_text: str = Field(min_length=1, max_length=256)
    numeric_value: Decimal | None = None
    unit: str | None = Field(default=None, max_length=64)
    reference_low: Decimal | None = None
    reference_high: Decimal | None = None
    reference_text: str | None = Field(default=None, max_length=256)
    lab_flag: str | None = Field(default=None, max_length=64)
    page_number: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_result(self) -> "LabResultInput":
        if (self.reference_low is None) != (self.reference_high is None):
            raise ValueError("Both numeric reference bounds are required together")
        values = [
            value
            for value in (self.numeric_value, self.reference_low, self.reference_high)
            if value is not None
        ]
        if not all(value.is_finite() for value in values):
            raise ValueError("Numeric result and bounds must be finite")
        if self.numeric_value is not None:
            try:
                entered_value = Decimal(self.value_text)
            except Exception as exc:
                raise ValueError("Numeric results must use a plain numeric value") from exc
            if not entered_value.is_finite() or entered_value != self.numeric_value:
                raise ValueError("Numeric value must match the displayed result")
        if (
            self.reference_low is not None
            and self.reference_high is not None
            and self.reference_low > self.reference_high
        ):
            raise ValueError("Reference lower bound exceeds upper bound")
        return self


class LabResultUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    test_name: str | None = Field(default=None, min_length=1, max_length=256)
    value_text: str | None = Field(default=None, min_length=1, max_length=256)
    numeric_value: Decimal | None = None
    unit: str | None = Field(default=None, max_length=64)
    reference_low: Decimal | None = None
    reference_high: Decimal | None = None
    reference_text: str | None = Field(default=None, max_length=256)
    lab_flag: str | None = Field(default=None, max_length=64)
    page_number: int | None = Field(default=None, ge=1)


class LabResultResponse(BaseModel):
    id: str
    test_name: str
    value_text: str
    numeric_value: Decimal | None
    unit: str | None
    reference_low: Decimal | None
    reference_high: Decimal | None
    reference_text: str | None
    lab_flag: str | None
    page_number: int | None
    review_status: str
    range_status: str | None
