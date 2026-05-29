"""Public Growth plan checkout from the marketing site."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.business_lead import BusinessLead
from app.services.stripe_service import CheckoutSessionResult


@patch("app.services.business_lead_checkout_service.stripe_service.create_growth_checkout_session")
def test_checkout_growth_redirects_to_stripe(
    mock_checkout,
    client: TestClient,
    db_session: Session,
) -> None:
    mock_checkout.return_value = CheckoutSessionResult(
        session_id="cs_public_test",
        url="https://checkout.stripe.com/c/pay/cs_public_test",
        customer_id="cus_public",
    )

    response = client.get("/checkout/growth", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "https://checkout.stripe.com/c/pay/cs_public_test"

    lead = db_session.query(BusinessLead).order_by(BusinessLead.created_at.desc()).first()
    assert lead is not None
    assert lead.source == "website_checkout"
    assert lead.status == "qualified"
    assert lead.payment_status == "checkout_created"
    assert lead.stripe_checkout_session_id == "cs_public_test"

    assert mock_checkout.called
    assert mock_checkout.call_args.kwargs.get("customer_email") is None


def test_landing_pricing_shows_checkout_buttons(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Buy Growth plan — $199 setup + $147/mo" in response.text
    assert response.text.count('href="/checkout/growth"') == 1


def test_landing_shows_cancel_message(client: TestClient) -> None:
    response = client.get("/?checkout=cancelled#pricing")
    assert response.status_code == 200
    assert "Checkout was cancelled" in response.text
