from fastapi import FastAPI
from app.auth.router import router as auth_router
from app.routers.clientes import router as clientes_router
from app.routers.ingesta import router as ingesta_router
from app.routers.resumen import router as resumen_router
from app.routers.reglas import router as reglas_router

app = FastAPI(title="Sistema XML")
app.include_router(auth_router)
app.include_router(clientes_router)
app.include_router(ingesta_router)
app.include_router(resumen_router)
app.include_router(reglas_router)

@app.get("/health")
def health():
    return {"status": "ok"}
