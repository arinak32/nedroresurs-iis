from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from .models import ClientType, DeliveryMethod, OrderSource, OrderStatus, Role, VehicleKind, VehicleStatus


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(ORM):
    id: int
    login: str
    full_name: str
    role: Role


class ProductOut(ORM):
    id: int
    name: str
    price_m3: Decimal


class SiteOut(BaseModel):
    id: int
    name: str
    product_id: int
    product_name: str
    capacity_m3: Decimal
    volume_m3: Decimal
    fill_pct: float


class QuarryOut(ORM):
    id: int
    name: str
    site_id: int


class Tariffs(BaseModel):
    delivery_step_km: Decimal = Field(gt=0)
    delivery_step_price: Decimal = Field(ge=0)
    vat_rate: Decimal = Field(ge=0, le=100)
    truck_capacity_m3: Decimal = Field(gt=0)
    prices: dict[int, Decimal] = {}  # id вида песка → цена за 1 м³


class AddressIn(BaseModel):
    address: str = Field(min_length=3)
    lat: float | None = None
    lon: float | None = None
    distance_km: Decimal | None = Field(default=None, ge=0)
    heavy_restricted: bool = False


class AddressOut(ORM):
    id: int
    address: str
    lat: float | None
    lon: float | None
    distance_km: Decimal
    heavy_restricted: bool


class ClientIn(BaseModel):
    name: str = Field(min_length=2)
    inn: str | None = Field(default=None, pattern=r"^\d{10}(\d{2})?$")
    kpp: str | None = Field(default=None, pattern=r"^\d{9}$")
    client_type: ClientType = ClientType.other
    phone: str | None = None
    email: str | None = None
    addresses: list[AddressIn] = []


class ClientOut(ORM):
    id: int
    name: str
    inn: str | None
    client_type: ClientType
    phone: str | None
    addresses: list[AddressOut]


class QuoteOut(BaseModel):
    distance_km: Decimal | None
    price_m3: Decimal
    delivery_m3: Decimal
    unit_total: Decimal
    amount: Decimal
    vat: Decimal
    vat_rate: Decimal
    tariff_steps: int
    site_id: int
    site_name: str
    available_m3: Decimal
    enough: bool
    trips_needed: int


class OrderIn(BaseModel):
    client_id: int
    product_id: int
    volume_m3: Decimal = Field(gt=0, le=100000)
    method: DeliveryMethod
    address_id: int | None = None
    distance_km: Decimal | None = Field(default=None, ge=0)
    contract_id: int | None = None
    desired_date: date | None = None
    source: OrderSource = OrderSource.phone
    procurement_no: str | None = None
    comment: str | None = None


class OrderOut(ORM):
    id: int
    number: str
    client_id: int
    client_name: str
    product_id: int
    product_name: str
    volume_m3: Decimal
    method: DeliveryMethod
    address: str | None
    distance_km: Decimal | None
    desired_date: date | None
    price_m3: Decimal
    delivery_m3: Decimal
    amount: Decimal
    vat: Decimal
    vat_rate: Decimal
    source: OrderSource
    procurement_no: str | None
    contract_number: str | None
    status: OrderStatus
    created_at: datetime


class OrdersPage(BaseModel):
    items: list[OrderOut]
    total: int
    counts: dict[str, int]


class StatusAction(BaseModel):
    action: str


class ProductionIn(BaseModel):
    quarry_id: int
    shift_date: date
    volume_m3: Decimal = Field(gt=0, le=5000)


class ProductionOut(BaseModel):
    id: int
    shift_date: date
    quarry_name: str
    product_name: str
    volume_m3: Decimal
    author: str | None


class MaintenanceOut(BaseModel):
    id: int
    kind: str
    description: str | None
    started_at: datetime
    planned_end: date | None
    finished_at: datetime | None
    mechanic: str | None


class VehicleOut(BaseModel):
    id: int
    kind: VehicleKind
    name: str
    model: str
    reg_number: str | None
    capacity_m3: Decimal
    status: VehicleStatus
    odometer_km: int
    engine_hours: int
    counter_unit: str            # «км» или «моточ.»
    service_interval: int
    service_left: int            # сколько осталось до ТО (может быть < 0 — ТО просрочено)
    service_soon: bool
    driver_id: int | None
    driver_name: str | None
    current: MaintenanceOut | None
    history: list[MaintenanceOut] = []


class MaintenanceStart(BaseModel):
    kind: str = Field(pattern="^(ТО|ремонт)$")
    description: str | None = Field(default=None, max_length=1000)
    planned_end: date | None = None


class MaintenanceFinish(BaseModel):
    counter: int | None = Field(default=None, ge=0)   # пробег или моточасы на момент окончания


class VehiclePatch(BaseModel):
    driver_id: int | None = None
    counter: int | None = Field(default=None, ge=0)
    service_interval: int | None = Field(default=None, gt=0)
    reg_number: str | None = None


class DriverShort(BaseModel):
    id: int
    full_name: str
    vehicle_name: str | None


class PlanRequest(BaseModel):
    plan_date: date


class TripOut(BaseModel):
    id: int
    seq: int
    order_id: int
    order_number: str
    client_name: str
    client_phone: str | None
    address: str | None
    heavy_restricted: bool
    product_name: str
    quarry_name: str | None
    vehicle_id: int | None
    vehicle_name: str | None
    driver_name: str | None
    planned_m3: Decimal
    actual_m3: Decimal | None
    distance_km: Decimal | None
    status: str
    loaded_at: datetime | None
    delivered_at: datetime | None


class TruckOut(BaseModel):
    id: int
    name: str
    driver_name: str | None
    status: str


class PlanOut(BaseModel):
    id: int
    plan_date: date
    status: str
    total_km: Decimal | None
    trips: list[TripOut]
    trucks: list[TruckOut]
    unplanned: list[dict] = []
    orders_count: int
    blocked: list[int] = []      # рейсы на самосвалах, ушедших в ремонт после утверждения плана


class MoveTrip(BaseModel):
    vehicle_id: int


class DriverEvent(BaseModel):
    event_id: str | None = Field(default=None, max_length=64)


class DeliverIn(DriverEvent):
    actual_m3: Decimal = Field(gt=0)


class DeliverOut(BaseModel):
    trip: TripOut
    documents: list[str]


class DriverDay(BaseModel):
    driver_name: str
    vehicle_name: str | None
    vehicle_model: str | None
    plan_date: date
    trips: list[TripOut]
