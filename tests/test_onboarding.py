import asyncio

import pytest

from dockdoor.models import OnboardingRequest
from dockdoor.onboarding import InviteCodeRejected, OnboardingDesk


def onboarding_request(invite_code: str = "DOCK-42") -> OnboardingRequest:
    return OnboardingRequest.model_validate(
        {
            "enrollment_id": "enroll-1042",
            "email": "ops@harbor-shop.example",
            "display_name": "Harbor Shop Dispatch",
            "invite_code": invite_code,
            "captcha_token": "captcha-token",
            "first_shipment_event": {
                "shipment_id": "ship-1042",
                "kind": "exception_opened",
                "occurred_at": "2026-09-03T09:30:00Z",
                "exception": {
                    "code": "ADDRESS_REVIEW",
                    "note": "Confirm the receiving dock number",
                },
            },
        }
    )


def test_valid_invite_activates_member_and_routes_exception() -> None:
    seen_tokens: list[str] = []

    async def verify(token: str) -> dict[str, object]:
        seen_tokens.append(token)
        return {"verified": True}

    desk = OnboardingDesk({"DOCK-42"}, verify)
    result = asyncio.run(desk.enroll(onboarding_request()))

    assert result.member_status == "active"
    assert result.exception_queue is True
    assert result.proof_recorded is False
    assert seen_tokens == ["captcha-token"]


def test_invalid_invite_stops_before_captcha() -> None:
    calls = 0

    async def verify(token: str) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"verified": True}

    desk = OnboardingDesk({"DOCK-42"}, verify)
    with pytest.raises(InviteCodeRejected):
        asyncio.run(desk.enroll(onboarding_request("CLOSED-CODE")))

    assert calls == 0

