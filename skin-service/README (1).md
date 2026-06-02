# 🩺 Skin Disease Classifier — FastAPI

Classification de 23 maladies cutanées avec EfficientNetV2-S.

---

## 📁 Structure attendue du projet

```
my_skin_project/
├── api/
│   └── main.py              ← le serveur FastAPI
├── outputs_pro/
│   └── best_model.pth       ← le modèle entraîné (à télécharger séparément)
├── Dockerfile
├── requirements.txt
└── README.md
```

---

## 🚀 Option 1 — Lancer avec Docker (recommandé)

### Prérequis
- Installer [Docker Desktop](https://www.docker.com/products/docker-desktop/)

### Étapes

**1. Construire l'image Docker**
```bash
docker build -t skin-classifier .
```

**2. Lancer le conteneur**
```bash
docker run -p 8000:8000 skin-classifier
```

**3. Ouvrir dans le navigateur**
```
http://localhost:8000/docs
```

C'est tout ! L'API est prête.

---

## 💻 Option 2 — Lancer sans Docker (Python local)

### Prérequis
- Python 3.10 ou 3.11

### Étapes

**1. Créer un environnement virtuel**
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Mac / Linux
source venv/bin/activate
```

**2. Installer les dépendances**
```bash
pip install -r requirements.txt
```

**3. Lancer le serveur**
```bash
cd api
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**4. Ouvrir dans le navigateur**
```
http://localhost:8000/docs
```

---

## 📡 Endpoints disponibles

| Méthode | URL | Description |
|---------|-----|-------------|
| `GET` | `/health` | Vérifier que le serveur tourne |
| `GET` | `/classes` | Liste des 23 maladies |
| `POST` | `/predict` | Envoyer une image → obtenir un diagnostic |
| `POST` | `/predict/base64` | Envoyer une image en base64 |

---

## 🧪 Tester l'API

### Via le navigateur (plus simple)
Aller sur `http://localhost:8000/docs` → cliquer sur **POST /predict** → **Try it out** → choisir une image → **Execute**

### Via Python
```python
import requests

response = requests.post(
    "http://localhost:8000/predict",
    files={"file": open("photo_peau.jpg", "rb")}
)
print(response.json())
```

### Via curl
```bash
curl -X POST http://localhost:8000/predict \
  -F "file=@photo_peau.jpg"
```

---

## 📊 Exemple de réponse

```json
{
  "top_prediction": "Nail Fungus and other Nail Disease",
  "confidence": 0.8231,
  "percent": 82.31,
  "all_predictions": [
    {"rank": 1, "class": "Nail Fungus and other Nail Disease", "confidence": 0.8231, "percent": 82.31},
    {"rank": 2, "class": "Psoriasis pictures Lichen Planus", "confidence": 0.0912, "percent": 9.12},
    {"rank": 3, "class": "Eczema Photos", "confidence": 0.0421, "percent": 4.21}
  ],
  "model_info": {
    "img_size": 300,
    "tta": false,
    "topk": 3
  }
}
```

---

## ⚠️ Important — Le fichier modèle

Le fichier `best_model.pth` est trop lourd pour être partagé sur GitHub (~80MB).

**Le récupérer :**
- Via Google Drive / WeTransfer (demander le lien à l'équipe)
- Le placer dans : `outputs_pro/best_model.pth`

---

## 🔧 Problèmes fréquents

| Erreur | Solution |
|--------|----------|
| `Could not import module "main"` | Tu n'es pas dans le bon dossier — faire `cd api` d'abord |
| `Model not found` | Vérifier que `best_model.pth` est dans `outputs_pro/` |
| `Address already in use` | Changer le port : `--port 8001` |
| `pip install` échoue | Vérifier que le venv est activé (`(venv)` visible dans le terminal) |

---

## 📈 Performance du modèle

| Métrique | Valeur |
|----------|--------|
| Accuracy (test) | 57.3% |
| Balanced Accuracy | 59.7% |
| Macro F1 | 0.55 |
| ROC-AUC | 0.92 |
| Meilleure classe | Nail Fungus (F1: 0.82) |
| Dataset | DermNet — 23 classes, 19 559 images |

> ⚠️ Cet outil est un support d'aide à la décision, **pas un diagnostic médical**. Toujours consulter un dermatologue.
