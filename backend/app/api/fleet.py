from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import MaintenanceRecord, Role, User, Vehicle, VehicleKind
from ..schemas import DriverShort, MaintenanceFinish, MaintenanceOut, MaintenanceStart, VehicleOut, VehiclePatch
from ..security import require
from ..services import fleet as svc

router = APIRouter(prefix="/api", tags=["Техника"])
READ = (Role.director, Role.manager, Role.mechanic, Role.admin)
EDIT = (Role.mechanic, Role.admin)


def m_out(r: MaintenanceRecord) -> MaintenanceOut:
    return MaintenanceOut(id=r.id, kind=r.kind, description=r.description, started_at=r.started_at,
                          planned_end=r.planned_end, finished_at=r.finished_at,
                          mechanic=r.mechanic.full_name if r.mechanic else None)


def v_out(db: Session, v: Vehicle, history: bool = False) -> VehicleOut:
    cur = svc.open_record(db, v)
    left = svc.service_left(v)
    hist = []
    if history:
        hist = [m_out(r) for r in db.scalars(select(MaintenanceRecord).where(MaintenanceRecord.vehicle_id == v.id)
                                             .order_by(MaintenanceRecord.started_at.desc()).limit(20))]
    return VehicleOut(id=v.id, kind=v.kind, name=v.name, model=v.model, reg_number=v.reg_number, capacity_m3=v.capacity_m3,
                      status=v.status, odometer_km=v.odometer_km, engine_hours=v.engine_hours,
                      counter_unit="км" if v.kind == VehicleKind.dump_truck else "моточ.",
                      service_interval=v.service_interval, service_left=left,
                      service_soon=left <= v.service_interval * svc.SOON_SHARE,
                      driver_id=v.driver_id, driver_name=v.driver.full_name if v.driver else None,
                      current=m_out(cur) if cur else None, history=hist)


def get_vehicle(db: Session, vehicle_id: int) -> Vehicle:
    v = db.scalar(select(Vehicle).where(Vehicle.id == vehicle_id).with_for_update())
    if v is None:
        raise HTTPException(404, "Техника не найдена")
    return v


@router.get("/vehicles", response_model=list[VehicleOut], summary="Вся техника", dependencies=[Depends(require(*READ))])
def vehicles(db: Session = Depends(get_db)):
    return [v_out(db, v) for v in db.scalars(select(Vehicle).order_by(Vehicle.kind, Vehicle.id))]


@router.get("/vehicles/{vehicle_id}", response_model=VehicleOut, summary="Карточка техники с историей обслуживания",
            dependencies=[Depends(require(*READ))])
def vehicle(vehicle_id: int, db: Session = Depends(get_db)):
    v = db.get(Vehicle, vehicle_id)
    if v is None:
        raise HTTPException(404, "Техника не найдена")
    return v_out(db, v, history=True)


@router.patch("/vehicles/{vehicle_id}", response_model=VehicleOut, summary="Водитель, пробег, интервал ТО")
def update(vehicle_id: int, data: VehiclePatch, db: Session = Depends(get_db), _: User = Depends(require(*EDIT))):
    v = get_vehicle(db, vehicle_id)
    fields = data.model_fields_set
    if "driver_id" in fields:
        svc.assign_driver(db, v, data.driver_id)
    if data.counter is not None:
        svc.set_counter(v, data.counter)
    if data.service_interval is not None:
        v.service_interval = data.service_interval
    if "reg_number" in fields:
        v.reg_number = data.reg_number
    db.commit()
    return v_out(db, v, history=True)


@router.post("/vehicles/{vehicle_id}/maintenance", response_model=VehicleOut, summary="Начать ремонт или ТО")
def start(vehicle_id: int, data: MaintenanceStart, db: Session = Depends(get_db), user: User = Depends(require(*EDIT))):
    v = get_vehicle(db, vehicle_id)
    svc.start(db, v, data.kind, data.description, data.planned_end, user)
    db.commit()
    return v_out(db, v, history=True)


@router.post("/vehicles/{vehicle_id}/maintenance/finish", response_model=VehicleOut, summary="Завершить ремонт или ТО")
def finish(vehicle_id: int, data: MaintenanceFinish, db: Session = Depends(get_db), _: User = Depends(require(*EDIT))):
    v = get_vehicle(db, vehicle_id)
    svc.finish(db, v, data.counter)
    db.commit()
    return v_out(db, v, history=True)


@router.get("/drivers", response_model=list[DriverShort], summary="Водители и их самосвалы",
            dependencies=[Depends(require(*READ))])
def drivers(db: Session = Depends(get_db)):
    trucks = {v.driver_id: v.name for v in db.scalars(select(Vehicle).where(Vehicle.driver_id.is_not(None)))}
    return [DriverShort(id=u.id, full_name=u.full_name, vehicle_name=trucks.get(u.id))
            for u in db.scalars(select(User).where(User.role == Role.driver, User.is_active).order_by(User.id))]
