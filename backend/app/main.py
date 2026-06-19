from fastapi import FastAPI

app = FastAPI(title="Sistema XML")

@app.get("/health")
def health():
    return {"status": "ok"}
