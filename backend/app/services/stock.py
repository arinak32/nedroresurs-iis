"""Остатки на площадках: сумма движений (раздел 2.3). Изменения — только в транзакции с блокировкой площадки."""
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import MovementKind, StockMovement, StorageSite


def site_volume(db: Session, site_id: int) -> Decimal:
    total = db.scalar(select(func.coalesce(func.sum(StockMovement.volume_m3), 0)).where(StockMovement.site_id == site_id))
    return Decimal(total)


def site_for_product(db: Session, product_id: int) -> StorageSite:
    site = db.scalar(select(StorageSite).where(StorageSite.product_id == product_id))
    if site is None:
        raise HTTPException(400, "Для этого вида песка не задана площадка хранения")
    return site


def lock_site(db: Session, site_id: int) -> StorageSite:
    return db.scalars(select(StorageSite).where(StorageSite.id == site_id).with_for_update()).one()


def add_movement(db: Session, site_id: int, kind: MovementKind, volume: Decimal, **refs) -> StockMovement:
    """Записать движение с проверкой: остаток не отрицательный и не больше вместимости."""
    site = lock_site(db, site_id)
    new_volume = site_volume(db, site_id) + volume
    if new_volume < 0:
        raise HTTPException(409, f"На площадке «{site.name}» недостаточно песка: не хватает {abs(new_volume):.0f} м³")
    if new_volume > site.capacity_m3:
        raise HTTPException(409, f"Площадка «{site.name}» переполнится: вместимость {site.capacity_m3:.0f} м³, "
                                 f"будет {new_volume:.0f} м³")
    mv = StockMovement(site_id=site_id, kind=kind, volume_m3=volume, **refs)
    db.add(mv)
    return mv
