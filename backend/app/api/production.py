from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..db import get_db
from ..models import MovementKind, ProductionRecord, Quarry, StorageSite, User
from ..schemas import ProductionIn, ProductionOut
from ..security import STOCK_EDIT, STOCK_READ, require
from ..services import stock

router = APIRouter(prefix="/api/production", tags=["Добыча и остатки"])


def to_out(r: ProductionRecord) -> ProductionOut:
    return ProductionOut(id=r.id, shift_date=r.shift_date, quarry_name=r.quarry.name,
                         product_name=r.quarry.site.product.name, volume_m3=r.volume_m3,
                         author=r.author.full_name if r.author else None)


@router.get("", response_model=list[ProductionOut], dependencies=[Depends(require(*STOCK_READ))])
def journal(limit: int = 50, db: Session = Depends(get_db)):
    rows = db.scalars(select(ProductionRecord).options(
        joinedload(ProductionRecord.quarry).joinedload(Quarry.site).joinedload(StorageSite.product),
        joinedload(ProductionRecord.author)).order_by(ProductionRecord.shift_date.desc(), ProductionRecord.id.desc())
        .limit(limit)).all()
    return [to_out(r) for r in rows]


@router.post("", response_model=ProductionOut, status_code=201, summary="Ввести добычу за смену")
def add(data: ProductionIn, db: Session = Depends(get_db), user: User = Depends(require(*STOCK_EDIT))):
    quarry = db.get(Quarry, data.quarry_id)
    if quarry is None or not quarry.is_active:
        raise HTTPException(404, "Карьер не найден")
    rec = ProductionRecord(quarry_id=quarry.id, shift_date=data.shift_date, volume_m3=data.volume_m3, entered_by=user.id)
    db.add(rec)
    db.flush()
    # приход на площадку того же вида песка; при переполнении вся транзакция откатывается
    stock.add_movement(db, quarry.site_id, MovementKind.production, data.volume_m3, production_id=rec.id)
    db.commit()
    db.refresh(rec)
    return to_out(rec)
