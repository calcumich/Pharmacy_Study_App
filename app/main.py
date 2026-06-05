from fastapi import FastAPI
from fastapi import Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

import app.models  # Ensure all ORM models are registered before route use.
from app.config import settings
from app.db.session import get_db
from app.routers import attribute_types, drug_classes, drugs, study

app = FastAPI(
    title="Pharmacy Study App",
    description="Spaced-repetition study tool for pharmacy students.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(drug_classes.router)
app.include_router(drugs.router)
app.include_router(attribute_types.router)
app.include_router(study.router)


@app.get("/health", tags=["meta"])
async def health(db: AsyncSession = Depends(get_db)) -> dict:
    try:
        await db.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc
    return {"status": "ok", "db": "ok"}
