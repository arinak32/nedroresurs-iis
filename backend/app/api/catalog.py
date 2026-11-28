from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Product, Quarry, Role, StorageSite
from ..schemas import ProductOut, QuarryOut, SiteOut, Tariffs
from ..security import STOCK_READ, current_user, require
from ..services import settings_store, stock

router = APIRouter(prefix="/api", tags=["Справочники и настройки"])


@router.get("/products", response_model=list[ProductOut], dependencies=[Depends(current_user)])
def products(db: Session = Depends(get_db)):
    return db.scalars(select(Product).order_by(Product.id)).all()


@router.get("/quarries", response_model=list[QuarryOut], dependencies=[Depends(current_user)])
def quarries(db: Session = Depends(get_db)):
    return db.scalars(select(Quarry).where(Quarry.is_active).order_by(Quarry.id)).all()


@router.get("/stock", response_model=list[SiteOut], summary="Остатки и заполненность площадок",
            dependencies=[Depends(require(*STOCK_READ))])
def stock_view(db: Session = Depends(get_db)):
    out = []
    for s in db.scalars(select(StorageSite).order_by(StorageSite.id)):
        v = stock.site_volume(db, s.id)
        out.append(SiteOut(id=s.id, name=s.name, product_id=s.product_id, product_name=s.product.name,
                           capacity_m3=s.capacity_m3, volume_m3=v, fill_pct=round(float(v / s.capacity_m3 * 100), 1)))
    return out


@router.get("/settings/tariffs", response_model=Tariffs, dependencies=[Depends(current_user)])
def get_tariffs(db: Session = Depends(get_db)):
    cfg = settings_store.get_all(db)
    prices = {p.id: p.price_m3 for p in db.scalars(select(Product))}
    return Tariffs(**cfg, prices=prices)


@router.put("/settings/tariffs", response_model=Tariffs, dependencies=[Depends(require(Role.admin))])
def put_tariffs(data: Tariffs, db: Session = Depends(get_db)):
    settings_store.set_values(db, data.model_dump(exclude={"prices"}))
    for pid, price in data.prices.items():
        product = db.get(Product, pid)
        if product is not None:
            product.price_m3 = price
    db.commit()
    return get_tariffs(db)
