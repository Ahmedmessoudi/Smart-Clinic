"""
Patient stroke risk prediction route.

Uses the trained RandomForestClassifier model (retrained with sklearn 1.8.0).
Input: 10 raw features -> one-hot encode -> scale -> predict.
"""
import os
import joblib
import numpy as np
import pandas as pd
from fastapi import APIRouter
from schemas.prediction import PatientPredictionRequest, PatientPredictionResponse

router = APIRouter(prefix="/predict", tags=["Patient Prediction"])

# ===== Load trained model artifacts at startup =====
MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "models")

try:
    _model = joblib.load(os.path.join(MODEL_DIR, "patient_model.pkl"))
    _scaler = joblib.load(os.path.join(MODEL_DIR, "patient_scaler.pkl"))
    _columns = joblib.load(os.path.join(MODEL_DIR, "patient_columns.pkl"))
    MODEL_LOADED = True
    print(f"[ML] Patient model loaded: RandomForestClassifier ({len(_columns)} features)")
except Exception as e:
    MODEL_LOADED = False
    print(f"[ML] Patient model FAILED to load: {e}")


@router.post("/patient", response_model=PatientPredictionResponse)
async def predict_stroke_risk(request: PatientPredictionRequest):
    """
    Predict stroke risk from patient features using trained RandomForest model.
    Falls back to rule-based calculator if model is unavailable.
    """
    if MODEL_LOADED:
        return _predict_with_model(request)
    else:
        return _fallback_prediction(request)


def _predict_with_model(req: PatientPredictionRequest) -> PatientPredictionResponse:
    """Run inference with the trained RandomForest model."""
    # Build raw feature dict matching the training data columns
    raw = {
        "age": req.age,
        "hypertension": int(req.hypertension),
        "heart_disease": int(req.heart_disease),
        "avg_glucose_level": req.avg_glucose_level,
        "bmi": req.bmi,
        # One-hot: gender
        "gender_Female": 1 if req.gender.lower() == "female" else 0,
        "gender_Male": 1 if req.gender.lower() == "male" else 0,
        "gender_Other": 1 if req.gender.lower() == "other" else 0,
        # One-hot: ever_married
        "ever_married_No": 0 if req.ever_married else 1,
        "ever_married_Yes": 1 if req.ever_married else 0,
        # One-hot: work_type
        "work_type_Govt_job": 1 if req.work_type == "Govt_job" else 0,
        "work_type_Never_worked": 1 if req.work_type == "Never_worked" else 0,
        "work_type_Private": 1 if req.work_type == "Private" else 0,
        "work_type_Self-employed": 1 if req.work_type == "Self-employed" else 0,
        "work_type_children": 1 if req.work_type == "children" else 0,
        # One-hot: Residence_type
        "Residence_type_Rural": 1 if req.residence_type == "Rural" else 0,
        "Residence_type_Urban": 1 if req.residence_type == "Urban" else 0,
        # One-hot: smoking_status
        "smoking_status_formerly smoked": 1 if req.smoking_status == "formerly smoked" else 0,
        "smoking_status_never smoked": 1 if req.smoking_status == "never smoked" else 0,
        "smoking_status_smokes": 1 if req.smoking_status == "smokes" else 0,
    }

    # Build DataFrame with correct column order
    df = pd.DataFrame([raw], columns=_columns)

    # Scale
    X_scaled = _scaler.transform(df)

    # Predict
    prediction = _model.predict(X_scaled)[0]
    probabilities = _model.predict_proba(X_scaled)[0]

    # Convert to risk percentage (probability of stroke class)
    stroke_prob = probabilities[1] if len(probabilities) > 1 else probabilities[0]

    # Recalibrate: the model is trained on imbalanced data (~5% stroke)
    # so raw probabilities are very conservative (max ~40% even for extreme cases).
    # Apply sigmoid recalibration to produce clinically meaningful risk scores.
    import math
    calibrated = 1.0 / (1.0 + math.exp(-12 * (stroke_prob - 0.12)))
    risk_percentage = round(float(calibrated) * 100, 2)
    risk_percentage = max(2.0, min(risk_percentage, 98.0))  # clamp to [2, 98]

    print(f"[ML] Patient raw prob: {stroke_prob:.4f} -> calibrated: {risk_percentage:.1f}%")

    risk_level = _determine_level(risk_percentage)
    recommendations = _generate_recommendations(risk_level, req)

    return PatientPredictionResponse(
        risk_percentage=risk_percentage,
        risk_level=risk_level,
        recommendations=recommendations,
        model_version="random-forest-v2",
        features_used=len(_columns)
    )


def _fallback_prediction(req: PatientPredictionRequest) -> PatientPredictionResponse:
    """Rule-based fallback when model is unavailable."""
    risk = 5.0
    if req.hypertension:
        risk += 25.0
    if req.heart_disease:
        risk += 20.0
    if req.age > 55:
        risk += 15.0
    elif req.age > 45:
        risk += 8.0
    if req.avg_glucose_level > 200:
        risk += 20.0
    elif req.avg_glucose_level > 150:
        risk += 12.0
    if req.bmi > 35:
        risk += 12.0
    elif req.bmi > 30:
        risk += 8.0
    if req.smoking_status and req.smoking_status.lower() == "smokes":
        risk += 10.0
    elif req.smoking_status and req.smoking_status.lower() == "formerly smoked":
        risk += 5.0
    risk = min(risk, 99.0)

    risk_level = _determine_level(risk)
    recommendations = _generate_recommendations(risk_level, req)

    return PatientPredictionResponse(
        risk_percentage=round(risk, 2),
        risk_level=risk_level,
        recommendations=recommendations,
        model_version="rule-based-fallback",
        features_used=10
    )


def _determine_level(percentage: float) -> str:
    if percentage < 20:
        return "LOW"
    elif percentage < 45:
        return "MODERATE"
    elif percentage < 70:
        return "HIGH"
    return "CRITICAL"


def _generate_recommendations(level: str, req: PatientPredictionRequest) -> str:
    recs = {
        "LOW": "Maintain a healthy lifestyle. Schedule annual checkups.",
        "MODERATE": "Monitor blood pressure regularly. Consider dietary changes. Consult your physician.",
        "HIGH": "Consult a neurologist immediately. Begin preventive medication. Regular monitoring required.",
        "CRITICAL": "URGENT: Seek emergency medical evaluation. Immediate specialist referral required."
    }
    msg = recs.get(level, "")
    if req.hypertension:
        msg += " Manage hypertension with prescribed medication."
    if req.bmi > 30:
        msg += " Weight management program recommended."
    if req.smoking_status and "smokes" in req.smoking_status.lower():
        msg += " Smoking cessation is strongly advised."
    return msg
