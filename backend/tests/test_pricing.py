from decimal import Decimal

from app.services.pricing import calculate, delivery_steps, vat_included

STEP, PRICE, VAT = Decimal(20), Decimal(200), Decimal(22)


def test_example_from_tariff_60km():
    # пример предприятия: 60 км → пробег 120 км → 6 × 200 = 1200 руб./м³, итого 1500 руб./м³
    p = calculate(Decimal(30), Decimal(300), Decimal(60), True, STEP, PRICE, VAT)
    assert p.steps == 6 and p.delivery_m3 == 1200 and p.unit_total == 1500 and p.amount == 45000


def test_steps_round_up():
    assert delivery_steps(Decimal(45), STEP) == 5   # 90 км → 4,5 шага → 5
    assert delivery_steps(Decimal(40), STEP) == 4   # ровно 80 км
    assert delivery_steps(Decimal("0.5"), STEP) == 1
    assert delivery_steps(0, STEP) == 0


def test_pickup_has_no_delivery_charge():
    p = calculate(Decimal(100), Decimal(300), Decimal(60), False, STEP, PRICE, VAT)
    assert p.delivery_m3 == 0 and p.amount == 30000


def test_contract_price_includes_delivery():
    p = calculate(Decimal(10), Decimal(300), Decimal(90), True, STEP, PRICE, VAT, contract_price=Decimal(1100))
    assert p.unit_total == 1100 and p.delivery_m3 == 0 and p.amount == 11000


def test_vat_22_included():
    assert vat_included(Decimal(1220), VAT) == Decimal("220.00")
    assert vat_included(Decimal(264000), VAT) == Decimal("47606.56")
