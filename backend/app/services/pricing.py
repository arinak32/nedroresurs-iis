"""Расчёт цены песка с доставкой — формула (2.1): c = p + a · ⌈2d / l⌉."""
import math
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")


@dataclass
class Price:
    price_m3: Decimal      # цена песка за 1 м³
    delivery_m3: Decimal   # надбавка за доставку на 1 м³
    unit_total: Decimal    # итого за 1 м³
    amount: Decimal        # сумма заказа с НДС
    vat: Decimal           # в т. ч. НДС
    steps: int             # число шагов тарифа


def delivery_steps(distance_km: Decimal | float, step_km: Decimal) -> int:
    """Число шагов тарифа: пробег туда и обратно (2d), делённый на шаг, с округлением вверх."""
    d = Decimal(str(distance_km))
    if d <= 0:
        return 0
    return math.ceil((2 * d) / step_km)


def vat_included(amount: Decimal, rate: Decimal) -> Decimal:
    """НДС, включённый в сумму: S · r / (100 + r)."""
    return (amount * rate / (Decimal(100) + rate)).quantize(CENT, ROUND_HALF_UP)


def calculate(volume_m3: Decimal, product_price: Decimal, distance_km: Decimal | None, is_delivery: bool,
              step_km: Decimal, step_price: Decimal, vat_rate: Decimal,
              contract_price: Decimal | None = None) -> Price:
    volume = Decimal(str(volume_m3))
    if contract_price is not None:
        # по договору цена указана сразу с доставкой
        unit, delivery, steps, base = Decimal(contract_price), Decimal(0), 0, Decimal(contract_price)
    else:
        steps = delivery_steps(distance_km or 0, step_km) if is_delivery else 0
        delivery = step_price * steps
        base = Decimal(product_price)
        unit = base + delivery
    amount = (unit * volume).quantize(CENT, ROUND_HALF_UP)
    return Price(base, delivery, unit, amount, vat_included(amount, vat_rate), steps)
