from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from ..config import settings
from ..db import get_db
from ..models import Client, ClientAddress
from ..schemas import AddressIn, AddressOut, ClientIn, ClientOut
from ..security import ORDERS_EDIT, ORDERS_READ, require
from ..services.distance import provider

router = APIRouter(prefix="/api/clients", tags=["Клиенты"])


def make_address(a: AddressIn) -> ClientAddress:
    distance = a.distance_km
    if distance is None:
        if a.lat is None or a.lon is None:
            raise HTTPException(422, f"Для адреса «{a.address}» укажите координаты или расстояние от карьера")
        distance = Decimal(str(provider.distance_km((settings.base_lat, settings.base_lon), (a.lat, a.lon))))
    return ClientAddress(address=a.address, lat=a.lat, lon=a.lon, distance_km=distance,
                         heavy_restricted=a.heavy_restricted)


@router.get("", response_model=list[ClientOut], dependencies=[Depends(require(*ORDERS_READ))])
def list_clients(q: str | None = None, db: Session = Depends(get_db)):
    stmt = select(Client).options(selectinload(Client.addresses)).where(Client.is_active).order_by(Client.name)
    if q:
        stmt = stmt.where(or_(Client.name.ilike(f"%{q}%"), Client.inn.ilike(f"{q}%")))
    return db.scalars(stmt).all()


@router.post("", response_model=ClientOut, status_code=201, dependencies=[Depends(require(*ORDERS_EDIT))])
def create_client(data: ClientIn, db: Session = Depends(get_db)):
    client = Client(**data.model_dump(exclude={"addresses"}))
    client.addresses = [make_address(a) for a in data.addresses]
    db.add(client)
    db.commit()
    return client


@router.post("/{client_id}/addresses", response_model=AddressOut, status_code=201,
             dependencies=[Depends(require(*ORDERS_EDIT))])
def add_address(client_id: int, data: AddressIn, db: Session = Depends(get_db)):
    client = db.get(Client, client_id)
    if client is None:
        raise HTTPException(404, "Клиент не найден")
    addr = make_address(data)
    client.addresses.append(addr)
    db.commit()
    return addr
