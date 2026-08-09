import os
os.environ["DATABASE_URL"] = "sqlite:///:memory:"  # set before importing app.py, it reads this at import time

import pytest
from app import app, db
from models import User, InventoryItems, InventoryHistory, AuditLog


# fresh in-memory db per test
@pytest.fixture
def client():
    app.config["TESTING"] = True

    with app.app_context():
        db.create_all()
        yield app.test_client()
        db.session.remove()
        db.drop_all()


def make_user(username, password, role):
    user = User(username=username, role=role)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


def login(client, username, password):
    return client.post("/login", data={"username": username, "password": password}, follow_redirects=True)


# --- login ---

def test_login_success(client):
    make_user("officer1", "pw123", "command_officer")
    resp = login(client, "officer1", "pw123")
    assert b"logged in as officer1" in resp.data
    with client.session_transaction() as sess:
        assert sess["role"] == "command_officer"


def test_login_failure(client):
    make_user("officer1", "pw123", "command_officer")
    resp = login(client, "officer1", "wrongpassword")
    assert b"invalid username or password" in resp.data
    with client.session_transaction() as sess:
        assert "user_id" not in sess


# --- RBAC ---

def test_cadet_blocked_from_add_item(client):
    make_user("cadet1", "pw123", "cadet")
    login(client, "cadet1", "pw123")
    resp = client.post("/inventory/add", data={"name": "phaser", "quantity": "5"}, follow_redirects=True)
    assert b"not authorised for this action" in resp.data
    with app.app_context():
        assert InventoryItems.query.count() == 0


def test_officer_permitted_to_add_item(client):
    make_user("officer1", "pw123", "command_officer")
    login(client, "officer1", "pw123")
    resp = client.post("/inventory/add", data={"name": "phaser", "quantity": "5"}, follow_redirects=True)
    assert b"item added" in resp.data
    with app.app_context():
        assert InventoryItems.query.count() == 1


# --- history ---

def test_history_recorded_for_create_update_remove(client):
    make_user("officer1", "pw123", "command_officer")
    login(client, "officer1", "pw123")

    client.post("/inventory/add", data={"name": "tricorder", "quantity": "5"})
    with app.app_context():
        item_id = InventoryItems.query.first().id

    client.put(f"/inventory/{item_id}", data={"quantity": "9"})
    client.delete(f"/inventory/{item_id}")

    with app.app_context():
        history = InventoryHistory.query.filter_by(item_id=item_id).order_by(InventoryHistory.id).all()
        actions = [h.action for h in history]
        assert actions == ["create", "update", "remove"]
        assert history[1].quantity_snapshot == 9


# --- audit log ---

def test_audit_log_covers_unauthenticated_denied_and_success(client):
    make_user("cadet1", "pw123", "cadet")

    # unauthenticated attempt - no session yet
    client.get("/inventory")
    with app.app_context():
        entry = AuditLog.query.filter_by(path="/inventory", outcome="unauthenticated").first()
        assert entry is not None
        assert entry.user_id is None

    # denied - logged in but wrong role
    login(client, "cadet1", "pw123")
    client.post("/inventory/add", data={"name": "x", "quantity": "1"})
    with app.app_context():
        denied = AuditLog.query.filter_by(path="/inventory/add", outcome="denied").first()
        assert denied is not None
        assert denied.user_id is not None

    # success - the login itself
    with app.app_context():
        success = AuditLog.query.filter_by(path="/login", outcome="success").first()
        assert success is not None
