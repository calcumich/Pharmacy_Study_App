from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.models  # Ensure all ORM models are registered before route use.
from app.routers import attribute_types, drug_classes, drugs, study

app = FastAPI(
    title="Pharmacy Study App",
    description="Spaced-repetition study tool for pharmacy students.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(drug_classes.router)
app.include_router(drugs.router)
app.include_router(attribute_types.router)
app.include_router(study.router)


@app.get("/health", tags=["meta"])
async def health() -> dict:
    return {"status": "ok"}
