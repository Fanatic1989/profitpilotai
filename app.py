from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# Database configuration (SQLite for simplicity)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# User model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)

    def to_dict(self):
        return {"id": self.id, "username": self.username, "email": self.email}

# Create DB
with app.app_context():
    db.create_all()

# Route: Home -> Admin Dashboard
@app.route("/")
def home():
    return render_template("admin.html")

# Route: Get all users
@app.route("/get_users", methods=["GET"])
def get_users():
    users = User.query.all()
    return jsonify([user.to_dict() for user in users])

# Route: Add user
@app.route("/add_user", methods=["POST"])
def add_user():
    try:
        data = request.json
        username = data.get("username")
        email = data.get("email")

        if not username or not email:
            return jsonify({"error": "Missing username or email"}), 400

        new_user = User(username=username, email=email)
        db.session.add(new_user)
        db.session.commit()

        return jsonify({"message": "User added successfully", "user": new_user.to_dict()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
