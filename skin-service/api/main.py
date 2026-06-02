"""
================================================================
  SKIN DISEASE CLASSIFIER — FastAPI Server
================================================================

INSTALL:
  pip install fastapi uvicorn python-multipart pillow torch torchvision

RUN:
  uvicorn main:app --host 0.0.0.0 --port 8000 --reload

ENDPOINTS:
  POST /predict        → upload an image file
  POST /predict/base64 → send base64-encoded image
  GET  /classes        → list all 23 disease classes
  GET  /health         → check server is alive
  GET  /docs           → auto-generated Swagger UI (FREE!)
================================================================
"""

import io
import base64
import os
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional

import numpy as np
import torch
import torch.nn as nn
from PIL import Image
from torchvision import transforms, models

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


# ─────────────────────────────────────────────────────────────
#  CONFIG  ← Edit this path to point to your .pth file
# ─────────────────────────────────────────────────────────────

MODEL_PATH = os.getenv(
    "SKIN_MODEL_PATH",
    os.path.join(os.path.dirname(__file__), "best_model.pth")
    if os.path.exists(os.path.join(os.path.dirname(__file__), "best_model.pth"))
    else os.path.join(os.path.dirname(__file__), "..", "outputs_pro", "best_model.pth")
)


IMG_SIZE   = 300     # must match training
USE_TTA    = False   # True = more accurate but ~8x slower
TOP_K      = 3       # how many top predictions to return


# ─────────────────────────────────────────────────────────────
#  MODEL DEFINITION  (must match training code exactly)
# ─────────────────────────────────────────────────────────────

class SkinClassifier(nn.Module):
    def __init__(self, num_classes: int, head_dropout: float = 0.4):
        super().__init__()
        base = models.efficientnet_v2_s(weights=None)
        in_features = base.classifier[1].in_features
        base.classifier = nn.Identity()
        self.backbone = base
        self.head = nn.Sequential(
            nn.BatchNorm1d(in_features),
            nn.Dropout(head_dropout),
            nn.Linear(in_features, 512),
            nn.GELU(),
            nn.Dropout(head_dropout),
            nn.Linear(512, num_classes),
        )

    def forward(self, x):
        return self.head(self.backbone(x))


# ─────────────────────────────────────────────────────────────
#  TRANSFORMS
# ─────────────────────────────────────────────────────────────

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD  = [0.229, 0.224, 0.225]

def get_val_transform(img_size: int):
    return transforms.Compose([
        transforms.Resize(int(img_size * 1.15)),
        transforms.CenterCrop(img_size),
        transforms.ToTensor(),
        transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
    ])

def get_tta_transforms(img_size: int):
    size = img_size
    base = transforms.Resize(int(size * 1.15))
    tt   = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
    ])
    return [
        transforms.Compose([base, transforms.CenterCrop(size), tt]),
        transforms.Compose([base, transforms.CenterCrop(size),
                            transforms.RandomHorizontalFlip(p=1.0), tt]),
        transforms.Compose([base, transforms.CenterCrop(size),
                            transforms.RandomVerticalFlip(p=1.0), tt]),
        transforms.Compose([base, transforms.CenterCrop(size),
                            transforms.RandomRotation((10, 10)), tt]),
        transforms.Compose([base, transforms.CenterCrop(size),
                            transforms.RandomRotation((-10, -10)), tt]),
        transforms.Compose([base, transforms.CenterCrop(size),
                            transforms.RandomRotation((45, 45)), tt]),
        transforms.Compose([base, transforms.CenterCrop(int(size * 0.90)),
                            transforms.Resize((size, size)), tt]),
        transforms.Compose([base, transforms.CenterCrop(int(size * 0.95)),
                            transforms.Resize((size, size)),
                            transforms.RandomHorizontalFlip(p=1.0), tt]),
    ]


# ─────────────────────────────────────────────────────────────
#  GLOBAL MODEL STATE  (loaded once at startup)
# ─────────────────────────────────────────────────────────────

ml = {}   # holds model, class_names, device, transforms


def load_model():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"[startup] Device: {device}")

    if not Path(MODEL_PATH).exists():
        raise FileNotFoundError(f"Model not found: {MODEL_PATH}")

    ckpt = torch.load(MODEL_PATH, map_location=device)
    class_names = ckpt["class_names"]
    num_classes = ckpt["num_classes"]
    cfg         = ckpt.get("config", {})
    img_size    = cfg.get("img_size", IMG_SIZE)
    dropout     = cfg.get("head_dropout", 0.4)

    model = SkinClassifier(num_classes, head_dropout=dropout)

    # Handle SWA model keys
    state = ckpt["state_dict"]
    if any(k.startswith("module.") for k in state):
        state = {k.replace("module.", "", 1): v for k, v in state.items()}

    model.load_state_dict(state, strict=False)
    model.to(device).eval()

    ml["model"]       = model
    ml["class_names"] = class_names
    ml["num_classes"] = num_classes
    ml["device"]      = device
    ml["img_size"]    = img_size
    ml["val_tfm"]     = get_val_transform(img_size)
    ml["tta_tfms"]    = get_tta_transforms(img_size)

    print(f"[startup] Model loaded — {num_classes} classes, img_size={img_size}")


# ─────────────────────────────────────────────────────────────
#  INFERENCE HELPER
# ─────────────────────────────────────────────────────────────

def run_inference(pil_image: Image.Image, use_tta: bool = USE_TTA, topk: int = TOP_K):
    model   = ml["model"]
    device  = ml["device"]

    with torch.no_grad():
        if use_tta:
            tensors = torch.stack(
                [t(pil_image) for t in ml["tta_tfms"]], dim=0
            ).to(device)
            logits = model(tensors)
            probs  = torch.softmax(logits, dim=1).mean(dim=0).cpu().numpy()
        else:
            tensor = ml["val_tfm"](pil_image).unsqueeze(0).to(device)
            logits = model(tensor)
            probs  = torch.softmax(logits, dim=1).squeeze().cpu().numpy()

    top_indices = probs.argsort()[::-1][:topk]
    predictions = [
        {
            "rank":       int(rank + 1),
            "class":      ml["class_names"][i],
            "confidence": round(float(probs[i]), 4),
            "percent":    round(float(probs[i]) * 100, 2),
        }
        for rank, i in enumerate(top_indices)
    ]
    return predictions


# ─────────────────────────────────────────────────────────────
#  FASTAPI APP
# ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    load_model()   # runs at startup
    yield
    ml.clear()     # cleanup on shutdown

app = FastAPI(
    title="Skin Disease Classifier API",
    description="Upload a skin image and get a disease prediction from EfficientNetV2-S.",
    version="1.0.0",
    lifespan=lifespan,
)

# Allow all origins (for local testing / frontend apps)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────
#  RESPONSE SCHEMAS
# ─────────────────────────────────────────────────────────────

class Prediction(BaseModel):
    rank:       int
    class_:     str
    confidence: float
    percent:    float

    class Config:
        populate_by_name = True

class PredictResponse(BaseModel):
    top_prediction: str
    confidence:     float
    percent:        float
    all_predictions: list
    model_info: dict

class Base64Request(BaseModel):
    image_base64: str          # pure base64 string (no data:image/... prefix needed)
    use_tta:      Optional[bool] = USE_TTA
    topk:         Optional[int]  = TOP_K


# ─────────────────────────────────────────────────────────────
#  ROUTES
# ─────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    """Quick check — is the server alive and model loaded?"""
    return {
        "status":      "ok",
        "model_loaded": "model" in ml,
        "num_classes":  ml.get("num_classes"),
        "device":       str(ml.get("device")),
    }


@app.get("/classes")
def get_classes():
    """Return the list of all disease classes the model knows."""
    return {
        "num_classes": ml["num_classes"],
        "classes":     ml["class_names"],
    }


@app.post("/predict")
async def predict(
    file:    UploadFile = File(..., description="Skin image (jpg/png/webp)"),
    use_tta: bool = USE_TTA,
    topk:    int  = TOP_K,
):
    """
    **Upload an image file** and get the top-K disease predictions.

    - **file**: image file (jpg, png, webp, bmp)
    - **use_tta**: enable 8-augment TTA for higher accuracy (slower)
    - **topk**: number of top predictions to return (default 3)
    """
    # Validate content type
    allowed = {"image/jpeg", "image/png", "image/webp", "image/bmp"}
    if file.content_type not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}. Use jpg/png/webp."
        )

    try:
        contents = await file.read()
        pil_image = Image.open(io.BytesIO(contents)).convert("RGB")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cannot read image: {e}")

    predictions = run_inference(pil_image, use_tta=use_tta, topk=topk)
    top = predictions[0]

    return {
        "top_prediction": top["class"],
        "confidence":     top["confidence"],
        "percent":        top["percent"],
        "all_predictions": predictions,
        "model_info": {
            "img_size": ml["img_size"],
            "tta":      use_tta,
            "topk":     topk,
        },
    }


@app.post("/predict/base64")
async def predict_base64(body: Base64Request):
    """
    **Send a base64-encoded image** and get predictions.

    Useful when calling from JavaScript / mobile apps.

    ```json
    {
      "image_base64": "/9j/4AAQSkZJRgAB...",
      "topk": 3,
      "use_tta": false
    }
    ```
    """
    try:
        # Strip data URI prefix if present  (data:image/jpeg;base64,...)
        b64 = body.image_base64
        if "," in b64:
            b64 = b64.split(",", 1)[1]
        img_bytes = base64.b64decode(b64)
        pil_image = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid base64 image: {e}")

    predictions = run_inference(pil_image, use_tta=body.use_tta, topk=body.topk)
    top = predictions[0]

    return {
        "top_prediction":  top["class"],
        "confidence":      top["confidence"],
        "percent":         top["percent"],
        "all_predictions": predictions,
        "model_info": {
            "img_size": ml["img_size"],
            "tta":      body.use_tta,
            "topk":     body.topk,
        },
    }