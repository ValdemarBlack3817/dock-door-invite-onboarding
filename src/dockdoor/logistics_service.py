import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Request

from .infrai_client import InfraiClient, InfraiError
from .models import OnboardingRequest, OnboardingResult
from .onboarding import InviteCodeRejected, OnboardingDesk


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Set {name} before starting the service")
    return value


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    api_key = _required_env("INFRAI_API_KEY")
    invite_codes = {
        code.strip()
        for code in _required_env("LOGISTICS_INVITE_CODES").split(",")
        if code.strip()
    }
    async with httpx.AsyncClient() as http_client:
        infrai = InfraiClient(api_key=api_key, client=http_client)

        async def verify(token: str) -> dict[str, object]:
            return await infrai.verify_captcha(
                token,
                widget_record_id="community_onboarding",
                action="community_onboarding",
            )

        app.state.onboarding = OnboardingDesk(invite_codes, verify)
        yield


app = FastAPI(title="Dock Door Onboarding", lifespan=lifespan)


@app.post("/onboarding", response_model=OnboardingResult, status_code=201)
async def create_membership(payload: OnboardingRequest, request: Request) -> OnboardingResult:
    desk: OnboardingDesk = request.app.state.onboarding
    try:
        return await desk.enroll(payload)
    except InviteCodeRejected as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except InfraiError as exc:
        caller_status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(
            status_code=caller_status,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc
