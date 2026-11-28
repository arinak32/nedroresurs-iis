"""Модель данных ИИС «Недроресурс» (глава 2, раздел 2.3)."""
import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (Boolean, Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text,
                        UniqueConstraint, func)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

M3 = Numeric(12, 2)      # объёмы, м³
MONEY = Numeric(14, 2)   # суммы, руб.


def pg_enum(cls, name):
    return Enum(cls, name=name, values_callable=lambda e: [m.value for m in e])


class Role(str, enum.Enum):
    director = "director"
    manager = "manager"
    accountant = "accountant"
    lawyer = "lawyer"
    mechanic = "mechanic"
    driver = "driver"
    admin = "admin"


class ClientType(str, enum.Enum):
    road = "road"                  # дорожная организация
    construction = "construction"  # строительная организация
    concrete = "concrete"          # завод ЖБИ / бетонный узел
    private = "private"            # частное лицо
    other = "other"


class DeliveryMethod(str, enum.Enum):
    delivery = "delivery"
    pickup = "pickup"


class OrderSource(str, enum.Enum):
    phone = "phone"
    etp = "etp"  # электронная торговая площадка


class OrderStatus(str, enum.Enum):
    new = "new"
    awaiting_payment = "awaiting_payment"
    planning = "planning"
    in_delivery = "in_delivery"
    shipped = "shipped"
    done = "done"
    cancelled = "cancelled"


class VehicleKind(str, enum.Enum):
    dump_truck = "dump_truck"
    excavator = "excavator"
    loader = "loader"


class VehicleStatus(str, enum.Enum):
    on_line = "on_line"
    maintenance = "maintenance"
    repair = "repair"


class PlanStatus(str, enum.Enum):
    draft = "draft"
    approved = "approved"


class TripStatus(str, enum.Enum):
    planned = "planned"
    en_route = "en_route"
    delivered = "delivered"
    cancelled = "cancelled"


class MovementKind(str, enum.Enum):
    production = "production"
    shipment = "shipment"
    adjustment = "adjustment"


class DocKind(str, enum.Enum):
    invoice = "invoice"
    waybill = "waybill"  # транспортная накладная
    upd = "upd"


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    login: Mapped[str] = mapped_column(String(50), unique=True)
    password_hash: Mapped[str] = mapped_column(String(100))
    full_name: Mapped[str] = mapped_column(String(150))
    phone: Mapped[str | None] = mapped_column(String(30))
    role: Mapped[Role] = mapped_column(pg_enum(Role, "user_role"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Setting(Base):
    """Параметры тарифа и системы: ключ — значение (шаг тарифа, надбавка, НДС, вместимость самосвала)."""
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[str] = mapped_column(String(200))


class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    price_m3: Mapped[Decimal] = mapped_column(MONEY)


class StorageSite(Base):
    __tablename__ = "storage_sites"
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    name: Mapped[str] = mapped_column(String(100))
    capacity_m3: Mapped[Decimal] = mapped_column(M3)
    lat: Mapped[float | None]
    lon: Mapped[float | None]
    product: Mapped[Product] = relationship()


class Quarry(Base):
    __tablename__ = "quarries"
    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("storage_sites.id"))
    name: Mapped[str] = mapped_column(String(100))
    lat: Mapped[float | None]
    lon: Mapped[float | None]
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    site: Mapped[StorageSite] = relationship()


class License(Base):
    __tablename__ = "licenses"
    id: Mapped[int] = mapped_column(primary_key=True)
    quarry_id: Mapped[int] = mapped_column(ForeignKey("quarries.id"))
    number: Mapped[str] = mapped_column(String(50))
    valid_to: Mapped[date] = mapped_column(Date)


class ProductionRecord(Base):
    __tablename__ = "production_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    quarry_id: Mapped[int] = mapped_column(ForeignKey("quarries.id"))
    shift_date: Mapped[date] = mapped_column(Date)
    volume_m3: Mapped[Decimal] = mapped_column(M3)
    entered_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    quarry: Mapped[Quarry] = relationship()
    author: Mapped[User | None] = relationship()


class StockMovement(Base):
    """Движение остатка на площадке: + добыча, − отгрузка, ± корректировка."""
    __tablename__ = "stock_movements"
    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("storage_sites.id"), index=True)
    kind: Mapped[MovementKind] = mapped_column(pg_enum(MovementKind, "movement_kind"))
    volume_m3: Mapped[Decimal] = mapped_column(M3)  # со знаком
    production_id: Mapped[int | None] = mapped_column(ForeignKey("production_records.id"))
    trip_id: Mapped[int | None] = mapped_column(ForeignKey("trips.id"))
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"))
    comment: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Client(Base):
    __tablename__ = "clients"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    inn: Mapped[str | None] = mapped_column(String(12))
    kpp: Mapped[str | None] = mapped_column(String(9))
    client_type: Mapped[ClientType] = mapped_column(pg_enum(ClientType, "client_type"), default=ClientType.other)
    phone: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    addresses: Mapped[list["ClientAddress"]] = relationship(back_populates="client", order_by="ClientAddress.id")


class ClientAddress(Base):
    __tablename__ = "client_addresses"
    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"))
    address: Mapped[str] = mapped_column(String(300))
    lat: Mapped[float | None]
    lon: Mapped[float | None]
    distance_km: Mapped[Decimal] = mapped_column(Numeric(8, 1))  # по дорогам от карьеров, в одну сторону
    heavy_restricted: Mapped[bool] = mapped_column(Boolean, default=False)  # дорога с ограничением массы
    client: Mapped[Client] = relationship(back_populates="addresses")


class Contract(Base):
    __tablename__ = "contracts"
    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    number: Mapped[str] = mapped_column(String(50), unique=True)
    volume_m3: Mapped[Decimal] = mapped_column(M3)
    price_m3: Mapped[Decimal] = mapped_column(MONEY)  # цена с доставкой по договору
    date_from: Mapped[date] = mapped_column(Date)
    date_to: Mapped[date] = mapped_column(Date)
    procurement_no: Mapped[str | None] = mapped_column(String(50))
    client: Mapped[Client] = relationship()
    product: Mapped[Product] = relationship()


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    number: Mapped[str | None] = mapped_column(String(20), unique=True)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), index=True)
    contract_id: Mapped[int | None] = mapped_column(ForeignKey("contracts.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    address_id: Mapped[int | None] = mapped_column(ForeignKey("client_addresses.id"))
    volume_m3: Mapped[Decimal] = mapped_column(M3)
    method: Mapped[DeliveryMethod] = mapped_column(pg_enum(DeliveryMethod, "delivery_method"))
    desired_date: Mapped[date | None] = mapped_column(Date)
    distance_km: Mapped[Decimal | None] = mapped_column(Numeric(8, 1))
    price_m3: Mapped[Decimal] = mapped_column(MONEY)      # цена песка на момент оформления
    delivery_m3: Mapped[Decimal] = mapped_column(MONEY)   # надбавка за доставку на 1 м³
    amount: Mapped[Decimal] = mapped_column(MONEY)        # сумма с НДС
    vat: Mapped[Decimal] = mapped_column(MONEY)           # в т. ч. НДС
    vat_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    source: Mapped[OrderSource] = mapped_column(pg_enum(OrderSource, "order_source"), default=OrderSource.phone)
    procurement_no: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[OrderStatus] = mapped_column(pg_enum(OrderStatus, "order_status"), default=OrderStatus.new, index=True)
    comment: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    client: Mapped[Client] = relationship()
    product: Mapped[Product] = relationship()
    address: Mapped[ClientAddress | None] = relationship()
    contract: Mapped[Contract | None] = relationship()


class Vehicle(Base):
    __tablename__ = "vehicles"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[VehicleKind] = mapped_column(pg_enum(VehicleKind, "vehicle_kind"))
    name: Mapped[str] = mapped_column(String(50))        # «Самосвал №1»
    model: Mapped[str] = mapped_column(String(50))
    reg_number: Mapped[str | None] = mapped_column(String(20))
    capacity_m3: Mapped[Decimal] = mapped_column(M3)     # кузов или ковш
    status: Mapped[VehicleStatus] = mapped_column(pg_enum(VehicleStatus, "vehicle_status"), default=VehicleStatus.on_line)
    odometer_km: Mapped[int] = mapped_column(Integer, default=0)
    engine_hours: Mapped[int] = mapped_column(Integer, default=0)
    driver_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))  # закреплённый водитель
    # ТО по пробегу (самосвалы) или по моточасам (экскаваторы, погрузчики)
    service_interval: Mapped[int] = mapped_column(Integer, default=15000)
    last_service_at: Mapped[int] = mapped_column(Integer, default=0)  # пробег/моточасы на последнем ТО
    driver: Mapped[User | None] = relationship()


class MaintenanceRecord(Base):
    __tablename__ = "maintenance_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"))
    kind: Mapped[str] = mapped_column(String(20))  # «ТО» или «ремонт»
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    planned_end: Mapped[date | None] = mapped_column(Date)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    description: Mapped[str | None] = mapped_column(Text)
    mechanic_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    mechanic: Mapped[User | None] = relationship()


class RoutePlan(Base):
    __tablename__ = "route_plans"
    id: Mapped[int] = mapped_column(primary_key=True)
    plan_date: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[PlanStatus] = mapped_column(pg_enum(PlanStatus, "plan_status"), default=PlanStatus.draft)
    total_km: Mapped[Decimal | None] = mapped_column(Numeric(10, 1))
    baseline_km: Mapped[Decimal | None] = mapped_column(Numeric(10, 1))  # «ручной» вариант для сравнения
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Trip(Base):
    __tablename__ = "trips"
    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int | None] = mapped_column(ForeignKey("route_plans.id"))
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    vehicle_id: Mapped[int | None] = mapped_column(ForeignKey("vehicles.id"))
    driver_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    quarry_id: Mapped[int | None] = mapped_column(ForeignKey("quarries.id"))
    seq: Mapped[int] = mapped_column(Integer, default=0)
    planned_m3: Mapped[Decimal] = mapped_column(M3)
    actual_m3: Mapped[Decimal | None] = mapped_column(M3)
    distance_km: Mapped[Decimal | None] = mapped_column(Numeric(8, 1))
    status: Mapped[TripStatus] = mapped_column(pg_enum(TripStatus, "trip_status"), default=TripStatus.planned)
    loaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    client_event_id: Mapped[str | None] = mapped_column(String(64), unique=True)  # защита от повторной отметки


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("kind", "number"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[DocKind] = mapped_column(pg_enum(DocKind, "doc_kind"))
    number: Mapped[str] = mapped_column(String(20))
    doc_date: Mapped[date] = mapped_column(Date)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    trip_id: Mapped[int | None] = mapped_column(ForeignKey("trips.id"))
    volume_m3: Mapped[Decimal | None] = mapped_column(M3)
    amount: Mapped[Decimal] = mapped_column(MONEY)
    vat: Mapped[Decimal] = mapped_column(MONEY)
    paid_amount: Mapped[Decimal] = mapped_column(MONEY, default=0)


class Forecast(Base):
    __tablename__ = "forecasts"
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    model_name: Mapped[str] = mapped_column(String(30))
    mae: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    mape: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    metrics_json: Mapped[str | None] = mapped_column(Text)  # метрики всех сравниваемых моделей
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ForecastValue(Base):
    __tablename__ = "forecast_values"
    id: Mapped[int] = mapped_column(primary_key=True)
    forecast_id: Mapped[int] = mapped_column(ForeignKey("forecasts.id", ondelete="CASCADE"))
    month: Mapped[date] = mapped_column(Date)
    value_m3: Mapped[Decimal] = mapped_column(M3)
    lower_m3: Mapped[Decimal | None] = mapped_column(M3)
    upper_m3: Mapped[Decimal | None] = mapped_column(M3)
    plan_m3: Mapped[Decimal | None] = mapped_column(M3)
