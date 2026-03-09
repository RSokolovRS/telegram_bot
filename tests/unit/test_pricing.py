from app.domain.enums import SubscriptionPlan
from app.services.payment_service import PaymentService


def test_plan_price_month() -> None:
    assert PaymentService.plan_price(SubscriptionPlan.MONTH) == 100


def test_plan_price_year() -> None:
    assert PaymentService.plan_price(SubscriptionPlan.YEAR) == 1000
