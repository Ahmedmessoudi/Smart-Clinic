# OcuScan — Eye Disease Classifier API

API FastAPI pour la classification des maladies oculaires.
**Modèle** : Keras Functional, entrée 300×300×3, 8 classes.
**Dataset** : [Kaggle Eye Diseases Classification](https://www.kaggle.com/datasets/gunavenkatdoddi/eye-diseases-classification)

---

## Structure du projet

```
eye_disease_app/
├── app/
│   ├── main.py              ← API FastAPI
│   └── templates/
│       └── index.html       ← Frontend intégré
├── best_model_final.h5      ← Ton modèle (à placer ici)
├── requirements.txt
├── Dockerfile
└── README.md
```

---

## Installation locale

```bash
# 1. Créer un environnement virtuel
python -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows

# 2. Installer les dépendances
pip install -r requirements.txt

# 3. Placer ton modèle à la racine du projet
cp /chemin/vers/best_model_final.h5 .

# 4. Lancer le serveur
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Ouvre ensuite [http://localhost:8000](http://localhost:8000)

---

## Lancer avec Docker

```bash
# Construire l'image
docker build -t ocuscan .

# Lancer le conteneur
docker run -p 8000:8000 ocuscan
```

---

## Endpoints API

| Méthode | Route       | Description                              |
|---------|-------------|------------------------------------------|
| GET     | `/`         | Interface web (frontend)                 |
| GET     | `/health`   | Vérification de l'état de l'API          |
| GET     | `/classes`  | Liste des 8 classes supportées           |
| POST    | `/predict`  | Classifie une image (multipart/form-data)|
| GET     | `/docs`     | Documentation Swagger interactive        |

### Exemple avec curl

```bash
curl -X POST http://localhost:8000/predict \
  -F "file=@retina.jpg"
```

### Réponse JSON

```json
{
  "prediction": "Glaucoma",
  "confidence": 94.3,
  "top3": [
    {"class": "Glaucoma", "confidence": 94.3},
    {"class": "Normal", "confidence": 3.1},
    {"class": "Cataract", "confidence": 1.8}
  ],
  "all_probabilities": {
    "Cataract": 1.8,
    "Diabetic Retinopathy": 0.3,
    "Glaucoma": 94.3,
    "Normal": 3.1,
    ...
  },
  "filename": "retina.jpg"
}
```

---

## ⚠️ Labels des classes

Le modèle expose **8 classes**. Ajuste `CLASS_NAMES` dans `app/main.py`
selon les dossiers exacts de ton dataset d'entraînement :

```python
CLASS_NAMES = [
    "Cataract",
    "Diabetic Retinopathy",
    "Glaucoma",
    "Normal",
    "Age-related Macular Degeneration",
    "Hypertensive Retinopathy",
    "Myopia",
    "Other Pathology",
]
```

> **Ordre important** : les labels doivent correspondre à l'ordre
> alphabétique des dossiers utilisés lors de l'entraînement
> (ImageDataGenerator / tf.keras.utils.image_dataset_from_directory).

---

## Avertissement

Cet outil est à **usage éducatif uniquement**.
Il ne remplace pas un diagnostic médical professionnel.
