
from flask import Flask

app = Flask(__name__)


@app.route("/", methods=["GET"])
def root():
    return {"message": "Room Monitoring Backend"}


@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    app.run(debug=True)
