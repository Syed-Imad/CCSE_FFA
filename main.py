from flask import Flask
from flask_sqlalchemy import SQLAlchemy 


app = Flask(__name__)

# Configs
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///inventory.db"

# Database
db = SQLAlchemy()
db.init_app(app)


# Models 
class InventoryItems(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    quantity = db.Column(db.Integer, default=0)

    def to_dict(self):
        return {"id": self.id, "name": self.name, "quantity": self.quantity}

# Create the database tables
with app.app_context():
    db.create_all()


    
# Routes 

# Route: Home 
@app.route("/")
def hello():
    return "homeee "


# Route: Inventory
@app.route("/inventory", methods=["GET"])
def list_inventory():
    items = ['gun', 'bullets', 'grenade']

    return items










# Run Application
if __name__ == "__main__":
    app.run(debug=True)