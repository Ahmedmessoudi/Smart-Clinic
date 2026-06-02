FROM python:3.11-slim

WORKDIR /eye_app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 libsm6 libxrender1 libxext6 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

# Copier les deux modèles
COPY best_model_final.h5 .
COPY eye_disease_best.pth .

ENV RETINA_MODEL_PATH=/eye_app/best_model_final.h5
ENV EXTERNAL_MODEL_PATH=/eye_app/eye_disease_best.pth

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
