from fastapi import FastAPI

from app.api.datasets import router as datasets_router
from app.api.health import router as health_router

app = FastAPI(title="AI Analyst API", version="0.1.0")
app.include_router(health_router, prefix="/api")
app.include_router(datasets_router, prefix="/api")
