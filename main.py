from flask import Flask
from users import users_bp
from courses import courses_bp

app = Flask(__name__)

app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
app.config["UPLOAD_EXTENSIONS"] = [".png"]
app.config["UPLOAD_PATH"] = "uploads"

@app.route("/")
def home():
    return "<h1> Tarpaulin API is Live</h1>"

app.register_blueprint(users_bp)
app.register_blueprint(courses_bp)
