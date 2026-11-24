"""Заказы: расчёт, создание и переходы статусов по диаграмме состояний (рисунок 2.3)."""
import math
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import (Client, ClientAddress, Contract, DeliveryMethod, MovementKind, Order, OrderStatus, Product,
                      User)
from . import pricing, settings_store, stock

S = OrderStatus
# действие → (из каких статусов, в какой статус)
TRANSITIONS = {
    "issue_invoice": ({S.new}, S.awaiting_payment),
    "confirm": ({S.new}, S.planning),
    "mark_paid": ({S.awaiting_payment}, S.planning),
    "pickup": ({S.planning}, S.shipped),
    "close": ({S.shipped}, S.done),
    "cancel": ({S.new, S.awaiting_payment, S.planning}, S.cancelled),
}


def quote(db: Session, product_id: int, volume: Decimal, method: DeliveryMethod,
          address_id: int | None = None, distance_km: Decimal | None = None, contract_id: int | None = None,
          client_id: int | None = None) -> dict:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(404, "Вид песка не найден")
    if volume <= 0:
        raise HTTPException(422, "Объём должен быть больше нуля")
    address = None
    if method == DeliveryMethod.delivery:
        if address_id is not None:
            address = db.get(ClientAddress, address_id)
            if address is None or (client_id is not None and address.client_id != client_id):
                raise HTTPException(422, "Адрес доставки не принадлежит клиенту")
            distance_km = address.distance_km
        if distance_km is None:
            raise HTTPException(422, "Для доставки укажите адрес или расстояние")
    else:
        distance_km = None
    contract = None
    if contract_id is not None:
        contract = db.get(Contract, contract_id)
        if contract is None or contract.product_id != product_id or (client_id and contract.client_id != client_id):
            raise HTTPException(422, "Договор не подходит: другой клиент или вид песка")
    cfg = settings_store.get_all(db)
    price = pricing.calculate(volume, product.price_m3, distance_km, method == DeliveryMethod.delivery,
                              cfg["delivery_step_km"], cfg["delivery_step_price"], cfg["vat_rate"],
                              contract.price_m3 if contract else None)
    site = stock.site_for_product(db, product_id)
    available = stock.site_volume(db, site.id)
    truck = cfg["truck_capacity_m3"]
    return {
        "distance_km": distance_km, "price_m3": price.price_m3, "delivery_m3": price.delivery_m3,
        "unit_total": price.unit_total, "amount": price.amount, "vat": price.vat, "vat_rate": cfg["vat_rate"],
        "tariff_steps": price.steps, "site_id": site.id, "site_name": site.name, "available_m3": available,
        "enough": available >= volume, "trips_needed": math.ceil(volume / truck) if method == DeliveryMethod.delivery else 0,
    }


def create(db: Session, data, user: User) -> Order:
    if db.get(Client, data.client_id) is None:
        raise HTTPException(404, "Клиент не найден")
    q = quote(db, data.product_id, data.volume_m3, data.method, data.address_id, data.distance_km,
              data.contract_id, data.client_id)
    order = Order(client_id=data.client_id, contract_id=data.contract_id, product_id=data.product_id,
                  address_id=data.address_id if data.method == DeliveryMethod.delivery else None,
                  volume_m3=data.volume_m3, method=data.method, desired_date=data.desired_date,
                  distance_km=q["distance_km"], price_m3=q["price_m3"], delivery_m3=q["delivery_m3"],
                  amount=q["amount"], vat=q["vat"], vat_rate=q["vat_rate"], source=data.source,
                  procurement_no=data.procurement_no, comment=data.comment, created_by=user.id)
    db.add(order)
    db.flush()
    order.number = f"З-{order.id}"
    return order


def change_status(db: Session, order: Order, action: str) -> Order:
    if action not in TRANSITIONS:
        raise HTTPException(422, "Неизвестное действие")
    allowed, target = TRANSITIONS[action]
    if order.status not in allowed:
        raise HTTPException(409, f"Действие недоступно для заказа в статусе «{STATUS_RU[order.status]}»")
    if action == "pickup":
        if order.method != DeliveryMethod.pickup:
            raise HTTPException(409, "Отгрузка в транспорт клиента возможна только для самовывоза")
        site = stock.site_for_product(db, order.product_id)
        stock.add_movement(db, site.id, MovementKind.shipment, -Decimal(order.volume_m3), order_id=order.id,
                           comment=f"Самовывоз по заказу {order.number}")
    order.status = target
    return order


STATUS_RU = {S.new: "Новый", S.awaiting_payment: "Ждёт оплаты", S.planning: "Планирование",
             S.in_delivery: "В доставке", S.shipped: "Отгружен", S.done: "Выполнен", S.cancelled: "Отменён"}
