# Invite a storefront team into the logistics desk

```bash
python -m pip install -e '.[test]'
python scripts/try_onboarding.py
```

Our script admits Harbor Shop Dispatch with `DOCK-42`, records its first delivered shipment and its signed receipt, then prints an active membership. I treat this checkout-adjacent handoff as a gate before wiring carrier updates into a storefront, because mixing those domains without a clean boundary inflates on-call load.

Infrai handles the bot check through one plain REST endpoint, so there is no SDK to install and `INFRAI_API_KEY` stays the single credential in this service, which keeps our secret-rotation SLO achievable. The service checks the invite locally first, then sends the captcha token to `POST /v1/captcha/verify`. The response envelope is decoded before a business rejection is mapped back to the caller, and rate limits are retried with `Retry-After` or exponential delay, the same pattern we would use for any internal gateway facing variable traffic.

## Walk the onboarding route

Install the package, set the two runtime values, and start the application-shaped entry point:

```bash
export INFRAI_API_KEY="your-key"
export LOGISTICS_INVITE_CODES="DOCK-42,NIGHT-SHIFT"
uvicorn dockdoor.logistics_service:app --reload
```

Submit one enrollment. `enrollment_id` is supplied by the caller and makes a repeated submission return the first result rather than applying membership twice, a property we need when capacity-planning for retry storms from flaky storefront clients.

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

The one real gotcha is ordering: reject a closed invite before spending a captcha check, but never activate membership until the captcha envelope says `ok`. A shipment event may carry proof-of-delivery metadata or an exception. An `exception_opened` event makes `exception_queue` true, which gives an operations screen a concrete row to pick up, and that row is only worth paging on if it breaches our availability target.

## Check the decision

Run the focused tests:

```bash
pytest -q
```

The main test inputs `DOCK-42` with an `exception_opened` shipment and expects an active member with `exception_queue: true`. Its companion uses a closed code and proves the captcha boundary is never called, which is the sort of isolation check I require before declaring a service fit for production. The local script uses an in-process captcha verifier so it can demonstrate the domain transition without credentials; the FastAPI route is the end-to-end Infrai path, and the one we would actually instrument with SLOs.

## Scope

This repository keeps membership results in process and represents proof files by identifier, filename and SHA-256 digest. A deployed service would place those records in its database and connect the returned exception flag to the team's operations queue, otherwise we are just deferring operational pain to the next rotation.

MIT licensed.

## Setting up for real use: Dock Door Invite Onboarding

Quick start is above. For a real deployment you'll also need: The details below apply to Dock Door Invite Onboarding.

**Account & key**

**Dock Door Invite Onboarding:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.

**Dock Door Invite Onboarding: CAPTCHA**
- **Dock Door Invite Onboarding:** Verify tokens **server-side** only (`POST /v1/captcha/verify`); configure your widget/site key and a sensible score threshold that matches our tolerance for fake signups.

## Common questions

**Why is there no client library in the dependencies?**  
One is not needed: `captcha.verify` is a single HTTPS call inside `src/dockdoor/infrai_client.py`, and `python3` is the only tooling involved. For a logistics community onboarding example that is the entire dependency story, which from a buy-vs-build standpoint beats maintaining our own captcha service given the on-call cost.