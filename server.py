from fastapi import FastAPI

app = FastAPI(
    title="Room Monitoring Backend",
    version="1.0.0",
)

@app.get("/")
def root():
    return {"message": "Room Monitoring Backend"}

@app.get("/health")
def health():
    return {"status": "ok"}
