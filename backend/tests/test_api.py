from tests.conftest import login


def test_login_and_me(client):
    h = login(client, "manager")
    assert client.get("/api/auth/me", headers=h).json()["role"] == "manager"


def test_wrong_password(client):
    r = client.post("/api/auth/login", data={"username": "manager", "password": "nope"})
    assert r.status_code == 401


def test_requires_token(client):
    assert client.get("/api/orders").status_code == 401


def test_driver_cannot_see_orders(client):
    assert client.get("/api/orders", headers=login(client, "driver1")).status_code == 403


def test_quote_and_create_delivery_order(client, manager):
    clients = client.get("/api/clients", headers=manager).json()
    c = clients[0]
    addr = c["addresses"][0]
    q = client.get("/api/orders/quote", headers=manager, params={
        "product_id": 1, "volume_m3": 240, "method": "delivery", "address_id": addr["id"], "client_id": c["id"]}).json()
    assert q["enough"] is True and q["trips_needed"] == 8
    r = client.post("/api/orders", headers=manager, json={
        "client_id": c["id"], "product_id": 1, "volume_m3": 240, "method": "delivery", "address_id": addr["id"],
        "source": "etp", "procurement_no": "0127300001126000412"})
    assert r.status_code == 201, r.text
    o = r.json()
    assert o["number"].startswith("З-") and o["status"] == "new"
    assert float(o["amount"]) == float(q["amount"])


def test_delivery_needs_address(client, manager):
    r = client.post("/api/orders", headers=manager, json={"client_id": 1, "product_id": 1, "volume_m3": 30,
                                                          "method": "delivery"})
    assert r.status_code == 422


def test_pickup_flow_writes_off_stock(client, manager):
    before = {s["id"]: float(s["volume_m3"]) for s in client.get("/api/stock", headers=manager).json()}
    o = client.post("/api/orders", headers=manager, json={"client_id": 2, "product_id": 1, "volume_m3": 300,
                                                          "method": "pickup"}).json()
    assert float(o["delivery_m3"]) == 0
    for action in ("issue_invoice", "mark_paid", "pickup"):
        r = client.post(f"/api/orders/{o['id']}/status", headers=manager, json={"action": action})
        assert r.status_code == 200, r.text
    assert r.json()["status"] == "shipped"
    after = {s["id"]: float(s["volume_m3"]) for s in client.get("/api/stock", headers=manager).json()}
    assert after[1] == before[1] - 300


def test_invalid_transition(client, manager):
    o = client.post("/api/orders", headers=manager, json={"client_id": 2, "product_id": 1, "volume_m3": 30,
                                                          "method": "pickup"}).json()
    r = client.post(f"/api/orders/{o['id']}/status", headers=manager, json={"action": "close"})
    assert r.status_code == 409


def test_pickup_more_than_stock_is_rejected(client, manager):
    o = client.post("/api/orders", headers=manager, json={"client_id": 2, "product_id": 2, "volume_m3": 20000,
                                                          "method": "pickup"}).json()
    client.post(f"/api/orders/{o['id']}/status", headers=manager, json={"action": "confirm"})
    r = client.post(f"/api/orders/{o['id']}/status", headers=manager, json={"action": "pickup"})
    assert r.status_code == 409 and "недостаточно" in r.json()["detail"]


def test_production_capacity_check(client, manager):
    r = client.post("/api/production", headers=manager, json={"quarry_id": 1, "shift_date": "2026-11-24", "volume_m3": 1540})
    assert r.status_code == 201
    # площадка «Мелкий»: 18 400 + 1 540 = 19 940; ещё 4 смены по 2 600 переполнят её (30 000)
    for _ in range(3):
        assert client.post("/api/production", headers=manager,
                           json={"quarry_id": 2, "shift_date": "2026-11-24", "volume_m3": 2600}).status_code == 201
    r = client.post("/api/production", headers=manager, json={"quarry_id": 2, "shift_date": "2026-11-25", "volume_m3": 2600})
    assert r.status_code == 409 and "переполнится" in r.json()["detail"]


def test_only_admin_changes_tariffs(client, manager):
    t = client.get("/api/settings/tariffs", headers=manager).json()
    assert client.put("/api/settings/tariffs", headers=manager, json=t).status_code == 403
    t["vat_rate"] = "20"
    r = client.put("/api/settings/tariffs", headers=login(client, "admin"), json=t)
    assert r.status_code == 200 and float(r.json()["vat_rate"]) == 20
