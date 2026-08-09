from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

# put db here instead of app.py to avoid circular import
db = SQLAlchemy()


# InventoryItems table
class InventoryItems(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    quantity = db.Column(db.Integer, default=0)
    is_removed = db.Column(db.Boolean, default=False, nullable=False)  # soft delete flag, real row stays for history later

    def to_dict(self):
        return {"id": self.id, "name": self.name, "quantity": self.quantity}


# User table
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='cadet')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


# one row per create/update/remove - snapshot after the change, not a diff
class InventoryHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey("inventory_items.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    action = db.Column(db.String(20), nullable=False)  # create / update / remove
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    name_snapshot = db.Column(db.String(80), nullable=False)
    quantity_snapshot = db.Column(db.Integer, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "item_id": self.item_id,
            "user_id": self.user_id,
            "action": self.action,
            "timestamp": self.timestamp.isoformat(),
            "name": self.name_snapshot,
            "quantity": self.quantity_snapshot,
        }


# one row per request - user_id null means not logged in at the time
class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    path = db.Column(db.String(200), nullable=False)
    method = db.Column(db.String(10), nullable=False)
    outcome = db.Column(db.String(20), nullable=False)  # success / denied / unauthenticated / failure
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "path": self.path,
            "method": self.method,
            "outcome": self.outcome,
            "timestamp": self.timestamp.isoformat(),
        }
