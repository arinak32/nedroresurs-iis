"""Рейсы: план на дату, ручная правка, утверждение и отметки водителя (глава 2, рисунки 2.2 и 2.4).

Планирование на этом этапе — базовый «ручной» вариант, близкий к текущей практике предприятия:
заказы берутся по очереди (срок → номер), каждый делится на рейсы по 30 м³, рейс отдаётся самосвалу
с наименьшей загрузкой смены. Оптимизация OR-Tools (раздел 2.6.3) заменит этот алгоритм на следующем этапе,
а базовый вариант останется для сравнения пробега.
"""
import math
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException
from sqlalchemy import Integer, cast, func, select
from sqlalchemy.orm import Session

from ..models import (DeliveryMethod, DocKind, Document, MovementKind, Order, OrderStatus, PlanStatus, Quarry,
                      RoutePlan, Trip, TripStatus, User, Vehicle, VehicleKind, VehicleStatus)
from . import pricing, settings_store, stock

SPEED_KMH = 45        # средняя скорость самосвала
LOAD_UNLOAD_H = 0.5   # погрузка и выгрузка за рейс
SHIFT_H = 12          # продолжительность смены
ACTIVE = (TripStatus.planned, TripStatus.en_route, TripStatus.delivered)


def trip_hours(distance_one_way_km: float) -> float:
    return 2 * distance_one_way_km / SPEED_KMH + LOAD_UNLOAD_H


def remaining_m3(db: Session, order: Order, exclude_plan_id: int | None = None) -> Decimal:
    """Объём заказа, ещё не распределённый по рейсам (доставленные считаются по факту)."""
    q = select(func.coalesce(func.sum(func.coalesce(Trip.actual_m3, Trip.planned_m3)), 0)).where(
        Trip.order_id == order.id, Trip.status.in_(ACTIVE))
    if exclude_plan_id is not None:
        q = q.where((Trip.plan_id != exclude_plan_id) | (Trip.plan_id.is_(None)))
    return Decimal(order.volume_m3) - Decimal(db.scalar(q))


def build_plan(db: Session, plan_date: date) -> tuple[RoutePlan, list[dict]]:
    """Рассчитать черновик плана на дату. Возвращает план и список рейсов, которые не поместились в смену."""
    if db.scalar(select(RoutePlan.id).where(RoutePlan.plan_date == plan_date, RoutePlan.status == PlanStatus.approved)):
        raise HTTPException(409, "План на эту дату уже утверждён")
    # старый черновик на ту же дату заменяется
    for old in db.scalars(select(RoutePlan).where(RoutePlan.plan_date == plan_date, RoutePlan.status == PlanStatus.draft)):
        for t in db.scalars(select(Trip).where(Trip.plan_id == old.id)):
            db.delete(t)
        db.flush()
        db.delete(old)
    db.flush()

    truck_cap = settings_store.get_all(db)["truck_capacity_m3"]
    trucks = db.scalars(select(Vehicle).where(Vehicle.kind == VehicleKind.dump_truck, Vehicle.status == VehicleStatus.on_line,
                                              Vehicle.driver_id.is_not(None)).order_by(Vehicle.id)).all()
    if not trucks:
        raise HTTPException(409, "Нет самосвалов на линии с закреплённым водителем")
    orders = db.scalars(select(Order).where(Order.method == DeliveryMethod.delivery,
                                            Order.status.in_([OrderStatus.planning, OrderStatus.in_delivery]),
                                            (Order.desired_date.is_(None)) | (Order.desired_date <= plan_date))
                        .order_by(Order.desired_date.asc().nullslast(), Order.id)).all()
    plan = RoutePlan(plan_date=plan_date, status=PlanStatus.draft)
    db.add(plan)
    db.flush()

    load = {t.id: 0.0 for t in trucks}   # часы смены
    seq = {t.id: 0 for t in trucks}
    total_km = Decimal(0)
    unplanned: list[dict] = []
    for order in orders:
        rest = remaining_m3(db, order)
        if rest <= 0:
            continue
        quarry = db.scalar(select(Quarry).where(Quarry.site_id == stock.site_for_product(db, order.product_id).id,
                                                Quarry.is_active).order_by(Quarry.id))
        d = float(order.distance_km or 0)
        hours = trip_hours(d)
        for _ in range(math.ceil(rest / truck_cap)):
            vol = min(truck_cap, rest)
            truck = min(trucks, key=lambda t: (load[t.id], t.id))
            if load[truck.id] + hours > SHIFT_H:
                unplanned.append({"order_id": order.id, "order_number": order.number, "volume_m3": vol})
                rest -= vol
                continue
            load[truck.id] += hours
            seq[truck.id] += 1
            km = Decimal(str(round(2 * d, 1)))
            db.add(Trip(plan_id=plan.id, order_id=order.id, vehicle_id=truck.id, driver_id=truck.driver_id,
                        quarry_id=quarry.id if quarry else None, seq=seq[truck.id], planned_m3=vol, distance_km=km))
            total_km += km
            rest -= vol
    plan.total_km = total_km
    plan.baseline_km = total_km
    db.flush()
    return plan, unplanned


def move_trip(db: Session, plan: RoutePlan, trip: Trip, vehicle_id: int) -> Trip:
    if plan.status != PlanStatus.draft:
        raise HTTPException(409, "Утверждённый план менять нельзя")
    truck = db.get(Vehicle, vehicle_id)
    if truck is None or truck.kind != VehicleKind.dump_truck or truck.status != VehicleStatus.on_line:
        raise HTTPException(422, "Самосвал недоступен для рейсов")
    last = db.scalar(select(func.coalesce(func.max(Trip.seq), 0)).where(Trip.plan_id == plan.id, Trip.vehicle_id == truck.id))
    trip.vehicle_id, trip.driver_id, trip.seq = truck.id, truck.driver_id, last + 1
    return trip


def approve(db: Session, plan: RoutePlan, user: User) -> RoutePlan:
    if plan.status != PlanStatus.draft:
        raise HTTPException(409, "План уже утверждён")
    plan.status, plan.approved_by = PlanStatus.approved, user.id
    return plan


# ── отметки водителя ──────────────────────────────────────────────

def _lock_own_trip(db: Session, trip_id: int, driver: User) -> Trip:
    trip = db.scalar(select(Trip).where(Trip.id == trip_id).with_for_update())
    if trip is None or trip.driver_id != driver.id:
        raise HTTPException(404, "Рейс не найден")
    plan = db.get(RoutePlan, trip.plan_id) if trip.plan_id else None
    if plan is None or plan.status != PlanStatus.approved:
        raise HTTPException(409, "План рейсов ещё не утверждён")
    return trip


def mark_loaded(db: Session, trip_id: int, driver: User, event_id: str | None) -> Trip:
    trip = _lock_own_trip(db, trip_id, driver)
    if trip.status == TripStatus.en_route and event_id and trip.client_event_id == event_id:
        return trip  # повтор той же отметки (плохая связь) — ничего не меняем
    if trip.status != TripStatus.planned:
        raise HTTPException(409, "Рейс уже отмечен")
    trip.status, trip.loaded_at, trip.client_event_id = TripStatus.en_route, datetime.now(timezone.utc), event_id
    order = db.scalar(select(Order).where(Order.id == trip.order_id).with_for_update())
    if order.status == OrderStatus.planning:
        order.status = OrderStatus.in_delivery
    return trip


def _next_number(db: Session, kind: DocKind) -> str:
    last = db.scalar(select(func.max(cast(Document.number, Integer))).where(Document.kind == kind))
    return str(int(last or 0) + 1)


def mark_delivered(db: Session, trip_id: int, driver: User, actual_m3: Decimal, event_id: str | None) -> tuple[Trip, list[Document]]:
    """Подтверждение доставки — одна транзакция: рейс, остаток, ТН и УПД, статус заказа (рисунок 2.4)."""
    trip = _lock_own_trip(db, trip_id, driver)
    if trip.status == TripStatus.delivered and event_id and trip.client_event_id == event_id:
        return trip, list(db.scalars(select(Document).where(Document.trip_id == trip.id)))
    if trip.status != TripStatus.en_route:
        raise HTTPException(409, "Рейс не в статусе «в пути»: сначала отметьте погрузку" if trip.status == TripStatus.planned
                            else "Рейс уже закрыт")
    if actual_m3 <= 0 or actual_m3 > trip.planned_m3:
        raise HTTPException(422, f"Фактический объём должен быть от 0 до {trip.planned_m3:.0f} м³")
    order = db.scalar(select(Order).where(Order.id == trip.order_id).with_for_update())
    quarry = db.get(Quarry, trip.quarry_id)
    site_id = quarry.site_id if quarry else stock.site_for_product(db, order.product_id).id

    trip.status, trip.actual_m3, trip.delivered_at, trip.client_event_id = (
        TripStatus.delivered, actual_m3, datetime.now(timezone.utc), event_id)
    stock.add_movement(db, site_id, MovementKind.shipment, -actual_m3, trip_id=trip.id, order_id=order.id,
                       comment=f"Рейс по заказу {order.number}")
    unit = Decimal(order.price_m3) + Decimal(order.delivery_m3)
    amount = (unit * actual_m3).quantize(Decimal("0.01"), ROUND_HALF_UP)
    vat = pricing.vat_included(amount, Decimal(order.vat_rate))
    docs = []
    for kind in (DocKind.waybill, DocKind.upd):
        doc = Document(kind=kind, number=_next_number(db, kind), doc_date=date.today(), order_id=order.id, trip_id=trip.id,
                       volume_m3=actual_m3, amount=amount, vat=vat, paid_amount=Decimal(0))
        db.add(doc)
        db.flush()
        docs.append(doc)
    delivered = Decimal(db.scalar(select(func.coalesce(func.sum(Trip.actual_m3), 0)).where(
        Trip.order_id == order.id, Trip.status == TripStatus.delivered)))
    open_trips = db.scalar(select(func.count()).where(Trip.order_id == order.id,
                                                      Trip.status.in_([TripStatus.planned, TripStatus.en_route])))
    if delivered >= order.volume_m3 or (open_trips == 0 and remaining_m3(db, order) <= 0):
        order.status = OrderStatus.shipped
    return trip, docs
