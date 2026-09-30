from decimal import Decimal

import pytest

from receipt_sender import InvoiceRequest, LiveEvent, PlayerAsset, invoice_html, issue_invoice


def test_only_approved_assets_and_completed_events_are_billed(monkeypatch):
    invoice = InvoiceRequest(
        "GAME-42",
        "player@example.com",
        (PlayerAsset("Approved skin", Decimal("12.50"), "approved"),
         PlayerAsset("Pending map", Decimal("900"), "pending")),
        (LiveEvent("Finished tournament", Decimal("7.25"), "completed"),
         LiveEvent("Upcoming season", Decimal("80"), "scheduled")),
    )
    calls = []

    def fake_post(path, payload, operation_id):
        calls.append((path, payload, operation_id))
        return {"url": "https://example.com/invoice.pdf"} if len(calls) == 1 else {"message_id": "msg_42"}

    monkeypatch.setattr("receipt_sender.post", fake_post)
    assert issue_invoice(invoice) == "msg_42"
    html = calls[0][1]["html"]
    assert "Approved skin" in html and "Finished tournament" in html and "19.75" in html
    assert "Pending map" not in html and "Upcoming season" not in html
    assert calls[1][1]["body"].endswith("https://example.com/invoice.pdf")
    assert calls[0][2] != calls[1][2]


def test_empty_billable_invoice_is_rejected():
    invoice = InvoiceRequest("GAME-43", "player@example.com", (), ())
    with pytest.raises(ValueError, match="no billable lines"):
        invoice_html(invoice)
