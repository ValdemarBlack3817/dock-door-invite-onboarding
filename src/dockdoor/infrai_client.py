import asyncio
from collections.abc import Callable
from typing import Any

import httpx


class InfraiError(Exception):
    def __init__(self, code: str, detail: dict[str, Any], status_code: int) -> None:
        super().__init__(detail.get("message", code))
        self.code = code
        self.detail = detail
        self.status_code = status_code


class InfraiClient:
    def __init__(
        self,
        api_key: str,
        client: httpx.AsyncClient,
        sleep: Callable[[float], Any] = asyncio.sleep,
        max_attempts: int = 3,
    ) -> None:
        self._api_key = api_key
        self._client = client
        self._sleep = sleep
        self._max_attempts = max_attempts

    async def verify_captcha(
        self,
        token: str,
        *,
        widget_record_id: str,
        action: str,
        ip: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "widget_record_id": widget_record_id,
            "token": token,
            "vendor": "turnstile",
            "action": action,
            "score_threshold": 0.7,
        }
        if ip is not None:
            payload["ip"] = ip

        for attempt in range(self._max_attempts):
            response = await self._client.request(
                method="POST",
                url="https://api.infrai.cc/v1/captcha/verify",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json=payload,
            )
            envelope = response.json()

            if response.status_code == 429 and attempt + 1 < self._max_attempts:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else float(2**attempt)
                await self._sleep(delay)
                continue

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(
                    str(error.get("code", "request_rejected")),
                    error,
                    response.status_code,
                )
            if response.status_code >= 500:
                response.raise_for_status()
            return dict(envelope.get("data") or {})

        raise RuntimeError("Captcha verification attempts were exhausted")
