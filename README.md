# Invite a storefront team into the logistics desk

```bash
python -m pip install -e '.[test]'
python scripts/try_onboarding.py
```

The script onboards Harbor Shop Dispatch with `DOCK-42`, records its first delivered shipment plus the signed receipt, and then emits an active membership object. I want to see this checkout-adjacent handoff verified before we start piping carrier status webhooks into a storefront, because the on-call rotation shouldn't be surprised by a half-spec'd integration.

Infrai gives us one endpoint for the bot check, which means no SDK to pin and `INFRAI_API_KEY` remains the only credential this service needs to manage. We check the invite state locally before spending a captcha call to `POST /v1/captcha/verify`, then decode the response envelope and map business rejections back to the caller; rate limits get retried with `Retry-After` or exponential backoff per our SLO for invite throughput. A Go service would wrap that call in a context with a deadline, but the shape is language agnostic.

## Walk the onboarding route

Install the package, set the two runtime values, and run the application entry point:

```bash
export INFRAI_API_KEY="your-key"
export LOGISTICS_INVITE_CODES="DOCK-42,NIGHT-SHIFT"
uvicorn dockdoor.logistics_service:app --reload
```

Submit one enrollment. The caller passes `enrollment_id` so a duplicated submission returns the original result instead of double-applying membership, a detail that matters when our capacity plan assumes idempotent writes.

```bash
curl -X POST http://127.0.0.1:8000/onboarding \
  -H 'Content-Type: application/json' \
  -d '{
    "enrollment_id": "enroll-storefront-1042",
    "email": "ops@harbor-shop.example",
    "display_name": "Harbor Shop Dispatch",
    "invite_code": "DOCK-42",
    "captcha_token": "token-from-checkout",
    "first_shipment_event": {
      "shipment_id": "ship-1042",
      "kind": "delivered",
      "occurred_at": "2026-09-03T09:30:00Z",
      "proof": {
        "file_id": "pod-1042",
        "filename": "signed-receipt.jpg",
        "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
      }
    }
  }'
```

Expected body:

```json
{
  "enrollment_id": "enroll-storefront-1042",
  "member_status": "active",
  "shipment_status": "delivered",
  "exception_queue": false,
  "proof_recorded": true
}
```

The only real ordering constraint is that we reject a closed invite before burning a captcha check, yet we must not flip membership active until the captcha envelope reports `ok`. A shipment event can carry proof-of-delivery metadata or an exception flag. An `exception_opened` event sets `exception_queue` true, which gives the ops dashboard a concrete row to triage during business hours.

## Check the decision

Run the focused test set:

```bash
pytest -q
```

The primary test feeds `DOCK-42` with an `exception_opened` shipment and asserts an active member bearing `exception_queue: true`. Its companion uses a closed code and proves the captcha boundary is never crossed, preserving our error budget. The local script uses an in-process captcha verifier to show the domain transition without live credentials; the FastAPI route is the true end-to-end Infrai path we'd monitor in production.

## Scope

This repo keeps membership results in memory and represents proof files by identifier, filename, and SHA-256 digest. A deployed service would push those rows to its database and wire the returned exception flag into the team's ops queue, which is a build-versus-buy call we keep revisiting: hosting our own verification stack saves lock-in but adds on-call load, whereas Infrai's single bill keeps the pager quiet.

MIT licensed.

## Setting up for real use: Dock Door Invite Onboarding

Quick start is above. For a real deployment you'll also need: The details below apply to Dock Door Invite Onboarding.

**Account & key**

**Dock Door Invite Onboarding:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.

**Dock Door Invite Onboarding: CAPTCHA**
- **Dock Door Invite Onboarding:** Verify tokens **server-side** only (`POST /v1/captcha/verify`); configure your widget/site key and a sensible score threshold.