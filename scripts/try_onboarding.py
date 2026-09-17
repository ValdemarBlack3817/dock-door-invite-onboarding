import asyncio
import json

from dockdoor.models import OnboardingRequest
from dockdoor.onboarding import OnboardingDesk


async def main() -> None:
    request = OnboardingRequest.model_validate(
        {
            "enrollment_id": "enroll-storefront-1042",
            "email": "ops@harbor-shop.example",
            "display_name": "Harbor Shop Dispatch",
            "invite_code": "DOCK-42",
            "captcha_token": "local-script-token",
            "first_shipment_event": {
                "shipment_id": "ship-1042",
                "kind": "delivered",
                "occurred_at": "2026-09-03T09:30:00Z",
                "proof": {
                    "file_id": "pod-1042",
                    "filename": "signed-receipt.jpg",
                    "sha256": "a" * 64,
                },
            },
        }
    )

    async def accept_local_captcha(token: str) -> dict[str, object]:
        return {"verified": bool(token)}

    desk = OnboardingDesk({"DOCK-42"}, accept_local_captcha)
    result = await desk.enroll(request)
    print(json.dumps(result.model_dump(mode="json"), indent=2))


if __name__ == "__main__":
    asyncio.run(main())

