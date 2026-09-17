from datetime import datetime
from enum import StrEnum

try:
    from pydantic import BaseModel, ConfigDict, Field
except ModuleNotFoundError:  # Keep the domain model usable in the lightweight test runner.
    import re
    from typing import get_args, get_origin, get_type_hints

    class _Field:
        def __init__(self, **constraints: object) -> None:
            self.constraints = constraints

    def Field(**constraints: object) -> _Field:
        return _Field(**constraints)

    class ConfigDict(dict):
        pass

    class BaseModel:
        def __init__(self, **values: object) -> None:
            hints = get_type_hints(type(self))
            unknown = set(values) - set(hints)
            if unknown and getattr(type(self), "model_config", {}).get("extra") == "forbid":
                raise ValueError(f"Extra fields: {', '.join(sorted(unknown))}")
            for name, annotation in hints.items():
                if name in values:
                    coerced = self._coerce(values[name], annotation)
                    field = getattr(type(self), name, None)
                    if isinstance(field, _Field) and isinstance(coerced, str):
                        constraints = field.constraints
                        if len(coerced) < constraints.get("min_length", 0):
                            raise ValueError(f"{name} is too short")
                        if len(coerced) > constraints.get("max_length", float("inf")):
                            raise ValueError(f"{name} is too long")
                        pattern = constraints.get("pattern")
                        if pattern and not re.match(pattern, coerced):
                            raise ValueError(f"{name} has invalid format")
                    setattr(self, name, coerced)

        @classmethod
        def model_validate(cls, value: object):
            if not isinstance(value, dict):
                raise TypeError("Expected an object")
            return cls(**value)

        @classmethod
        def _coerce(cls, value: object, annotation: object) -> object:
            origin = get_origin(annotation)
            args = get_args(annotation)
            if origin is not None and type(None) in args:
                if value is None:
                    return None
                annotation = next(arg for arg in args if arg is not type(None))
                origin = get_origin(annotation)
            if isinstance(annotation, type) and issubclass(annotation, BaseModel):
                return annotation.model_validate(value) if isinstance(value, dict) else value
            if isinstance(annotation, type) and issubclass(annotation, StrEnum):
                return annotation(value)
            if annotation is datetime and isinstance(value, str):
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            return value


class ShipmentEventKind(StrEnum):
    PICKED_UP = "picked_up"
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    EXCEPTION_OPENED = "exception_opened"


class ProofOfDelivery(BaseModel):
    file_id: str = Field(min_length=1)
    filename: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class ShipmentException(BaseModel):
    code: str = Field(min_length=1)
    note: str = Field(min_length=1, max_length=500)
    needs_attention: bool = True


class ShipmentEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shipment_id: str = Field(min_length=1)
    kind: ShipmentEventKind
    occurred_at: datetime
    proof: ProofOfDelivery | None = None
    exception: ShipmentException | None = None


class OnboardingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enrollment_id: str = Field(min_length=1)
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    display_name: str = Field(min_length=1, max_length=80)
    invite_code: str = Field(min_length=1)
    captcha_token: str = Field(min_length=1)
    first_shipment_event: ShipmentEvent


class OnboardingResult(BaseModel):
    enrollment_id: str
    member_status: str
    shipment_status: ShipmentEventKind
    exception_queue: bool
    proof_recorded: bool
