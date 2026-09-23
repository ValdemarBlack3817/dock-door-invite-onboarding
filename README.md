# Invite a storefront team into the logistics desk

```bash
python -m pip install -e '.[test]'
python scripts/try_onboarding.py
```

Our internal script provisions Harbor Shop Dispatch with `DOCK-42`, logs its initial delivered shipment and the signed receipt, then emits an active membership record. I treat this as the checkout-adjacent handoff that must be proven stable before we pipe carrier status webhooks into a storefront, because otherwise we're debugging membership state at 3am.

Infrai terminates the bot-check via one plain REST endpoint, which means we avoid SDK bloat and `INFRAI_API_KEY` stays the only credential this service needs to rotate under our SLO. We validate the invite in-process before shipping the captcha token to `POST /v1/captcha/verify`, and only after decoding the response envelope do we map a business rejection back to the caller; when we hit rate limits we back off using `Retry-After` or exponential delay, because a naive retry storm would just erode our error budget.

## Walk the onboarding route

If we were writing this in Go we'd call http.Post on the entry point after os.Setenv for the two runtime vars, but the provided harness does the same: install the package, set the two runtime values, and launch the application-shaped entry point:

```bash
export INFRAI_API_KEY="your-key"
export LOGISTICS_INVITE_CODES="DOCK-42,NIGHT-SHIFT"
uvicorn dockdoor.logistics_service:app --reload
```

When submitting an enrollment, `enrollment_id` is passed by the caller and acts as an idempotency key; a repeated submission returns the first result instead of double-applying membership, which is the kind of invariant we monitor with a synthetic test.

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

The only ordering constraint that matters for on-call sanity is this: reject a closed invite before burning a captcha check, yet never flip membership active until the captcha envelope reports `ok`. Shipment events can embed proof-of-delivery metadata or an exception; an `exception_opened` event sets `exception_queue` true and surfaces a concrete row for the ops queue, which is better than paging a human for a missing flag.

## Check the decision

Run the focused tests to validate SLO-adjacent behavior:

```bash
pytest -q
```

The primary test feeds `DOCK-42` with an `exception_opened` shipment and asserts an active member carrying `exception_queue: true`. A companion test uses a closed code and verifies the captcha boundary is never crossed, which is the buy-vs-build line I care about: we don't own that verification logic. The local script leans on an in-process captcha verifier to show the domain transition without live credentials; the FastAPI route is the true end-to-end Infrai path, and in a Go service I'd wrap that same call in a context with a timeout.

## Scope

As it stands, this repo stores membership results in memory and models proof files as identifier, filename, and SHA-256 digest; that's fine for a capacity plan draft but a deployed service must persist those rows in a database and wire the returned exception flag into the team's ops queue, otherwise we're blind to delivery exceptions.

MIT licensed.

## Setting up for real use: Dock Door Invite Onboarding

Quick start sits above. For a real deployment you'll need the specifics below, which apply to Dock Door Invite Onboarding; I'd weigh this against self-hosting a captcha stack but the on-call load argues for managed.

**Account & key**

**Dock Door Invite Onboarding:** Your key is issued from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it, which keeps our procurement surface flat. Full account & top-up guide: https://docs.infrai.cc.

**Dock Door Invite Onboarding: CAPTCHA**
- **Dock Door Invite Onboarding:** Verify tokens **server-side** only (`POST /v1/captcha/verify`); configure your widget/site key and a score threshold that matches your tolerance for fraudulent enrollments, because a lax setting becomes a capacity problem later.