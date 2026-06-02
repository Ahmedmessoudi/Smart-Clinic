"""
AVC Healthcare Platform — ML Microservice

FastAPI application serving two ML models:
1. Patient stroke risk predictor (tabular, 12 features)
2. Specialist CT-scan classifier (image → stroke type)

Runs on port 8000 by default.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes.patient_predict import router as patient_router, MODEL_LOADED as patient_model_loaded
from routes.specialist_predict import router as specialist_router, MODEL_LOADED as specialist_model_loaded
from schemas.prediction import HealthResponse

app = FastAPI(
    title="AVC ML Service",
    description="Machine Learning microservice for stroke risk prediction and CT-scan classification",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS — allow Spring Boot backend to call this service
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080", "http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(patient_router)
app.include_router(specialist_router)


@app.get("/", response_model=HealthResponse)
async def health_check():
    """ML Service health check."""
    return HealthResponse(
        status="UP",
        service="AVC ML Service",
        version="1.0.0",
        models_loaded={
            "tabular_stroke_predictor": "RandomForestClassifier (loaded)" if patient_model_loaded else "rule-based-fallback (active)",
            "ct_scan_classifier": "ResNeXt50_32X4D (loaded)" if specialist_model_loaded else "failed-to-load"
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
