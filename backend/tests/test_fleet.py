from datetime import date

from tests.conftest import login
from tests.test_trips import TODAY, make_delivery_order, plan_and_approve


def test_vehicles_list_and_roles(client):
    mech = login(client, "mechanic")
    vs = client.get("/api/vehicles", headers=mech).json()
    assert len(vs) == 12
    truck = next(v for v in vs if v["kind"] == "dump_truck")
    assert truck["counter_unit"] == "км" and truck["driver_name"]
    exc = next(v for v in vs if v["kind"] == "excavator")
    assert exc["counter_unit"] == "моточ." and exc["service_interval"] == 250
    assert client.get("/api/vehicles", headers=login(client, "buh")).status_code == 403
    assert client.post("/api/vehicles/1/maintenance", headers=login(client, "manager"),
                       json={"kind": "ремонт"}).status_code == 403


def test_repair_cycle_and_history(client):
    mech = login(client, "mechanic")
    r = client.post("/api/vehicles/4/maintenance", headers=mech,
                    json={"kind": "ремонт", "description": "Замена рессоры", "planned_end": "2026-12-01"})
    assert r.status_code == 200 and r.json()["status"] == "repair" and r.json()["current"]["mechanic"]
    assert client.post("/api/vehicles/4/maintenance", headers=mech, json={"kind": "ТО"}).status_code == 409
    r = client.post("/api/vehicles/4/maintenance/finish", headers=mech, json={})
    assert r.json()["status"] == "on_line" and r.json()["current"] is None
    assert r.json()["history"][0]["finished_at"]


def test_service_resets_counter(client):
    mech = login(client, "mechanic")
    before = client.get("/api/vehicles/1", headers=mech).json()
    client.post("/api/vehicles/1/maintenance", headers=mech, json={"kind": "ТО"})
    r = client.post("/api/vehicles/1/maintenance/finish", headers=mech, json={"counter": before["odometer_km"] + 10}).json()
    assert r["odometer_km"] == before["odometer_km"] + 10 and r["service_left"] == r["service_interval"]


def test_counter_cannot_decrease(client):
    mech = login(client, "mechanic")
    v = client.get("/api/vehicles/1", headers=mech).json()
    assert client.patch("/api/vehicles/1", headers=mech, json={"counter": v["odometer_km"] - 1}).status_code == 422


def test_truck_in_repair_is_not_planned(client, manager):
    client.post("/api/vehicles/1/maintenance", headers=login(client, "mechanic"), json={"kind": "ремонт"})
    make_delivery_order(client, manager, volume=300)
    p = client.post("/api/route-plans", headers=manager, json={"plan_date": TODAY}).json()
    assert p["trips"] and all(t["vehicle_id"] != 1 for t in p["trips"])


def test_repair_after_approval_blocks_and_trip_can_be_moved(client, manager):
    make_delivery_order(client, manager, volume=30)
    p = plan_and_approve(client, manager)
    trip = p["trips"][0]
    client.post(f"/api/vehicles/{trip['vehicle_id']}/maintenance", headers=login(client, "mechanic"), json={"kind": "ремонт"})
    p2 = client.get("/api/route-plans", headers=manager, params={"plan_date": TODAY}).json()
    assert p2["blocked"] == [trip["id"]]
    other = 8 if trip["vehicle_id"] != 8 else 7
    r = client.patch(f"/api/route-plans/{p['id']}/trips/{trip['id']}", headers=manager, json={"vehicle_id": other})
    assert r.status_code == 200 and r.json()["blocked"] == []
    # новый водитель видит рейс у себя
    d = login(client, f"driver{other}")
    assert [t["id"] for t in client.get("/api/trips/my", headers=d).json()["trips"]] == [trip["id"]]


def test_delivery_adds_mileage(client, manager):
    make_delivery_order(client, manager, volume=30)
    trip = plan_and_approve(client, manager)["trips"][0]
    mech = login(client, "mechanic")
    km0 = client.get(f"/api/vehicles/{trip['vehicle_id']}", headers=mech).json()["odometer_km"]
    d = login(client, f"driver{trip['vehicle_id']}")
    client.post(f"/api/trips/{trip['id']}/load", headers=d, json={})
    client.post(f"/api/trips/{trip['id']}/deliver", headers=d, json={"actual_m3": 30})
    km1 = client.get(f"/api/vehicles/{trip['vehicle_id']}", headers=mech).json()["odometer_km"]
    assert km1 - km0 == round(float(trip["distance_km"]))


def test_reassign_driver_moves_from_old_truck(client):
    mech = login(client, "mechanic")
    drivers = client.get("/api/drivers", headers=mech).json()
    d9 = next(d for d in drivers if d["vehicle_name"] is None)
    r = client.patch("/api/vehicles/2", headers=mech, json={"driver_id": d9["id"]})
    assert r.json()["driver_id"] == d9["id"]
    r = client.patch("/api/vehicles/3", headers=mech, json={"driver_id": d9["id"]})
    assert client.get("/api/vehicles/2", headers=mech).json()["driver_id"] is None
    assert client.patch("/api/vehicles/9", headers=mech, json={"driver_id": d9["id"]}).status_code == 422  # экскаватор
