"""
OcuScan — Dual Model Eye Disease Classification API
─────────────────────────────────────────────────────
Modèle 1 (Keras .h5)  : Images rétiniennes (fond d'œil)
  Dataset : Kaggle – Eye Diseases Classification
  Entrée  : 300×300×3
  Classes : 8 (rétine)

Modèle 2 (PyTorch .pth) : Images extérieures de l'œil
  Dataset : Mendeley – n9zp473wfw
  Backbone: EfficientNet-B4
  Entrée  : 380×380×3
  Classes : 5 (externe)
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import numpy as np
from PIL import Image
import io, os, logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# Configuration des deux modèles
# ══════════════════════════════════════════════════════════════════════════════

# ── Modèle 1 : Rétine (Keras) ─────────────────────────────────────────────────
RETINA_MODEL_PATH   = os.getenv("RETINA_MODEL_PATH", "best_model_final.h5")
RETINA_IMG_SIZE     = (300, 300)
RETINA_CLASS_NAMES  = [
    "Cataract",
    "Diabetic Retinopathy",
    "Glaucoma",
    "Normal",
    "Age-related Macular Degeneration",
    "Hypertensive Retinopathy",
    "Myopia",
    "Other Pathology",
]

# ── Modèle 2 : Œil externe (PyTorch EfficientNet-B4) ─────────────────────────
EXTERNAL_MODEL_PATH  = os.getenv("EXTERNAL_MODEL_PATH", "eye_disease_best.pth")
EXTERNAL_IMG_SIZE    = (380, 380)
# ⚠️ Ajuste l'ordre alphabétique selon tes dossiers d'entraînement
EXTERNAL_CLASS_NAMES = [
    "Conjunctivitis",
    "Corneal Disease",
    "Normal",
    "Pterygium",
    "Uveitis",
]
# Normalisation ImageNet (standard EfficientNet)
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD  = [0.229, 0.224, 0.225]

# ══════════════════════════════════════════════════════════════════════════════
# Chargement des modèles (lazy)
# ══════════════════════════════════════════════════════════════════════════════

_retina_model   = None
_external_model = None



def load_retina_model():
    global _retina_model
    if _retina_model is None:
        if not os.path.exists(RETINA_MODEL_PATH):
            raise RuntimeError(f"Fichier introuvable : {RETINA_MODEL_PATH}")
        loaded = False
        last_err = None
        # Stratégie 1 : keras standalone (keras>=3, compatible TF 2.16+)
        try:
            import keras
            logger.info(f"[Retine] keras {keras.__version__} - {RETINA_MODEL_PATH}")
            # keras 3 : on force le backend TF pour les fichiers .h5 legacy
            _retina_model = keras.models.load_model(RETINA_MODEL_PATH, compile=False)
            loaded = True
        except Exception as e:
            logger.warning(f"[Retine] keras echoue : {e}")
            last_err = e
        # Stratégie 2 : tf.keras via l'attribut keras de TensorFlow
        if not loaded:
            try:
                import tensorflow as tf
                # TF 2.16+ expose tf.keras via le module keras standalone
                tf_version = getattr(tf, "__version__", None) or getattr(tf, "version", {}).get("VERSION", "?")
                logger.info(f"[Retine] tf {tf_version} - {RETINA_MODEL_PATH}")
                keras_mod = getattr(tf, "keras", None)
                if keras_mod is None:
                    raise ImportError("tf.keras introuvable")
                _retina_model = keras_mod.models.load_model(RETINA_MODEL_PATH, compile=False)
                loaded = True
            except Exception as e:
                logger.error(f"[Retine] tf.keras echoue : {e}")
                last_err = e
        # Stratégie 3 : h5py + reconstruction manuelle si keras indisponible
        if not loaded:
            try:
                from tensorflow.python.keras.models import load_model as _load_model  # type: ignore
                logger.info("[Retine] Tentative via tensorflow.python.keras")
                _retina_model = _load_model(RETINA_MODEL_PATH, compile=False)
                loaded = True
            except Exception as e:
                logger.error(f"[Retine] tensorflow.python.keras echoue : {e}")
                last_err = e
        if not loaded:
            raise RuntimeError(f"Impossible de charger le modele retine : {last_err}")
        logger.info("Modele retine charge - sortie : %s", _retina_model.output_shape)
    return _retina_model


def load_external_model():
    global _external_model
    if _external_model is None:
        if not os.path.exists(EXTERNAL_MODEL_PATH):
            raise RuntimeError(f"Fichier introuvable : {EXTERNAL_MODEL_PATH}")
        import torch
        from torchvision import models as tv_models

        logger.info(f"[Externe] torch {torch.__version__} - {EXTERNAL_MODEL_PATH}")

        state = torch.load(
            EXTERNAL_MODEL_PATH,
            map_location=torch.device("cpu"),
            weights_only=False,
        )
        logger.info(f"[Externe] type : {type(state).__name__}")

        # Cas 1 : le .pth est le modele complet
        if not isinstance(state, dict):
            _external_model = state
            _external_model.eval()
            logger.info("[Externe] Modele complet charge directement")
            return _external_model

        # Cas 2 : extraire le state_dict
        if "model_state_dict" in state:
            state_dict = state["model_state_dict"]
        elif "state_dict" in state:
            state_dict = state["state_dict"]
        else:
            state_dict = state

        # Detecter le nombre de classes : dernier biais de type (N,) avec N petit
        # On cherche le biais de la couche de sortie finale du classifier
        clf_biases = [(k, v) for k, v in state_dict.items()
                      if "classifier" in k and k.endswith(".bias") and v.dim() == 1]
        # La couche finale est celle dont le biais correspond au nombre de classes (la plus petite)
        if clf_biases:
            # Trouver le biais associé au dernier Linear (celui dont weight a shape [N, M] et M != N)
            clf_linear_keys = [k for k, v in state_dict.items()
                               if "classifier" in k and k.endswith(".weight") and v.dim() == 2]
            # Le dernier Linear classifier est la couche de sortie
            last_linear_key = clf_linear_keys[-1] if clf_linear_keys else None
            if last_linear_key:
                num_classes = state_dict[last_linear_key].shape[0]
            else:
                num_classes = clf_biases[-1][1].shape[0]
        else:
            num_classes = 5  # fallback
        logger.info(f"[Externe] classes detectees : {num_classes}")

        # Detecter in_features depuis la tete du backbone (features.8.1 = BN apres conv finale)
        # features.8.1.bias a shape (C,) ou C = nb canaux de sortie du backbone
        backbone_head_candidates = [
            (k, v) for k, v in state_dict.items()
            if k.startswith("features.8") and k.endswith(".bias") and v.dim() == 1
        ]
        if backbone_head_candidates:
            in_feat = backbone_head_candidates[0][1].shape[0]
        else:
            # Fallback : premier poids Linear du classifier -> shape [hidden, in_feat]
            clf_weights = [v for k, v in state_dict.items()
                           if "classifier" in k and k.endswith(".weight") and v.dim() == 2]
            in_feat = clf_weights[0].shape[1] if clf_weights else 1792

        EFFNET_MAP = {1280: "b0", 1408: "b2", 1536: "b3", 1792: "b4", 2048: "b5", 2304: "b6", 2560: "b7"}
        variant = EFFNET_MAP.get(in_feat, "b4")
        logger.info(f"[Externe] architecture : efficientnet_{variant} (in_features={in_feat})")

        builder = getattr(tv_models, f"efficientnet_{variant}")
        net = builder(weights=None)

        # Reconstruire le classifier pour correspondre exactement au checkpoint.
        # On reconstruit un Sequential avec les mêmes indices que le checkpoint
        # afin que load_state_dict trouve chaque clé (classifier.1, classifier.3, classifier.5…).
        from collections import OrderedDict as _OD
        clf_indices = sorted(set(
            int(k.split(".")[1])
            for k in state_dict if k.startswith("classifier.")
        ))
        clf_od = _OD()
        prev_idx = -1
        for idx in clf_indices:
            # Combler les "trous" d'indices avec des activations/Dropout sans poids
            if prev_idx >= 0:
                gap = idx - prev_idx
                if gap == 2:
                    # Un slot vide entre deux couches : on insère un ReLU
                    clf_od[str(prev_idx + 1)] = torch.nn.ReLU(inplace=True)
            w_key = f"classifier.{idx}.weight"
            rm_key = f"classifier.{idx}.running_mean"
            if w_key in state_dict:
                w = state_dict[w_key]
                if w.dim() == 2:          # Couche Linear
                    out_f, in_f = w.shape
                    clf_od[str(idx)] = torch.nn.Linear(in_f, out_f)
                elif w.dim() == 1 and rm_key in state_dict:  # BatchNorm1d
                    clf_od[str(idx)] = torch.nn.BatchNorm1d(w.shape[0])
            prev_idx = idx
        if clf_od:
            net.classifier = torch.nn.Sequential(clf_od)
        else:
            net.classifier[1] = torch.nn.Linear(in_feat, num_classes)

        missing, unexpected = net.load_state_dict(state_dict, strict=False)
        if missing:
            logger.warning(f"[Externe] cles manquantes ({len(missing)}) : {missing[:3]}")
        if unexpected:
            logger.warning(f"[Externe] cles inattendues ({len(unexpected)}) : {unexpected[:3]}")

        net.eval()
        _external_model = net
        logger.info("[Externe] Modele charge avec succes")
    return _external_model


# ══════════════════════════════════════════════════════════════════════════════
# Prétraitement
# ══════════════════════════════════════════════════════════════════════════════

def preprocess_retina(file_bytes: bytes) -> np.ndarray:
    """300×300, normalisation [0,1], shape (1,300,300,3)."""
    try:
        img = Image.open(io.BytesIO(file_bytes)).convert("RGB")
        img = img.resize(RETINA_IMG_SIZE, Image.LANCZOS)
        arr = np.array(img, dtype=np.float32) / 255.0
        return np.expand_dims(arr, axis=0)
    except Exception as e:
        raise ValueError(f"Image invalide : {e}")


def preprocess_external(file_bytes: bytes):
    """380×380, normalisation ImageNet, tenseur PyTorch (1,3,380,380)."""
    import torch
    try:
        img = Image.open(io.BytesIO(file_bytes)).convert("RGB")
        img = img.resize(EXTERNAL_IMG_SIZE, Image.LANCZOS)
        arr = np.array(img, dtype=np.float32) / 255.0
        # Normalisation ImageNet canal par canal
        mean = np.array(IMAGENET_MEAN, dtype=np.float32)
        std  = np.array(IMAGENET_STD,  dtype=np.float32)
        arr  = (arr - mean) / std                             # (H,W,3)
        arr  = arr.transpose(2, 0, 1)                        # (3,H,W)
        return torch.tensor(arr, dtype=torch.float32).unsqueeze(0)  # (1,3,H,W)
    except Exception as e:
        raise ValueError(f"Image invalide : {e}")


# ══════════════════════════════════════════════════════════════════════════════
# Application FastAPI
# ══════════════════════════════════════════════════════════════════════════════

app = FastAPI(
    title="OcuScan — Dual Eye Disease Classifier",
    description=(
        "Deux modèles de classification des maladies oculaires :\n"
        "- `/predict?model=retina`   → Images rétiniennes (Keras)\n"
        "- `/predict?model=external` → Images extérieures (PyTorch EfficientNet)"
    ),
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


# ══════════════════════════════════════════════════════════════════════════════
# Routes
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    if os.path.exists(html_path):
        with open(html_path, encoding="utf-8") as f:
            return f.read()
    return HTMLResponse("<h1>OcuScan API v2 — voir /docs</h1>")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "retina_model_loaded":   _retina_model   is not None,
        "external_model_loaded": _external_model is not None,
    }


@app.get("/classes")
async def get_classes(model: str = Query("retina", enum=["retina", "external"])):
    """Liste des classes pour le modèle sélectionné."""
    names = RETINA_CLASS_NAMES if model == "retina" else EXTERNAL_CLASS_NAMES
    return {"model": model, "classes": names, "count": len(names)}


@app.post("/predict")
async def predict(
    file:  UploadFile = File(...),
    model: str        = Query("retina", enum=["retina", "external"]),
):
    """
    Classifie une image oculaire.

    - **model** : `retina` (fond d'œil, Keras) ou `external` (œil externe, PyTorch)
    - **file**  : image JPEG / PNG / BMP / TIFF
    """
    allowed_types = {"image/jpeg", "image/png", "image/bmp", "image/tiff", "image/webp"}
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=415,
            detail=f"Type non supporté : {file.content_type}",
        )

    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Fichier trop volumineux (max 10 Mo).")

    if model == "retina":
        # ── Inférence Keras ───────────────────────────────────────────────────
        try:
            img_array = preprocess_retina(contents)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

        try:
            net  = load_retina_model()
            preds = net.predict(img_array, verbose=0)[0]
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Erreur Keras : {e}")

        class_names = RETINA_CLASS_NAMES

    else:
        # ── Inférence PyTorch ─────────────────────────────────────────────────
        import torch, torch.nn.functional as F

        try:
            tensor = preprocess_external(contents)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

        try:
            net = load_external_model()
            with torch.no_grad():
                logits = net(tensor)[0]          # (num_classes,)
            preds = F.softmax(logits, dim=0).numpy()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Erreur PyTorch : {e}")

        class_names = EXTERNAL_CLASS_NAMES

    # ── Construction de la réponse (commun aux deux modèles) ─────────────────
    top_idx = int(np.argmax(preds))
    top3_idx = np.argsort(preds)[::-1][:3]

    return JSONResponse({
        "model":      model,
        "prediction": class_names[top_idx],
        "confidence": round(float(preds[top_idx]) * 100, 2),
        "top3": [
            {"class": class_names[i], "confidence": round(float(preds[i]) * 100, 2)}
            for i in top3_idx
        ],
        "all_probabilities": {
            class_names[i]: round(float(preds[i]) * 100, 2)
            for i in range(len(class_names))
        },
        "filename": file.filename,
    })
