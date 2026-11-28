from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import (Client, ClientAddress, DocKind, Order, PlanStatus, Product, Quarry, Role, RoutePlan, Trip, User,
                      Vehicle, VehicleKind)
from ..schemas import (DeliverIn, DeliverOut, DriverDay, DriverEvent, MoveTrip, PlanOut, PlanRequest, TripOut,
                       TruckOut)
from ..security import require
from ..services import fleet
from ..services import trips as svc

router = APIRouter(prefix="/api", tags=["Рейсы"])
PLAN_READ = (Role.director, Role.manager, Role.mechanic, Role.admin)
DOC_RU = {DocKind.waybill: "ТН", DocKind.upd: "УПД", DocKind.invoice: "Счёт"}


def trip_out(db: Session, t: Trip) -> TripOut:
    order = db.get(Order, t.order_id)
    client = db.get(Client, order.client_id)
    addr = db.get(ClientAddress, order.address_id) if order.address_id else None
    vehicle = db.get(Vehicle, t.vehicle_id) if t.vehicle_id else None
    driver = db.get(User, t.driver_id) if t.driver_id else None
    quarry = db.get(Quarry, t.quarry_id) if t.quarry_id else None
    return TripOut(id=t.id, seq=t.seq, order_id=order.id, order_number=order.number, client_name=client.name,
                   client_phone=client.phone, address=addr.address if addr else None,
                   heavy_restricted=bool(addr and addr.heavy_restricted), product_name=db.get(Product, order.product_id).name,
                   quarry_name=quarry.name if quarry else None, vehicle_id=t.vehicle_id,
                   vehicle_name=vehicle.name if vehicle else None, driver_name=driver.full_name if driver else None,
                   planned_m3=t.planned_m3, actual_m3=t.actual_m3, distance_km=t.distance_km, status=t.status.value,
                   loaded_at=t.loaded_at, delivered_at=t.delivered_at)


def plan_out(db: Session, plan: RoutePlan, unplanned: list[dict] | None = None) -> PlanOut:
    trips = db.scalars(select(Trip).where(Trip.plan_id == plan.id).order_by(Trip.vehicle_id, Trip.seq)).all()
    trucks = db.scalars(select(Vehicle).where(Vehicle.kind == VehicleKind.dump_truck).order_by(Vehicle.id)).all()
    return PlanOut(id=plan.id, plan_date=plan.plan_date, status=plan.status.value, total_km=plan.total_km,
                   trips=[trip_out(db, t) for t in trips], unplanned=unplanned or [],
                   trucks=[TruckOut(id=v.id, name=v.name, driver_name=v.driver.full_name if v.driver else None,
                                    status=v.status.value) for v in trucks],
                   orders_count=len({t.order_id for t in trips}),
                   blocked=[t.id for t in fleet.blocked_trips(db, plan)])


@router.post("/route-plans", response_model=PlanOut, status_code=201, summary="Рассчитать план рейсов на дату")
def create_plan(data: PlanRequest, db: Session = Depends(get_db), _: User = Depends(require(Role.manager))):
    plan, unplanned = svc.build_plan(db, data.plan_date)
    db.commit()
    return plan_out(db, plan, unplanned)


@router.get("/route-plans", response_model=PlanOut | None, summary="План рейсов на дату",
            dependencies=[Depends(require(*PLAN_READ))])
def get_plan(plan_date: date, db: Session = Depends(get_db)):
    plan = db.scalar(select(RoutePlan).where(RoutePlan.plan_date == plan_date).order_by(RoutePlan.id.desc()))
    return plan_out(db, plan) if plan else None


@router.patch("/route-plans/{plan_id}/trips/{trip_id}", response_model=PlanOut, summary="Перенести рейс на другой самосвал")
def move(plan_id: int, trip_id: int, data: MoveTrip, db: Session = Depends(get_db), _: User = Depends(require(Role.manager))):
    plan, trip = db.get(RoutePlan, plan_id), db.get(Trip, trip_id)
    if plan is None or trip is None or trip.plan_id != plan.id:
        raise HTTPException(404, "Рейс не найден")
    svc.move_trip(db, plan, trip, data.vehicle_id)
    db.commit()
    return plan_out(db, plan)


@router.post("/route-plans/{plan_id}/approve", response_model=PlanOut, summary="Утвердить план")
def approve(plan_id: int, db: Session = Depends(get_db), user: User = Depends(require(Role.manager))):
    plan = db.get(RoutePlan, plan_id)
    if plan is None:
        raise HTTPException(404, "План не найден")
    svc.approve(db, plan, user)
    db.commit()
    return plan_out(db, plan)


# ── интерфейс водителя ──

@router.get("/trips/my", response_model=DriverDay, summary="Рейсы водителя на сегодня")
def my_trips(day: date | None = None, db: Session = Depends(get_db), user: User = Depends(require(Role.driver))):
    day = day or date.today()
    trips = db.scalars(select(Trip).join(RoutePlan, RoutePlan.id == Trip.plan_id).where(
        Trip.driver_id == user.id, RoutePlan.plan_date == day, RoutePlan.status == PlanStatus.approved)
        .order_by(Trip.seq)).all()
    vehicle = db.scalar(select(Vehicle).where(Vehicle.driver_id == user.id))
    return DriverDay(driver_name=user.full_name, vehicle_name=vehicle.name if vehicle else None,
                     vehicle_model=vehicle.model if vehicle else None, plan_date=day,
                     trips=[trip_out(db, t) for t in trips])


@router.post("/trips/{trip_id}/load", response_model=TripOut, summary="Отметка «погружен»")
def load(trip_id: int, data: DriverEvent, db: Session = Depends(get_db), user: User = Depends(require(Role.driver))):
    trip = svc.mark_loaded(db, trip_id, user, data.event_id)
    db.commit()
    return trip_out(db, trip)


@router.post("/trips/{trip_id}/deliver", response_model=DeliverOut, summary="Отметка «доставлено»")
def deliver(trip_id: int, data: DeliverIn, db: Session = Depends(get_db), user: User = Depends(require(Role.driver))):
    trip, docs = svc.mark_delivered(db, trip_id, user, data.actual_m3, data.event_id)
    db.commit()
    return DeliverOut(trip=trip_out(db, trip), documents=[f"{DOC_RU[d.kind]} № {d.number}" for d in docs])
