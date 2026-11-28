"""Начальное заполнение базы: справочники предприятия, пользователи по ролям и демонстрационные клиенты.
Запускается при каждом старте контейнера, но ничего не перезаписывает, если данные уже есть."""
import sys
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from .config import settings
from .db import SessionLocal
from .models import (Client, ClientAddress, ClientType, License, MovementKind, Product, Quarry, Role, StockMovement,
                     StorageSite, User, Vehicle, VehicleKind)
from .security import hash_password

# Координаты — приблизительные (район пос. Свень); администратор уточняет их в настройках.
B_LAT, B_LON = settings.base_lat, settings.base_lon

USERS = [  # логин, ФИО, роль
    ("director", "Куликов Денис Геннадьевич", Role.director),
    ("manager", "Смирнова Ольга", Role.manager),
    ("buh", "Фролова Елена", Role.accountant),
    ("lawyer", "Ковалёва Марина", Role.lawyer),
    ("mechanic", "Ткачёв Сергей", Role.mechanic),
    ("admin", "Нестеров Игорь", Role.admin),
] + [(f"driver{i}", name, Role.driver) for i, name in enumerate(
    ["Петров Иван", "Громов Сергей", "Белов Андрей", "Лебедев Роман", "Орлов Дмитрий",
     "Ковалёв Павел", "Зайцев Никита", "Соколов Артём", "Морозов Илья", "Волков Егор"], start=1)]


def seed_reference(db):
    if db.scalar(select(Product.id).limit(1)):
        return False
    fine = Product(name="Мелкий", price_m3=Decimal(300))
    very = Product(name="Очень мелкий", price_m3=Decimal(300))
    db.add_all([fine, very])
    db.flush()
    s1 = StorageSite(product_id=fine.id, name="Площадка «Мелкий»", capacity_m3=Decimal(30000), lat=B_LAT, lon=B_LON)
    s2 = StorageSite(product_id=very.id, name="Площадка «Очень мелкий»", capacity_m3=Decimal(30000),
                     lat=B_LAT + 0.004, lon=B_LON + 0.006)
    db.add_all([s1, s2])
    db.flush()
    quarries = [Quarry(site_id=s1.id, name="Карьер №1", lat=B_LAT + 0.002, lon=B_LON - 0.004),
                Quarry(site_id=s1.id, name="Карьер №2", lat=B_LAT + 0.006, lon=B_LON - 0.002),
                Quarry(site_id=s2.id, name="Карьер №3", lat=B_LAT + 0.007, lon=B_LON + 0.009),
                Quarry(site_id=s2.id, name="Карьер №4", lat=B_LAT + 0.011, lon=B_LON + 0.006)]
    db.add_all(quarries)
    db.flush()
    # номера и сроки лицензий — условные, юрист заменит их реальными
    for q, (num, to) in zip(quarries, [("БРН 0001 ТЭ", date(2031, 3, 15)), ("БРН 0002 ТЭ", date(2031, 3, 15)),
                                       ("БРН 0003 ТЭ", date(2027, 7, 1)), ("БРН 0004 ТЭ", date(2027, 7, 1))]):
        db.add(License(quarry_id=q.id, number=num, valid_to=to))
    # пробег и моточасы — условные начальные значения, механик заменит их фактическими
    for i in range(1, 9):
        km = 138000 + i * 3100
        db.add(Vehicle(kind=VehicleKind.dump_truck, name=f"Самосвал №{i}", model="SsangYong", capacity_m3=Decimal(30),
                       odometer_km=km, service_interval=15000, last_service_at=km - 4000 * (i % 4) - 1200))
    for i in (1, 2):
        db.add(Vehicle(kind=VehicleKind.excavator, name=f"Экскаватор №{i}", model="Hitachi", capacity_m3=Decimal("1.5"),
                       engine_hours=8000 + 400 * i, service_interval=250, last_service_at=8000 + 400 * i - 170 + 60 * i))
        db.add(Vehicle(kind=VehicleKind.loader, name=f"Погрузчик №{i}", model="Фронтальный погрузчик", capacity_m3=Decimal(2),
                       engine_hours=5300 + 200 * i, service_interval=250, last_service_at=5300 + 200 * i - 230 + 40 * i))
    return True


def seed_users(db):
    if db.scalar(select(User.id).limit(1)):
        return False
    if not settings.seed_password:
        print("SEED_PASSWORD не задан — пользователи не созданы. Укажите его в .env и перезапустите.")
        return False
    pwd = hash_password(settings.seed_password)
    for login, name, role in USERS:
        db.add(User(login=login, full_name=name, role=role, password_hash=pwd))
    db.flush()
    drivers = db.scalars(select(User).where(User.role == Role.driver).order_by(User.id)).all()
    trucks = db.scalars(select(Vehicle).where(Vehicle.kind == VehicleKind.dump_truck).order_by(Vehicle.id)).all()
    for truck, driver in zip(trucks, drivers):
        truck.driver_id = driver.id
    return True


def seed_demo(db):
    """Демонстрационные клиенты (названия вымышленные) и начальные остатки на площадках."""
    if db.scalar(select(Client.id).limit(1)):
        return False
    demo = [
        ("ООО «ДорСтройПроект»", "3250000001", ClientType.road, "г. Брянск, ул. Литейная, 68", 53.258, 34.371),
        ("АО «Бетон-Сервис»", "3250000002", ClientType.concrete, "г. Брянск, ул. Сталелитейная, 1", 53.276, 34.330),
        ("ООО «СтройИнвест»", "3250000003", ClientType.construction, "пгт Выгоничи, ул. Ленина, 12", 53.090, 34.070),
        ("ИП Сафонов А. В.", "325000000004", ClientType.private, "д. Супонево, ул. Садовая, 5", 53.203, 34.276),
    ]
    for name, inn, kind, addr, lat, lon in demo:
        c = Client(name=name, inn=inn, client_type=kind)
        from .services.distance import provider
        d = provider.distance_km((B_LAT, B_LON), (lat, lon))
        c.addresses = [ClientAddress(address=addr, lat=lat, lon=lon, distance_km=Decimal(str(d)))]
        db.add(c)
    for site, vol in zip(db.scalars(select(StorageSite).order_by(StorageSite.id)), (18400, 12900)):
        db.add(StockMovement(site_id=site.id, kind=MovementKind.adjustment, volume_m3=Decimal(vol),
                             comment="Начальный остаток (демонстрационные данные)"))
    return True


def main():
    with SessionLocal() as db:
        r = seed_reference(db)
        u = seed_users(db)
        d = seed_demo(db) if "--no-demo" not in sys.argv else False
        db.commit()
    print(f"seed: справочники={'созданы' if r else 'есть'}, пользователи={'созданы' if u else 'есть/пропущено'}, "
          f"демо={'созданы' if d else 'есть/пропущено'}")


if __name__ == "__main__":
    main()
