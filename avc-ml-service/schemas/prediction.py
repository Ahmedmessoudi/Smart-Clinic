"""
Pydantic schemas for ML prediction requests and responses.
"""
from pydantic import BaseModel, Field
from typing import Optional


class PatientPredictionRequest(BaseModel):
    """12-feature input for the tabular stroke risk model."""
    gender: str = Field(..., description="Male or Female")
    age: float = Field(..., ge=1, le=120, description="Patient age")
    hypertension: bool = Field(..., description="Has hypertension")
    heart_disease: bool = Field(..., description="Has heart disease")
    ever_married: Optional[bool] = Field(None, description="Ever married")
    work_type: Optional[str] = Field(None, description="Private, Govt_job, Self-employed, etc.")
    residence_type: Optional[str] = Field(None, description="Urban or Rural")
    avg_glucose_level: float = Field(..., ge=30, le=500, description="Average glucose level")
    bmi: float = Field(..., ge=10, le=80, description="Body Mass Index")
    smoking_status: Optional[str] = Field(None, description="formerly smoked, never smoked, smokes")


class PatientPredictionResponse(BaseModel):
    """Output from the tabular stroke risk model."""
    risk_percentage: float
    risk_level: str  # LOW, MODERATE, HIGH, CRITICAL
    recommendations: str
    model_version: str = "rule-based-v1"
    features_used: int = 10


class CtScanPredictionResponse(BaseModel):
    """Output from the CT-scan image classifier."""
    classification: str  # NORMAL, ISCHEMIC_STROKE, HEMORRHAGIC_STROKE
    confidence: float
    heatmap_url: Optional[str] = None
    model_version: str = "cnn-v1"


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    service: str
    version: str
    models_loaded: dict
