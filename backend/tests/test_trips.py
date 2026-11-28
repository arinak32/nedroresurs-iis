from datetime import date, timedelta

from tests.conftest import login

TODAY = date.today().isoformat()


def make_delivery_order(client, h, volume=90, client_id=1):
    c = next(x for x in client.get("/api/clients", headers=h).json() if x["id"] == client_id)
    o = client.post("/api/orders", headers=h, json={"client_id": c["id"], "product_id": 1, "volume_m3": volume,
                                                    "method": "delivery", "address_id": c["addresses"][0]["id"]}).json()
    for a in ("issue_invoice", "mark_paid"):
        assert client.post(f"/api/orders/{o['id']}/status", headers=h, json={"action": a}).status_code == 200
    return o


def plan_and_approve(client, h, day=TODAY):
    p = client.post("/api/route-plans", headers=h, json={"plan_date": day})
    assert p.status_code == 201, p.text
    p = p.json()
    assert client.post(f"/api/route-plans/{p['id']}/approve", headers=h).status_code == 200
    return p


def test_plan_splits_order_into_truck_loads(client, manager):
    make_delivery_order(client, manager, volume=100)
    p = client.post("/api/route-plans", headers=manager, json={"plan_date": TODAY}).json()
    vols = sorted(float(t["planned_m3"]) for t in p["trips"])
    assert vols == [10, 30, 30, 30]                       # 100 м³ = 3 полных рейса + 10 м³
    assert len({t["vehicle_id"] for t in p["trips"]}) == 4  # разнесены по разным самосвалам
    assert p["status"] == "draft"


def test_recalculating_draft_replaces_it(client, manager):
    make_delivery_order(client, manager, volume=60)
    client.post("/api/route-plans", headers=manager, json={"plan_date": TODAY})
    p = client.post("/api/route-plans", headers=manager, json={"plan_date": TODAY}).json()
    assert len(p["trips"]) == 2


def test_driver_full_flow(client, manager):
    before = {s["id"]: float(s["volume_m3"]) for s in client.get("/api/stock", headers=manager).json()}
    o = make_delivery_order(client, manager, volume=30)
    p = plan_and_approve(client, manager)
    trip = p["trips"][0]
    driver_login = f"driver{trip['vehicle_id']}"     # в демо-данных водитель N закреплён за самосвалом N
    d = login(client, driver_login)
    day = client.get("/api/trips/my", headers=d).json()
    assert [t["id"] for t in day["trips"]] == [trip["id"]]

    r = client.post(f"/api/trips/{trip['id']}/deliver", headers=d, json={"actual_m3": 30})
    assert r.status_code == 409                       # нельзя доставить без погрузки
    assert client.post(f"/api/trips/{trip['id']}/load", headers=d, json={"event_id": "e1"}).status_code == 200
    assert client.get(f"/api/orders/{o['id']}", headers=manager).json()["status"] == "in_delivery"

    r = client.post(f"/api/trips/{trip['id']}/deliver", headers=d, json={"actual_m3": 30, "event_id": "e2"})
    assert r.status_code == 200, r.text
    assert len(r.json()["documents"]) == 2            # ТН и УПД
    assert client.get(f"/api/orders/{o['id']}", headers=manager).json()["status"] == "shipped"
    after = {s["id"]: float(s["volume_m3"]) for s in client.get("/api/stock", headers=manager).json()}
    assert after[1] == before[1] - 30


def test_repeated_delivery_does_not_write_off_twice(client, manager):
    make_delivery_order(client, manager, volume=30)
    trip = plan_and_approve(client, manager)["trips"][0]
    d = login(client, f"driver{trip['vehicle_id']}")
    client.post(f"/api/trips/{trip['id']}/load", headers=d, json={"event_id": "a"})
    r1 = client.post(f"/api/trips/{trip['id']}/deliver", headers=d, json={"actual_m3": 30, "event_id": "b"})
    stock1 = client.get("/api/stock", headers=manager).json()[0]["volume_m3"]
    r2 = client.post(f"/api/trips/{trip['id']}/deliver", headers=d, json={"actual_m3": 30, "event_id": "b"})
    assert r1.status_code == r2.status_code == 200
    assert r1.json()["documents"] == r2.json()["documents"]
    assert client.get("/api/stock", headers=manager).json()[0]["volume_m3"] == stock1
    r3 = client.post(f"/api/trips/{trip['id']}/deliver", headers=d, json={"actual_m3": 30, "event_id": "other"})
    assert r3.status_code == 409


def test_partial_delivery_leaves_rest_for_next_plan(client, manager):
    o = make_delivery_order(client, manager, volume=30)
    trip = plan_and_approve(client, manager)["trips"][0]
    d = login(client, f"driver{trip['vehicle_id']}")
    client.post(f"/api/trips/{trip['id']}/load", headers=d, json={})
    client.post(f"/api/trips/{trip['id']}/deliver", headers=d, json={"actual_m3": 25})
    assert client.get(f"/api/orders/{o['id']}", headers=manager).json()["status"] == "in_delivery"
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    p = client.post("/api/route-plans", headers=manager, json={"plan_date": tomorrow}).json()
    assert [float(t["planned_m3"]) for t in p["trips"]] == [5]


def test_other_driver_cannot_mark_trip(client, manager):
    make_delivery_order(client, manager, volume=30)
    trip = plan_and_approve(client, manager)["trips"][0]
    other = login(client, "driver9")   # водитель без самосвала
    assert client.post(f"/api/trips/{trip['id']}/load", headers=other, json={}).status_code == 404


def test_driver_sees_only_approved_plan(client, manager):
    make_delivery_order(client, manager, volume=30)
    p = client.post("/api/route-plans", headers=manager, json={"plan_date": TODAY}).json()
    d = login(client, f"driver{p['trips'][0]['vehicle_id']}")
    assert client.get("/api/trips/my", headers=d).json()["trips"] == []


def test_move_trip_to_another_truck(client, manager):
    make_delivery_order(client, manager, volume=30)
    p = client.post("/api/route-plans", headers=manager, json={"plan_date": TODAY}).json()
    t = p["trips"][0]
    r = client.patch(f"/api/route-plans/{p['id']}/trips/{t['id']}", headers=manager, json={"vehicle_id": 5})
    assert r.status_code == 200
    assert r.json()["trips"][0]["vehicle_id"] == 5 and r.json()["trips"][0]["driver_name"] is not None


def test_shift_limit_leaves_trips_unplanned(client, manager):
    # 30 рейсов по ~23 км: 8 самосвалов × 12 ч вмещают не все
    make_delivery_order(client, manager, volume=3000)
    p = client.post("/api/route-plans", headers=manager, json={"plan_date": TODAY}).json()
    assert p["unplanned"] and len(p["trips"]) + len(p["unplanned"]) == 100
