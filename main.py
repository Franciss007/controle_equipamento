from flask import Flask
from config import SECRET_KEY
from routes import register_routes

app = Flask(__name__)
app.secret_key = SECRET_KEY

register_routes(app)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
