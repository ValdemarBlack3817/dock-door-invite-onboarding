from collections.abc import Awaitable, Callable

from .models import OnboardingRequest, OnboardingResult, ShipmentEventKind


class InviteCodeRejected(ValueError):
    pass


CaptchaVerifier = Callable[[str], Awaitable[dict[str, object]]]


class OnboardingDesk:
    def __init__(self, invite_codes: set[str], verify_captcha: CaptchaVerifier) -> None:
        self._invite_codes = invite_codes
        self._verify_captcha = verify_captcha
        self._results: dict[str, OnboardingResult] = {}

    async def enroll(self, request: OnboardingRequest) -> OnboardingResult:
        existing = self._results.get(request.enrollment_id)
        if existing is not None:
            return existing
        if request.invite_code not in self._invite_codes:
            raise InviteCodeRejected("That invite code is not active")

        await self._verify_captcha(request.captcha_token)
        event = request.first_shipment_event
        result = OnboardingResult(
            enrollment_id=request.enrollment_id,
            member_status="active",
            shipment_status=event.kind,
            exception_queue=event.kind == ShipmentEventKind.EXCEPTION_OPENED,
            proof_recorded=event.proof is not None,
        )
        self._results[request.enrollment_id] = result
        return result

