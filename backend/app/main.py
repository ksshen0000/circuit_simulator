import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import init_db
from .routers.circuits import router as circuit_router
from .routers.simulation import router as sim_router

app = FastAPI(title="Circuit Simulator API")

_cors_origins = os.environ.get("CORS_ORIGINS", "*")
origins = [o.strip() for o in _cors_origins.split(",")] if _cors_origins != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup():
    init_db()

app.include_router(sim_router)
app.include_router(circuit_router)
