"""
CT-Scan image classification route (Specialist only).

Uses a pre-trained ResNeXt50_32X4D CNN model fine-tuned on ~20k brain CT images.
Classes:
  0 - Normal
  1 - Bleeding  (Hemorrhagic Stroke)
  2 - Ischemia  (Ischemic Stroke)
"""
import os
import io
import torch
import torch.nn as nn
from torchvision import models, transforms
from PIL import Image
from fastapi import APIRouter, UploadFile, File
from schemas.prediction import CtScanPredictionResponse

router = APIRouter(prefix="/predict", tags=["Specialist CT-Scan"])

# ===== Model setup =====
MODEL_PATH = os.path.join(
    os.path.dirname(__file__), "..", "models", "model for specialist", "best_brain_ct_model.pth"
)

CLASS_NAMES = ["NORMAL", "HEMORRHAGIC_STROKE", "ISCHEMIC_STROKE"]

DEVICE = torch.device("cpu")

# Image preprocessing — must match training pipeline (ImageNet normalization)
_inference_transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406],
                         std=[0.229, 0.224, 0.225]),
])


def _build_model() -> nn.Module:
    """Reconstruct the ResNeXt50 architecture and load trained weights."""
    model = models.resnext50_32x4d(weights=None)
    num_features = model.fc.in_features
    model.fc = nn.Linear(num_features, 3)  # 3 classes
    return model


# Load model at startup
try:
    _model = _build_model()
    _model.load_state_dict(torch.load(MODEL_PATH, map_location=DEVICE))
    _model.to(DEVICE)
    _model.eval()
    MODEL_LOADED = True
    print(f"[ML] CT-Scan CNN model loaded: ResNeXt50_32X4D (3 classes) from {MODEL_PATH}")
except Exception as e:
    _model = None
    MODEL_LOADED = False
    print(f"[ML] CT-Scan CNN model FAILED to load: {e}")


def _preprocess_image(image_bytes: bytes) -> torch.Tensor:
    """Load image bytes, convert to RGB, apply transforms, return batch tensor."""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    tensor = _inference_transform(img)
    return tensor.unsqueeze(0)  # add batch dimension


@router.post("/specialist", response_model=CtScanPredictionResponse)
async def classify_ct_scan(image: UploadFile = File(..., description="CT-Scan image file")):
    """Classify a brain CT-scan for stroke detection using the ResNeXt50 CNN model."""
    contents = await image.read()

    if len(contents) == 0:
        return CtScanPredictionResponse(
            classification="ERROR", confidence=0.0, model_version="error"
        )

    if not MODEL_LOADED or _model is None:
        return CtScanPredictionResponse(
            classification="ERROR",
            confidence=0.0,
            model_version="model-not-loaded",
        )

    try:
        # Preprocess
        input_tensor = _preprocess_image(contents).to(DEVICE)

        # Inference
        with torch.no_grad():
            outputs = _model(input_tensor)
            probabilities = torch.softmax(outputs, dim=1)[0]

        # Extract results
        confidence, predicted_idx = torch.max(probabilities, 0)
        classification = CLASS_NAMES[predicted_idx.item()]
        conf_value = round(confidence.item(), 4)

        # Log probabilities
        probs_dict = {CLASS_NAMES[i]: round(probabilities[i].item(), 4) for i in range(3)}
        print(f"[ML] CT-Scan CNN -> {probs_dict} => {classification} ({conf_value:.1%})")

        return CtScanPredictionResponse(
            classification=classification,
            confidence=conf_value,
            heatmap_url=None,
            model_version="resnext50-v1",
        )
    except Exception as e:
        print(f"[ML] CT-Scan CNN error: {e}")
        return CtScanPredictionResponse(
            classification="ERROR",
            confidence=0.0,
            heatmap_url=None,
            model_version=f"error: {str(e)[:50]}",
        )
