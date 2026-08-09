from functools import wraps
from flask import Flask, request, jsonify, render_template, redirect, url_for, session, flash
from models import db, InventoryItems, User

app = Flask(__name__)

# Configs
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///inventory.db"
app.config["SECRET_KEY"] = "dev-secret-change-before-deployment"  # signs session cookie, use env var in prod

# Database
db.init_app(app)

# Create the database tables
with app.app_context():
    db.create_all()


# redirects to login if no session
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("login required", "error")
            return redirect(url_for("home"))
        return f(*args, **kwargs)
    return wrapper


# Routes

# Route: Home - login form if logged out, dashboard if logged in
@app.route("/")
def home():
    if "user_id" not in session:
        return render_template("login.html")

    items = InventoryItems.query.all()
    return render_template("dashboard.html", items=items, username=session.get("username"), role=session.get("role"))


# Route: Inventory
@app.route("/inventory", methods=["GET"])
def list_inventory():
    items = InventoryItems.query.all()

    return [item.to_dict() for item in items]


# Route: Login
@app.route("/login", methods=["POST"])
def login():
    username = request.form.get("username")
    password = request.form.get("password")

    user = User.query.filter_by(username=username).first()
    if not user or not user.check_password(password):
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
@login_required
def add_inventory_item():
    name = request.form.get("name")
    quantity = int(request.form.get("quantity", 0) or 0)

    if not name:
        flash("name is required", "error")
        return redirect(url_for("home"))

    new_item = InventoryItems(name=name, quantity=quantity)
    db.session.add(new_item)
    db.session.commit()

    flash("item added", "success")
    return redirect(url_for("home"))

# Route: User --> Add
@app.route("/user/add", methods=["POST"])
@login_required
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


# Route: Temporarily add user for testing
@app.route("/user/temp_add", methods=["GET"])
def temp_add_user():
    data = {"username": "testuser", "password": "testpassword", "role": "cadet"}
    username = data.get("username")
    password = data.get("password")
    role = data.get("role", "cadet")

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
    app.run(debug=True)
