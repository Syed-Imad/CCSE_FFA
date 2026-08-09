import os
from functools import wraps
from flask import Flask, request, jsonify, render_template, redirect, url_for, session, flash, g
from models import db, InventoryItems, User, InventoryHistory, AuditLog

app = Flask(__name__)

# Configs
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///inventory.db")  # tests override via env var
app.config["SECRET_KEY"] = "dev-secret-change-before-deployment"  # signs session cookie, use env var in prod

# Database
db.init_app(app)


# redirects to login if no session
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            g.audit_outcome = "unauthenticated"
            flash("login required", "error")
            return redirect(url_for("home"))
        return f(*args, **kwargs)
    return wrapper


# restricts route to given roles, checks login too so decorator order can't mess it up
def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                g.audit_outcome = "unauthenticated"
                flash("login required", "error")
                return redirect(url_for("home"))
            if session.get("role") not in roles:
                g.audit_outcome = "denied"
                flash("not authorised for this action", "error")
                return redirect(url_for("home"))
            return f(*args, **kwargs)
        return wrapper
    return decorator


# logs one history row per create/update/remove - snapshot of the item after the change
def record_history(item, action):
    entry = InventoryHistory(
        item_id=item.id,
        user_id=session["user_id"],
        action=action,
        name_snapshot=item.name,
        quantity_snapshot=item.quantity,
    )
    db.session.add(entry)
    db.session.commit()


# resets g each request - otherwise it can carry a stale value over from the last one
@app.before_request
def reset_audit_outcome():
    g.audit_outcome = "success"


# logs every request, denied/unauthenticated included - skips /static, not an "action"
@app.after_request
def log_request(response):
    if not request.path.startswith("/static"):
        entry = AuditLog(
            user_id=session.get("user_id"),
            path=request.path,
            method=request.method,
            outcome=g.audit_outcome,
        )
        db.session.add(entry)
        db.session.commit()
    return response


# Routes

# Route: Home - login form if logged out, dashboard if logged in
@app.route("/")
def home():
    if "user_id" not in session:
        return render_template("login.html")

    items = InventoryItems.query.filter_by(is_removed=False).all()
    return render_template("dashboard.html", items=items, username=session.get("username"), role=session.get("role"))


# Route: Inventory
@app.route("/inventory", methods=["GET"])
@login_required
def list_inventory():
    items = InventoryItems.query.filter_by(is_removed=False).all()

    return [item.to_dict() for item in items]


# Route: Inventory item - view is any role, edit/remove is officer only
@app.route("/inventory/<int:item_id>", methods=["GET", "PUT", "POST", "DELETE"])
@login_required
def inventory_item(item_id):
    item = InventoryItems.query.filter_by(id=item_id, is_removed=False).first()
    if not item:
        return jsonify({"error": "item not found"}), 404

    if request.method == "GET":
        return jsonify(item.to_dict())

    # everything below here is a write - officer only
    if session.get("role") != "command_officer":
        g.audit_outcome = "denied"
        flash("not authorised for this action", "error")
        return redirect(url_for("home"))

    # browser form can't send DELETE, so it sends _action=delete instead
    if request.method == "DELETE" or request.form.get("_action") == "delete":
        item.is_removed = True
        db.session.commit()
        record_history(item, "remove")
        flash("item removed", "success")
    else:
        name = request.form.get("name")
        quantity = request.form.get("quantity")
        if name:
            item.name = name
        if quantity:
            item.quantity = int(quantity)
        db.session.commit()
        record_history(item, "update")
        flash("item updated", "success")

    if request.method in ("PUT", "DELETE"):
        return jsonify(item.to_dict())
    return redirect(url_for("home"))


# Route: Inventory item history
@app.route("/inventory/<int:item_id>/history", methods=["GET"])
@login_required
def inventory_item_history(item_id):
    entries = InventoryHistory.query.filter_by(item_id=item_id).order_by(InventoryHistory.timestamp.desc()).all()
    return jsonify([entry.to_dict() for entry in entries])


# Route: Audit log - officer only
@app.route("/audit-log", methods=["GET"])
@role_required("command_officer")
def audit_log():
    entries = AuditLog.query.order_by(AuditLog.timestamp.desc()).all()
    return render_template("audit_log.html", entries=entries)


# Route: Login
@app.route("/login", methods=["POST"])
def login():
    username = request.form.get("username")
    password = request.form.get("password")

    user = User.query.filter_by(username=username).first()
    if not user or not user.check_password(password):
        g.audit_outcome = "failure"
        flash("invalid username or password", "error")
        return redirect(url_for("home"))

    # cookie set here, browser sends it back automatically after this
    session["user_id"] = user.id
    session["username"] = user.username
    session["role"] = user.role
    return redirect(url_for("home"))


# Route: Logout
@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("home"))


# Route: Inventory  --> Add
@app.route("/inventory/add", methods=["POST"])
@role_required("command_officer")
def add_inventory_item():
    name = request.form.get("name")
    quantity = int(request.form.get("quantity", 0) or 0)

    if not name:
        flash("name is required", "error")
        return redirect(url_for("home"))

    new_item = InventoryItems(name=name, quantity=quantity)
    db.session.add(new_item)
    db.session.commit()
    record_history(new_item, "create")

    flash("item added", "success")
    return redirect(url_for("home"))

# Route: User --> Add
@app.route("/user/add", methods=["POST"])
@role_required("command_officer")
def add_user():
    username = request.form.get("username")
    password = request.form.get("password")
    role = request.form.get("role", "cadet")

    if not username or not password:
        flash("username and password are required", "error")
        return redirect(url_for("home"))

    if User.query.filter_by(username=username).first():
        flash("username already exists", "error")
        return redirect(url_for("home"))

    new_user = User(username=username, role=role)
    new_user.set_password(password)
    db.session.add(new_user)
    db.session.commit()

    flash("user created", "success")
    return redirect(url_for("home"))


# Route: Temporarily add user for testing - add ?role=command_officer for an officer
@app.route("/user/temp_add", methods=["GET"])
def temp_add_user():
    role = request.args.get("role", "cadet")
    username = "testofficer" if role == "command_officer" else "testcadet"
    password = "testpassword"

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({"error": "Username already exists"}), 400

    new_user = User(username=username, role=role)
    new_user.set_password(password)
    db.session.add(new_user)
    db.session.commit()

    return jsonify({"message": "User created successfully"}), 201

# Route: Temporarily add item for testing
@app.route("/item/temp_add", methods=["GET"])
def temp_add_item():
    data = {"name": "Test Item", "quantity": 10}
    name = data.get("name")
    quantity = data.get("quantity", 0)

    if not name:
        return jsonify({"error": "Name is required"}), 400

    new_item = InventoryItems(name=name, quantity=quantity)
    db.session.add(new_item)
    db.session.commit()

    return jsonify(new_item.to_dict()), 201


# Run Application
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
