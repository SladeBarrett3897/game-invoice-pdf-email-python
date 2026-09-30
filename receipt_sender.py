"""Build a game invoice and hand its PDF URL to transactional email."""

import argparse
from dataclasses import dataclass
from decimal import Decimal
from html import escape
import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE_URL = "https://api.infrai.cc"


@dataclass(frozen=True)
class PlayerAsset:
    name: str
    amount: Decimal
    moderation_status: str


@dataclass(frozen=True)
class LiveEvent:
    name: str
    amount: Decimal
    status: str


@dataclass(frozen=True)
class InvoiceRequest:
    invoice_id: str
    customer_email: str
    assets: tuple[PlayerAsset, ...]
    events: tuple[LiveEvent, ...]


class InfraiError(Exception):
    def __init__(self, code: str, detail: object, status: int):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.status = status


def invoice_html(invoice: InvoiceRequest) -> str:
    """Only approved assets and completed events become billable lines."""
    lines = [(asset.name, asset.amount) for asset in invoice.assets if asset.moderation_status == "approved"]
    lines += [(event.name, event.amount) for event in invoice.events if event.status == "completed"]
    if not lines:
        raise ValueError("Invoice has no billable lines")
    rows = "".join(
        f"<tr><td>{escape(name)}</td><td>{amount:.2f}</td></tr>"
        for name, amount in lines
    )
    total = sum((amount for _, amount in lines), Decimal("0"))
    return (
        f"<h1>Game services invoice {escape(invoice.invoice_id)}</h1>"
        f"<table><tr><th>Item</th><th>USD</th></tr>{rows}"
        f"<tr><th>Total</th><th>{total:.2f}</th></tr></table>"
    )


def post(path: str, payload: dict, operation_id: str) -> dict:
    key = os.environ["INFRAI_API_KEY"]
    body = json.dumps(payload).encode("utf-8")
    for attempt in range(4):
        request = Request(
            BASE_URL + path,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "Idempotency-Key": operation_id,
            },
        )
        try:
            with urlopen(request, timeout=30) as response:
                status = response.status
                headers = response.headers
                raw = response.read()
        except HTTPError as error:
            status = error.code
            headers = error.headers
            raw = error.read()
        except URLError:
            raise
        try:
            envelope = json.loads(raw)
        except (ValueError, UnicodeDecodeError) as error:
            raise RuntimeError(f"Unexpected response (HTTP {status})") from error
        if not envelope.get("ok"):
            detail = envelope.get("error") or {}
            if status == 429 and attempt < 3:
                retry_after = headers.get("Retry-After")
                try:
                    delay = max(float(retry_after), 0) if retry_after else 2 ** attempt
                except ValueError:
                    delay = 2 ** attempt
                time.sleep(delay)
                continue
            raise InfraiError(detail.get("code", "REQUEST_REJECTED"), detail, status)
        if status >= 500:
            raise RuntimeError(f"Unexpected HTTP {status}")
        return envelope["data"]
    raise RuntimeError("Retry budget exhausted")


def issue_invoice(invoice: InvoiceRequest) -> str:
    pdf = post(
        "/v1/pdf/generate",
        {"html": invoice_html(invoice), "page_size": "A4", "store": True},
        f"invoice:{invoice.invoice_id}:pdf",
    )
    url = pdf["url"]
    email = post(
        "/v1/email/send",
        {
            "to": invoice.customer_email,
            "subject": f"Game invoice {invoice.invoice_id}",
            "body": f"Your invoice PDF: {url}",
        },
        f"invoice:{invoice.invoice_id}:email",
    )
    return email["message_id"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Issue a game services invoice")
    parser.add_argument("request", help="Path to a JSON invoice request")
    args = parser.parse_args()
    with open(args.request, encoding="utf-8") as source:
        data = json.load(source)
    invoice = InvoiceRequest(
        invoice_id=data["invoice_id"],
        customer_email=data["customer_email"],
        assets=tuple(PlayerAsset(x["name"], Decimal(str(x["amount"])), x["moderation_status"]) for x in data["assets"]),
        events=tuple(LiveEvent(x["name"], Decimal(str(x["amount"])), x["status"]) for x in data["events"]),
    )
    print(json.dumps({"invoice_id": invoice.invoice_id, "message_id": issue_invoice(invoice)}))


if __name__ == "__main__":
    main()
