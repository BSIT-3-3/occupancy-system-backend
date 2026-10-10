from database import create_app

app = create_app()

@app.get("/")
def root():
    return {"message": "Room Monitoring Backend"}

@app.get("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    app.run(debug=True)