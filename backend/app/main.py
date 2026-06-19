from fastapi import FastAPI
from app.auth.router import router as auth_router
from app.routers.clientes import router as clientes_router

app = FastAPI(title="Sistema XML")
app.include_router(auth_router)
app.include_router(clientes_router)

@app.get("/health")
def health():
    return {"status": "ok"}
