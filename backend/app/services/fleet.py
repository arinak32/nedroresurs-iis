"""Техника: ремонты и ТО, пробег, закрепление водителей (экран механика)."""
from datetime import date, datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (MaintenanceRecord, PlanStatus, Role, RoutePlan, Trip, TripStatus, User, Vehicle, VehicleKind,
                      VehicleStatus)

SOON_SHARE = 0.1  # «скоро ТО», если до обслуживания осталось меньше 10 % интервала

KIND_STATUS = {"ТО": VehicleStatus.maintenance, "ремонт": VehicleStatus.repair}


def counter(v: Vehicle) -> int:
    """Самосвалы обслуживаются по пробегу, остальная техника — по моточасам."""
    return v.odometer_km if v.kind == VehicleKind.dump_truck else v.engine_hours


def service_left(v: Vehicle) -> int:
    return v.last_service_at + v.service_interval - counter(v)


def open_record(db: Session, v: Vehicle) -> MaintenanceRecord | None:
    return db.scalar(select(MaintenanceRecord).where(MaintenanceRecord.vehicle_id == v.id,
                                                     MaintenanceRecord.finished_at.is_(None)))


def start(db: Session, v: Vehicle, kind: str, description: str | None, planned_end: date | None, user: User):
    if kind not in KIND_STATUS:
        raise HTTPException(422, "Вид работ: «ТО» или «ремонт»")
    if v.status != VehicleStatus.on_line or open_record(db, v):
        raise HTTPException(409, f"{v.name} уже в ремонте или на ТО")
    rec = MaintenanceRecord(vehicle_id=v.id, kind=kind, description=description, planned_end=planned_end,
                            started_at=datetime.now(timezone.utc), mechanic_id=user.id)
    db.add(rec)
    v.status = KIND_STATUS[kind]
    return rec


def finish(db: Session, v: Vehicle, counter_value: int | None):
    rec = open_record(db, v)
    if rec is None:
        raise HTTPException(409, f"{v.name} не в ремонте и не на ТО")
    if counter_value is not None:
        set_counter(v, counter_value)
    rec.finished_at = datetime.now(timezone.utc)
    if rec.kind == "ТО":
        v.last_service_at = counter(v)
    v.status = VehicleStatus.on_line
    return rec


def set_counter(v: Vehicle, value: int):
    if value < counter(v):
        raise HTTPException(422, "Пробег и моточасы не могут уменьшаться")
    if v.kind == VehicleKind.dump_truck:
        v.odometer_km = value
    else:
        v.engine_hours = value


def assign_driver(db: Session, v: Vehicle, driver_id: int | None):
    if v.kind != VehicleKind.dump_truck:
        raise HTTPException(422, "Водитель закрепляется только за самосвалом")
    if driver_id is not None:
        driver = db.get(User, driver_id)
        if driver is None or driver.role != Role.driver or not driver.is_active:
            raise HTTPException(422, "Пользователь не является водителем")
        # у водителя один самосвал: снимаем его с прежней машины
        for other in db.scalars(select(Vehicle).where(Vehicle.driver_id == driver_id, Vehicle.id != v.id)):
            other.driver_id = None
    v.driver_id = driver_id


def blocked_trips(db: Session, plan: RoutePlan) -> list[Trip]:
    """Невыполненные рейсы утверждённого плана, назначенные на самосвал не на линии."""
    if plan.status != PlanStatus.approved:
        return []
    return list(db.scalars(select(Trip).join(Vehicle, Vehicle.id == Trip.vehicle_id).where(
        Trip.plan_id == plan.id, Trip.status == TripStatus.planned, Vehicle.status != VehicleStatus.on_line)))
