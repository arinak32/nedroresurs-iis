"""Тарифы и параметры системы, которые меняет администратор (экран «Настройки»)."""
from decimal import Decimal

from sqlalchemy.orm import Session

from ..models import Setting

DEFAULTS = {
    "delivery_step_km": "20",      # шаг тарифа: каждые 20 км пробега туда и обратно
    "delivery_step_price": "200",  # надбавка за шаг, руб./м³
    "vat_rate": "22",              # ставка НДС, %
    "truck_capacity_m3": "30",     # вместимость кузова самосвала
}


def get_all(db: Session) -> dict[str, Decimal]:
    stored = {s.key: s.value for s in db.query(Setting).all()}
    return {k: Decimal(stored.get(k, v)) for k, v in DEFAULTS.items()}


def set_values(db: Session, values: dict[str, Decimal]) -> None:
    for key, value in values.items():
        if key not in DEFAULTS:
            raise KeyError(key)
        row = db.get(Setting, key)
        if row is None:
            db.add(Setting(key=key, value=str(value)))
        else:
            row.value = str(value)
