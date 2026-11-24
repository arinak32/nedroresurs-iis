from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from ..db import get_db
from ..models import Client, DeliveryMethod, Order, OrderSource, OrderStatus, User
from ..schemas import OrderIn, OrderOut, OrdersPage, QuoteOut, StatusAction
from ..security import ORDERS_EDIT, ORDERS_READ, require
from ..services import orders as svc

router = APIRouter(prefix="/api/orders", tags=["Заказы"])


def to_out(o: Order) -> OrderOut:
    return OrderOut(
        id=o.id, number=o.number, client_id=o.client_id, client_name=o.client.name, product_id=o.product_id,
        product_name=o.product.name, volume_m3=o.volume_m3, method=o.method,
        address=o.address.address if o.address else None, distance_km=o.distance_km, desired_date=o.desired_date,
        price_m3=o.price_m3, delivery_m3=o.delivery_m3, amount=o.amount, vat=o.vat, vat_rate=o.vat_rate,
        source=o.source, procurement_no=o.procurement_no,
        contract_number=o.contract.number if o.contract else None, status=o.status, created_at=o.created_at)


@router.get("/quote", response_model=QuoteOut, summary="Расчёт цены и проверка остатка до сохранения заказа",
            dependencies=[Depends(require(*ORDERS_EDIT))])
def quote(product_id: int, volume_m3: Decimal, method: DeliveryMethod, address_id: int | None = None,
          distance_km: Decimal | None = None, contract_id: int | None = None, client_id: int | None = None,
          db: Session = Depends(get_db)):
    return svc.quote(db, product_id, volume_m3, method, address_id, distance_km, contract_id, client_id)


@router.get("", response_model=OrdersPage, dependencies=[Depends(require(*ORDERS_READ))])
def list_orders(status: OrderStatus | None = None, product_id: int | None = None, source: OrderSource | None = None,
                q: str | None = None, date_from: date | None = None, date_to: date | None = None,
                limit: int = Query(50, le=200), offset: int = 0, db: Session = Depends(get_db)):
    base = select(Order).join(Order.client)
    if product_id:
        base = base.where(Order.product_id == product_id)
    if source:
        base = base.where(Order.source == source)
    if q:
        base = base.where(or_(Client.name.ilike(f"%{q}%"), Order.number.ilike(f"%{q}%")))
    if date_from:
        base = base.where(func.date(Order.created_at) >= date_from)
    if date_to:
        base = base.where(func.date(Order.created_at) <= date_to)
    counts = {s.value: n for s, n in db.execute(
        base.with_only_columns(Order.status, func.count()).group_by(Order.status)).all()}
    stmt = base.where(Order.status == status) if status else base
    total = db.scalar(stmt.with_only_columns(func.count()))
    rows = db.scalars(stmt.options(joinedload(Order.client), joinedload(Order.product), joinedload(Order.address),
                                   joinedload(Order.contract)).order_by(Order.id.desc()).limit(limit).offset(offset)).all()
    return OrdersPage(items=[to_out(o) for o in rows], total=total, counts=counts)


@router.post("", response_model=OrderOut, status_code=201)
def create_order(data: OrderIn, db: Session = Depends(get_db), user: User = Depends(require(*ORDERS_EDIT))):
    order = svc.create(db, data, user)
    db.commit()
    db.refresh(order)
    return to_out(order)


@router.get("/{order_id}", response_model=OrderOut, dependencies=[Depends(require(*ORDERS_READ))])
def get_order(order_id: int, db: Session = Depends(get_db)):
    order = db.get(Order, order_id)
    if order is None:
        raise HTTPException(404, "Заказ не найден")
    return to_out(order)


@router.post("/{order_id}/status", response_model=OrderOut, summary="Переход статуса заказа",
             dependencies=[Depends(require(*ORDERS_EDIT))])
def change_status(order_id: int, data: StatusAction, db: Session = Depends(get_db)):
    order = db.scalar(select(Order).where(Order.id == order_id).with_for_update())
    if order is None:
        raise HTTPException(404, "Заказ не найден")
    svc.change_status(db, order, data.action)
    db.commit()
    db.refresh(order)
    return to_out(order)
