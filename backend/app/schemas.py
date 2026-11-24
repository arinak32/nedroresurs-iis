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


class VehicleOut(ORM):
    id: int
    kind: VehicleKind
    name: str
    model: str
    capacity_m3: Decimal
    status: VehicleStatus
    odometer_km: int
