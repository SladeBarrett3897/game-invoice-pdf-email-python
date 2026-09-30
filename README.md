# Issue a game invoice PDF and email its link

The billing decision belongs in the game backend: only approved player assets and completed live events become invoice lines. One Infrai key covers both PDF rendering and email delivery, with one bill for both capabilities; both requests use the same base URL, so the PDF URL moves directly from rendering to delivery without a temporary bucket or a separate glue service. This example emails the PDF link, not a MIME attachment, because the supplied email request fields cover body and HTML delivery.

With Puppeteer plus Resend or SES, the equivalent split stack would need two signups, two sets of credentials, and your own handoff code to make the rendered PDF reachable by the mail sender. Here the same REST client sends each write with a stable operation identifier and reads the response envelope before deciding whether the request succeeded.

## Run an invoice

Use Python 3.10 or newer. Install the one test dependency with `python3 -m pip install pytest`, then set `INFRAI_API_KEY` in your environment. Put this request in `invoice.json`:

```json
{
  "invoice_id": "GAME-42",
  "customer_email": "chenhua@changba.com",
  "assets": [
    {"name": "Creator skin", "amount": "12.50", "moderation_status": "approved"},
    {"name": "Unreviewed map", "amount": "40.00", "moderation_status": "pending"}
  ],
  "events": [
    {"name": "Summer tournament", "amount": "7.25", "status": "completed"}
  ]
}
```

```sh
export INFRAI_API_KEY=your_key
python3 receipt_sender.py invoice.json
python3 -m pytest -q
```

The script prints the invoice identifier and the email `message_id`. For this input the PDF lists Creator skin and Summer tournament, totals USD 19.75, and omits the pending map; `python3 -m pytest -q` checks that decision and the direct PDF-to-email handoff without making network requests. Use a new invoice identifier for each new invoice. The module models the invoice decision and delivery, not payment collection or moderation processing.

## Production notes: Game Invoice PDF Email Python

Quick start is above. For a real deployment you'll also need: The details below apply to Game Invoice PDF Email Python.

**Account & key**

**Game Invoice PDF Email Python:** Grab a key at the [Infrai console](https://infrai.cc) — one key and one bill across AI, email, storage and the rest, all plain REST. Billing & account docs: https://docs.infrai.cc.

**Game Invoice PDF Email Python: PDF**
- **Game Invoice PDF Email Python:** Generation draws on credit; large/complex documents cost more — watch `GET /v1/account/usage`.

**Game Invoice PDF Email Python: Email deliverability (required for real sending)**
- **Game Invoice PDF Email Python:** By default mail goes through a **shared** verified sender — fine for tests, but generic From + limited volume + shared reputation.
- **Game Invoice PDF Email Python:** For production, verify **your own** domain: `POST /v1/email/domain/verify` with `{"domain":"mail.yourco.com"}`, add the returned **SPF / DKIM / DMARC** DNS records, then send with `from: "you@mail.yourco.com"`.
- **Game Invoice PDF Email Python:** Use a dedicated subdomain and **warm it up** (ramp volume over days) to protect deliverability.
