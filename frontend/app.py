import os
import requests
import streamlit as st
from PIL import Image
import io

# Config
DEFAULT_TIMEOUT_SEC = 20

def _env(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip()

# Base URLs setup
default_url = _env("AVC_SERVICE_URL", "http://localhost:8000")
eye_default_url = _env("EYE_SERVICE_URL", "http://localhost:8001")
skin_default_url = _env("SKIN_SERVICE_URL", "http://localhost:8002")

# Streamlit config
st.set_page_config(
    page_title="Smart Clinic Diagnostic Assistant",
    page_icon="🏥",
    layout="wide",
)

# Custom Styling (Premium Slate/Teal CSS with custom card enhancements)
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

:root {
  --teal-primary: #0d9488;
  --teal-dark: #0f766e;
  --teal-light: #f0fdfa;
  --slate-dark: #0f172a;
  --slate-light: #f8fafc;
  --slate-muted: #64748b;
  --rose-primary: #e11d48;
  --amber-primary: #d97706;
  --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
  --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1);
  --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -4px rgba(0, 0, 0, 0.1);
}

html, body, [class*="css"] {
  font-family: 'Outfit', sans-serif;
}

/* Background gradient */
.stApp {
  background: radial-gradient(circle at 80% 20%, #f0fdfa 0%, transparent 50%),
              radial-gradient(circle at 20% 80%, #f8fafc 0%, #f1f5f9 100%);
}

/* Clean sidebar styling */
[data-testid="stSidebar"] {
  background-color: #0f172a !important;
  color: #f8fafc !important;
  border-right: 1px solid #1e293b;
}

[data-testid="stSidebar"] .stMarkdown, [data-testid="stSidebar"] p, [data-testid="stSidebar"] label {
  color: #cbd5e1 !important;
}

[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
  color: #ffffff !important;
}

/* Chat bubble enhancements */
[data-testid="stChatMessage"] {
  background: transparent !important;
  border: none !important;
  padding: 1rem 0 !important;
}

[data-testid="stChatMessage"] .stMarkdown {
  background: #ffffff;
  border-radius: 16px;
  padding: 14px 18px;
  border: 1px solid #e2e8f0;
  box-shadow: var(--shadow-sm);
  color: #1e293b;
  line-height: 1.5;
}

/* User message right aligned or distinct bg */
[data-testid="stChatMessage"]:has([data-testid="chat-message-user"]) .stMarkdown {
  background: linear-gradient(135deg, #0d9488 0%, #0f766e 100%);
  color: #ffffff !important;
  border: none;
}

[data-testid="stChatMessage"]:has([data-testid="chat-message-user"]) .stMarkdown p {
  color: #ffffff !important;
}

/* Custom cards for reports */
.report-card {
  border-radius: 12px;
  padding: 20px;
  margin: 10px 0;
  box-shadow: var(--shadow-md);
  border-left: 6px solid var(--teal-primary);
  background: #ffffff;
}

.report-header {
  font-weight: 700;
  font-size: 1.25rem;
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.report-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 15px;
  margin-bottom: 15px;
  background: #f8fafc;
  padding: 12px;
  border-radius: 8px;
  border: 1px solid #f1f5f9;
}

.report-item {
  display: flex;
  flex-direction: column;
}

.report-label {
  font-size: 0.75rem;
  color: var(--slate-muted);
  text-transform: uppercase;
  font-weight: 600;
  letter-spacing: 0.05em;
}

.report-value {
  font-size: 1.2rem;
  font-weight: 700;
}

.recommendation-title {
  font-size: 0.85rem;
  font-weight: 600;
  text-transform: uppercase;
  color: var(--slate-muted);
  margin-bottom: 4px;
}

.recommendation-body {
  font-size: 0.95rem;
  color: #334155;
  line-height: 1.4;
}

/* Status badge styling */
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 99px;
  font-size: 0.75rem;
  font-weight: 600;
  background: #1e293b;
  border: 1px solid #334155;
  color: #e2e8f0;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}

.status-healthy .status-dot {
  background-color: #10b981;
  box-shadow: 0 0 8px #10b981;
}

.status-unreachable .status-dot, .status-error .status-dot {
  background-color: #ef4444;
  box-shadow: 0 0 8px #ef4444;
}

.status-not_configured .status-dot {
  background-color: #6b7280;
}

footer { visibility: hidden; }
</style>
""",
    unsafe_allow_html=True,
)

# Health Check helper
@st.cache_data(ttl=5)
def _check_health(base_url: str):
    if not base_url:
        return "not_configured", {}
    try:
        response = requests.get(base_url.rstrip("/") + "/health", timeout=3)
        if response.status_code == 200:
            return "healthy", response.json()
        return "error", {"status_code": response.status_code, "payload": response.text}
    except Exception:
        # Fallback for AVC root path health check
        try:
            response = requests.get(base_url, timeout=3)
            if response.status_code == 200:
                return "healthy", response.json()
        except Exception as exc:
            return "unreachable", {"error": str(exc)}
        return "unreachable", {}

# API interactions
def _predict_patient(base_url: str, data: dict):
    url = f"{base_url.rstrip('/')}/predict/patient"
    response = requests.post(url, json=data, timeout=DEFAULT_TIMEOUT_SEC)
    return response.status_code, response.json()

def _classify_ct_scan(base_url: str, file_name: str, file_bytes: bytes, file_type: str):
    url = f"{base_url.rstrip('/')}/predict/specialist"
    files = {"image": (file_name, file_bytes, file_type or "application/octet-stream")}
    response = requests.post(url, files=files, timeout=DEFAULT_TIMEOUT_SEC)
    return response.status_code, response.json()

def _classify_eye_disease(base_url: str, model_type: str, file_name: str, file_bytes: bytes, file_type: str):
    url = f"{base_url.rstrip('/')}/predict?model={model_type}"
    files = {"file": (file_name, file_bytes, file_type or "application/octet-stream")}
    response = requests.post(url, files=files, timeout=DEFAULT_TIMEOUT_SEC)
    return response.status_code, response.json()

def _classify_skin_disease(base_url: str, file_name: str, file_bytes: bytes, file_type: str, use_tta: bool, topk: int):
    url = f"{base_url.rstrip('/')}/predict?use_tta={use_tta}&topk={topk}"
    files = {"file": (file_name, file_bytes, file_type or "application/octet-stream")}
    response = requests.post(url, files=files, timeout=DEFAULT_TIMEOUT_SEC)
    return response.status_code, response.json()

# Chat assistant conversational responses (Fallbacks for text questions)
def _get_conversational_response(user_text: str) -> str:
    text = user_text.lower()
    if "hello" in text or "hi" in text or "hey" in text:
        return (
            "Hello! I am your **Smart Clinic Diagnostic Assistant**. 🏥\n\n"
            "I'm fully integrated with all clinical decision-support microservices. "
            "To begin an assessment, choose your workflow in the **sidebar**:\n"
            "- **Infarctus du Myocarde**: Demographics and clinical data tabular evaluation.\n"
            "- **CT Scan Analysis**: Morphological scan classifier for stroke type detection.\n"
            "- **Eye Diseases**: Retinal (Fond d'œil) and outer eye photograph deep classifiers.\n"
            "- **Skin Diseases**: 23-class dermatologist classifier powered by EfficientNetV2-S."
        )
    elif "symptom" in text or "signs" in text or "warning" in text:
        return (
            "### ⚠️ Critical Warning Symptoms\n\n"
            "Depending on the condition, monitor these emergency signs:\n\n"
            "* **Stroke / Infarctus Cérébral (B.E. F.A.S.T.)**:\n"
            "  * **B - Balance**: Loss of balance/coordination.\n"
            "  * **E - Eyes**: Sudden double vision or sight loss.\n"
            "  * **F - Face**: Drooping/numbness on one side.\n"
            "  * **A - Arms**: Weakness in raising arms.\n"
            "  * **S - Speech**: Slurred speech or difficulty understanding.\n"
            "  * **T - Time**: Call emergency services immediately!\n"
            "* **Myocardial Infarction / Heart Attack**:\n"
            "  * Crushing chest pain or pressure, pain radiating to left arm/jaw, shortness of breath, sudden cold sweats.\n"
            "* **Ophthalmology**:\n"
            "  * Sudden blindness, flashes of light with floating spots, severe localized eye pain.\n"
            "* **Dermatology**:\n"
            "  * Rapidly evolving black/asymmetrical skin lesion, bleeding moles (possible melanoma)."
        )
    elif "ischemic" in text or "hemorrhagic" in text:
        return (
            "### 🧠 Brain Parenchyma CT Identifiers\n\n"
            "* **Ischemic Stroke**: Appears as a dark, **hypodense** area due to cell necrosis from blocked blood vessels. "
            "It represents ~87% of clinical strokes.\n"
            "* **Hemorrhagic Stroke**: Appears as a bright, **hyperdense** (white) patch in the brain parenchyma caused by blood pooling "
            "due to blood vessel rupture."
        )
    elif "eye" in text or "retina" in text or "cataract" in text or "glaucoma" in text:
        return (
            "### 👁️ Eye Disease Models\n\n"
            "I support two main models for ophthalmology decision support:\n\n"
            "1. **Fond d'œil (Rétine)**: Analyzes retinal images to identify 8 diseases: Cataract, Diabetic Retinopathy, Glaucoma, "
            "AMD, Hypertensive Retinopathy, Myopia, Normal, or Other Pathologies.\n"
            "2. **Œil externe**: Analyzes outer eye surface images for 5 classifications: Conjunctivitis, Corneal Disease, "
            "Normal, Pterygium, or Uveitis."
        )
    elif "skin" in text or "dermatology" in text or "melanoma" in text or "eczema" in text or "fungus" in text:
        return (
            "### 🔬 Skin Disease Classifier (EfficientNetV2-S)\n\n"
            "The dermatology engine classifies skin anomalies into **23 categories** including:\n"
            "- Melanoma / Skin Cancer / Malignant Lesions\n"
            "- Atopic Dermatitis, Eczema, Psoriasis, or Lichen Planus\n"
            "- Nail Fungus & Tinea/Ringworm fungal infections\n"
            "- Acne, Rosacea, Seborrheic Keratoses, and Warts/Viral Infections\n\n"
            "You can upload any skin image in the sidebar. Enabling Test-Time Augmentation (TTA) increases accuracy but takes longer."
        )
    else:
        return (
            "I understand you are looking for medical diagnostic insights. "
            "To run an official decision-support check, please use the sidebar inputs to select the diagnostic mode, "
            "provide the clinical parameters or image scans, and click the analysis button."
        )

# Helper for status badge html rendering
def _get_badge_html(status: str) -> str:
    status_class = f"status-{status}"
    status_lbl = {
        "healthy": "Online",
        "error": "Error",
        "unreachable": "Offline",
        "not_configured": "Offline",
    }.get(status, "Offline")
    return f"""
    <div class="status-badge {status_class}" style="display: inline-flex; align-items: center; gap: 8px;">
        <span class="status-dot"></span>
        <span>{status_lbl}</span>
    </div>
    """

# Sidebar Design
st.sidebar.markdown("<h2 style='text-align: center; margin-bottom: 0;'>🏥 Smart Clinic</h2>", unsafe_allow_html=True)
st.sidebar.markdown("<p style='text-align: center; font-size: 0.85rem; color: #94a3b8; margin-top: 0;'>Multi-Service Diagnostic Suite</p>", unsafe_allow_html=True)
st.sidebar.markdown("---")

# Service Configuration
st.sidebar.markdown("### ⚙️ Endpoint Config")
api_url = st.sidebar.text_input("AVC ML URL", value=default_url)
eye_api_url = st.sidebar.text_input("Eye ML URL", value=eye_default_url)
skin_api_url = st.sidebar.text_input("Skin ML URL", value=skin_default_url)

# Check Healths
health_avc, _ = _check_health(api_url)
health_eye, _ = _check_health(eye_api_url)
health_skin, _ = _check_health(skin_api_url)

# Display Badges
st.sidebar.markdown(
    f"""
    <div style="font-size: 0.8rem; line-height: 1.8; margin-bottom: 10px;">
        <div><b>AVC Service:</b> {_get_badge_html(health_avc)}</div>
        <div style="margin-top: 5px;"><b>Eye Service:</b> {_get_badge_html(health_eye)}</div>
        <div style="margin-top: 5px;"><b>Skin Service:</b> {_get_badge_html(health_skin)}</div>
    </div>
    """,
    unsafe_allow_html=True,
)
st.sidebar.markdown("---")

# Session State Initialization
if "messages" not in st.session_state:
    st.session_state["messages"] = [
        {
            "role": "assistant",
            "content": (
                "Welcome! I am your **Smart Clinic Diagnostic Assistant**. 🏥\n\n"
                "I am fully integrated with your machine learning microservices. "
                "Please configure and use the specialized diagnostic modules in the left sidebar "
                "to analyze patient cases. You can also chat with me directly."
            ),
        }
    ]

if "eye_model_type" not in st.session_state:
    st.session_state["eye_model_type"] = "retina"

# Diagnostic Selector
workflow = st.sidebar.selectbox(
    "Select Diagnostic Mode",
    [
        "📝 Infarctus du Myocarde",
        "📷 CT Scan Analysis",
        "👁️ Eye Diseases",
        "🔬 Skin Diseases"
    ],
    help="Pick a diagnostic model to execute",
)

# Render Forms based on selection
if workflow == "📝 Infarctus du Myocarde":
    st.sidebar.subheader("Patient Clinical Data")
    
    with st.sidebar.form(key="patient_form", clear_on_submit=False):
        gender = st.selectbox("Gender", ["Male", "Female", "Other"])
        age = st.number_input("Age (Years)", min_value=1.0, max_value=120.0, value=55.0, step=1.0)
        
        col1, col2 = st.columns(2)
        with col1:
            hypertension = st.checkbox("Hypertension")
            ever_married = st.checkbox("Ever Married", value=True)
        with col2:
            heart_disease = st.checkbox("Heart Disease")
            
        work_type = st.selectbox("Work Type", ["Private", "Self-employed", "Govt_job", "children", "Never_worked"])
        residence_type = st.selectbox("Residence Type", ["Urban", "Rural"])
        
        avg_glucose_level = st.slider("Average Glucose (mg/dL)", min_value=30.0, max_value=500.0, value=95.0, step=0.5)
        bmi = st.slider("Body Mass Index (BMI)", min_value=10.0, max_value=80.0, value=24.5, step=0.1)
        
        smoking_status = st.selectbox("Smoking Status", ["never smoked", "formerly smoked", "smokes"])
        
        submit_risk = st.form_submit_button("Calculate Stroke Risk")

    if submit_risk:
        if health_avc != "healthy":
            st.sidebar.error("Cannot process: AVC Service is offline. Check URL configuration.")
        else:
            patient_data = {
                "gender": gender,
                "age": age,
                "hypertension": bool(hypertension),
                "heart_disease": bool(heart_disease),
                "ever_married": bool(ever_married),
                "work_type": work_type,
                "residence_type": residence_type,
                "avg_glucose_level": float(avg_glucose_level),
                "bmi": float(bmi),
                "smoking_status": smoking_status
            }
            
            user_msg = (
                f"📝 **Requesting Stroke Risk Assessment for Patient:**\n"
                f"- **Demographics**: {gender}, {int(age)} years old, ever married: {'Yes' if ever_married else 'No'}\n"
                f"- **Clinical features**: Hypertension: {'Yes' if hypertension else 'No'}, Heart Disease: {'Yes' if heart_disease else 'No'}\n"
                f"- **Vitals**: Glucose level: {avg_glucose_level:.1f} mg/dL, BMI: {bmi:.1f}\n"
                f"- **Lifestyle**: Work: {work_type}, Residence: {residence_type}, Smoking: {smoking_status}"
            )
            st.session_state["messages"].append({"role": "user", "content": user_msg})
            
            with st.spinner("Calculating patient risk profile..."):
                status_code, result = _predict_patient(api_url, patient_data)
                
            if status_code == 200:
                risk_pct = result["risk_percentage"]
                risk_lvl = result["risk_level"]
                recs = result["recommendations"]
                m_ver = result["model_version"]
                feat_cnt = result["features_used"]
                
                colors = {
                    "LOW": ("#0d9488", "#f0fdfa", "#115e59"),
                    "MODERATE": ("#d97706", "#fef3c7", "#92400e"),
                    "HIGH": ("#e11d48", "#fff1f2", "#9f1239"),
                    "CRITICAL": ("#7f1d1d", "#fef2f2", "#7f1d1d")
                }
                border_c, bg_c, text_c = colors.get(risk_lvl, ("#0d9488", "#f0fdfa", "#115e59"))
                
                report_html = f"""
                <div class="report-card" style="border-left: 6px solid {border_c}; background-color: {bg_c};">
                    <div class="report-header" style="color: {text_c};">🧠 Patient Stroke Risk Report</div>
                    <div class="report-grid">
                        <div class="report-item">
                            <span class="report-label">Risk Probability</span>
                            <span class="report-value" style="color: {text_c};">{risk_pct}%</span>
                        </div>
                        <div class="report-item">
                            <span class="report-label">Risk Level</span>
                            <span class="report-value" style="color: {border_c}; font-weight: 800;">{risk_lvl}</span>
                        </div>
                    </div>
                    <div style="margin-top: 10px;">
                        <div class="recommendation-title">Clinical Recommendations</div>
                        <div class="recommendation-body">{recs}</div>
                    </div>
                    <div style="display: flex; justify-content: space-between; font-size: 0.75rem; color: #94a3b8; border-top: 1px solid rgba(0,0,0,0.05); padding-top: 8px; margin-top: 15px;">
                        <span>Inference Engine: {m_ver}</span>
                        <span>Processed Variables: {feat_cnt}</span>
                    </div>
                </div>
                """
                st.session_state["messages"].append({
                    "role": "assistant",
                    "content": "I have successfully calculated the patient risk indicators using the Random Forest classifier model.",
                    "html": report_html
                })
            else:
                st.session_state["messages"].append({
                    "role": "assistant",
                    "content": f"⚠️ **Error**: Unable to complete patient risk prediction (API returned status {status_code}). Details: {result}"
                })
            st.rerun()

elif workflow == "📷 CT Scan Analysis":
    st.sidebar.subheader("Brain Scan Upload")
    uploaded_file = st.sidebar.file_uploader("Upload CT Scan Image", type=["png", "jpg", "jpeg"])
    submit_scan = st.sidebar.button("Run Diagnostic Classification", disabled=uploaded_file is None)
    
    if submit_scan and uploaded_file is not None:
        if health_avc != "healthy":
            st.sidebar.error("Cannot process: AVC Service is offline. Check URL configuration.")
        else:
            file_bytes = uploaded_file.getvalue()
            file_name = uploaded_file.name
            file_type = uploaded_file.type
            
            st.session_state["messages"].append({
                "role": "user",
                "content": f"📷 **Requested Brain CT Scan Diagnostics on file:** `{file_name}`",
                "image": file_bytes
            })
            
            with st.spinner("Analyzing brain parenchyma (excluding skull bone structure)..."):
                status_code, result = _classify_ct_scan(api_url, file_name, file_bytes, file_type)
                
            if status_code == 200:
                cls_res = result["classification"]
                conf_val = result["confidence"] * 100
                m_ver = result["model_version"]
                
                meta = {
                    "NORMAL": {
                        "color": "#0d9488", "bg": "#f0fdfa", "txt": "#115e59",
                        "desc": "No abnormal bright (hyperdense) or dark (hypodense) parenchyma regions are detected. Left-right tissue structures appear symmetric and normal."
                    },
                    "ISCHEMIC_STROKE": {
                        "color": "#d97706", "bg": "#fef3c7", "txt": "#92400e",
                        "desc": "Hypodense (darker) areas or significant structural asymmetry are detected in the brain parenchyma, indicating potential restricted blood flow and ischemia."
                    },
                    "HEMORRHAGIC_STROKE": {
                        "color": "#e11d48", "bg": "#fff1f2", "txt": "#9f1239",
                        "desc": "Hyperdense (bright) patches are detected inside the brain tissue (skull bone is mathematically excluded), indicating potential bleeding or localized hematoma."
                    },
                    "ERROR": {
                        "color": "#64748b", "bg": "#f1f5f9", "txt": "#334155",
                        "desc": "The model could not identify valid brain parenchyma. Ensure the image is a properly centered brain transverse CT slice."
                    }
                }
                
                info = meta.get(cls_res, meta["ERROR"])
                
                report_html = f"""
                <div class="report-card" style="border-left: 6px solid {info['color']}; background-color: {info['bg']};">
                    <div class="report-header" style="color: {info['txt']};">📷 CT Scan Analysis Report</div>
                    <div class="report-grid">
                        <div class="report-item">
                            <span class="report-label">Diagnostic Output</span>
                            <span class="report-value" style="color: {info['txt']};">{cls_res.replace('_', ' ')}</span>
                        </div>
                        <div class="report-item">
                            <span class="report-label">Classification Confidence</span>
                            <span class="report-value" style="color: {info['color']}; font-weight: 800;">{conf_val:.2f}%</span>
                        </div>
                    </div>
                    <div style="margin-top: 10px;">
                        <div class="recommendation-title">Parenchyma Analysis Notes</div>
                        <div class="recommendation-body">{info['desc']}</div>
                    </div>
                    <div style="display: flex; justify-content: space-between; font-size: 0.75rem; color: #94a3b8; border-top: 1px solid rgba(0,0,0,0.05); padding-top: 8px; margin-top: 15px;">
                        <span>Inference Pipeline: {m_ver}</span>
                        <span>Analysis Focus: Skull-Excluded Parenchyma</span>
                    </div>
                </div>
                """
                st.session_state["messages"].append({
                    "role": "assistant",
                    "content": "CT scan processing completed. The skull-exclusion algorithm has completed analysis of the brain parenchyma.",
                    "html": report_html
                })
            else:
                st.session_state["messages"].append({
                    "role": "assistant",
                    "content": f"⚠️ **Error**: Unable to complete CT-scan analysis (API returned status {status_code}). Details: {result}"
                })
            st.rerun()

elif workflow == "👁️ Eye Diseases":
    st.sidebar.subheader("Ophthalmology Console")
    
    # Premium Dual Selector cards exactly matching the provided image description
    retina_active = st.session_state.eye_model_type == "retina"
    
    # Visual cards matching eye image design
    card_retina_html = f"""
    <div style="
        border: 2px solid {'#0d9488' if retina_active else '#1e293b'};
        background-color: {'rgba(13, 148, 136, 0.05)' if retina_active else '#0f172a'};
        border-radius: 12px;
        padding: 12px;
        text-align: center;
        margin-bottom: 10px;
    ">
        <div style="font-size: 1.5rem;">🔬</div>
        <div style="font-weight: 700; color: #ffffff; font-size: 0.95rem;">Fond d'œil (Rétine)</div>
        <div style="font-size: 0.75rem; color: #94a3b8; margin: 4px 0;">Images rétiniennes · Keras</div>
        <div style="margin-top: 4px;"><span style="background-color: #1e293b; border: 1px solid #334155; color: #0d9488; padding: 2px 8px; border-radius: 99px; font-size: 0.7rem; font-weight: 600;">8 classes · 300×300</span></div>
    </div>
    """
    
    card_external_html = f"""
    <div style="
        border: 2px solid {'#0d9488' if not retina_active else '#1e293b'};
        background-color: {'rgba(13, 148, 136, 0.05)' if not retina_active else '#0f172a'};
        border-radius: 12px;
        padding: 12px;
        text-align: center;
        margin-bottom: 10px;
    ">
        <div style="font-size: 1.5rem;">👁️</div>
        <div style="font-weight: 700; color: #ffffff; font-size: 0.95rem;">Œil externe</div>
        <div style="font-size: 0.75rem; color: #94a3b8; margin: 4px 0;">Photos de l'œil · EfficientNet-B4</div>
        <div style="margin-top: 4px;"><span style="background-color: #1e293b; border: 1px solid #334155; color: #0d9488; padding: 2px 8px; border-radius: 99px; font-size: 0.7rem; font-weight: 600;">5 classes · 380×380</span></div>
    </div>
    """
    
    col_retina, col_external = st.sidebar.columns(2)
    with col_retina:
        st.markdown(card_retina_html, unsafe_allow_html=True)
        if st.button("Sélect. Rétine", use_container_width=True, key="sel_retina"):
            st.session_state.eye_model_type = "retina"
            st.rerun()
            
    with col_external:
        st.markdown(card_external_html, unsafe_allow_html=True)
        if st.button("Sélect. Externe", use_container_width=True, key="sel_external"):
            st.session_state.eye_model_type = "external"
            st.rerun()

    st.sidebar.markdown("---")
    
    # Model indicator banner
    if st.session_state.eye_model_type == "retina":
        st.sidebar.info("🔵 Modèle rétine — Kaggle Eye Diseases Classification (Keras .h5)")
    else:
        st.sidebar.info("🔵 Modèle externe — Mendeley Eye Diseases (EfficientNet-B4)")
        
    uploaded_eye_file = st.sidebar.file_uploader(
        "Déposez une image oculaire", 
        type=["png", "jpg", "jpeg", "bmp", "tiff"]
    )
    st.sidebar.caption("JPEG • PNG • BMP • TIFF — max 10 Mo")
    
    submit_eye = st.sidebar.button("Analyser l'image", disabled=uploaded_eye_file is None)
    
    if submit_eye and uploaded_eye_file is not None:
        if health_eye != "healthy":
            st.sidebar.error("Cannot process: Eye ML Service is offline. Check URL configuration.")
        else:
            file_bytes = uploaded_eye_file.getvalue()
            file_name = uploaded_eye_file.name
            file_type = uploaded_eye_file.type
            m_type = st.session_state.eye_model_type
            
            st.session_state["messages"].append({
                "role": "user",
                "content": f"👁️ **Requested Eye Diagnostics ({'Retina Scan' if m_type == 'retina' else 'External Photo'}):** `{file_name}`",
                "image": file_bytes
            })
            
            with st.spinner("Processing eye scan image..."):
                status_code, result = _classify_eye_disease(eye_api_url, m_type, file_name, file_bytes, file_type)
                
            if status_code == 200:
                pred_class = result["prediction"]
                confidence = result["confidence"]
                top3 = result.get("top3", [])
                
                # Check normal vs pathology styling
                is_normal = "normal" in pred_class.lower()
                border_c = "#0d9488" if is_normal else "#e11d48"
                bg_c = "#f0fdfa" if is_normal else "#fff1f2"
                txt_c = "#115e59" if is_normal else "#9f1239"
                
                # Render other pathology names and progress bars
                top3_html = ""
                for rank, p in enumerate(top3):
                    p_name = p["class"]
                    p_conf = p["confidence"]
                    p_color = "#0d9488" if "normal" in p_name.lower() else "#e11d48"
                    top3_html += f"""
                    <div style="margin-bottom: 8px;">
                        <div style="display: flex; justify-content: space-between; font-size: 0.85rem; font-weight: 600; margin-bottom: 2px;">
                            <span style="color: #334155;">{rank+1}. {p_name}</span>
                            <span style="color: {p_color};">{p_conf}%</span>
                        </div>
                        <div style="background-color: #cbd5e1; border-radius: 4px; overflow: hidden; height: 6px; width: 100%;">
                            <div style="background-color: {p_color}; width: {p_conf}%; height: 100%;"></div>
                        </div>
                    </div>
                    """
                
                report_html = f"""
                <div class="report-card" style="border-left: 6px solid {border_c}; background-color: {bg_c};">
                    <div class="report-header" style="color: {txt_c};">👁️ Eye Diagnostic Report ({m_type.upper()})</div>
                    <div class="report-grid">
                        <div class="report-item">
                            <span class="report-label">Top Condition</span>
                            <span class="report-value" style="color: {txt_c};">{pred_class}</span>
                        </div>
                        <div class="report-item">
                            <span class="report-label">Confidence Score</span>
                            <span class="report-value" style="color: {border_c}; font-weight: 800;">{confidence}%</span>
                        </div>
                    </div>
                    
                    <div style="margin-top: 15px; margin-bottom: 15px;">
                        <div class="recommendation-title">Top 3 Class Probabilities</div>
                        <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; margin-top: 5px;">
                            {top3_html}
                        </div>
                    </div>
                    
                    <div>
                        <div class="recommendation-title">Clinical Action Notes</div>
                        <div class="recommendation-body">
                            {"Maintain regular diagnostic screenings." if is_normal else "Ophthalmologist evaluation is highly advised. Plan retinal mapping or slit lamp verification."}
                        </div>
                    </div>
                    <div style="display: flex; justify-content: space-between; font-size: 0.75rem; color: #94a3b8; border-top: 1px solid rgba(0,0,0,0.05); padding-top: 8px; margin-top: 15px;">
                        <span>Inference Pipeline: Keras h5 (Retina) or PyTorch pth (External)</span>
                        <span>Filename: {result.get('filename', 'Unknown')}</span>
                    </div>
                </div>
                """
                st.session_state["messages"].append({
                    "role": "assistant",
                    "content": "Image processed successfully. Reconstructed eye classification results details are posted.",
                    "html": report_html
                })
            else:
                st.session_state["messages"].append({
                    "role": "assistant",
                    "content": f"⚠️ **Error**: Unable to complete eye analysis (API returned status {status_code}). Details: {result}"
                })
            st.rerun()

elif workflow == "🔬 Skin Diseases":
    st.sidebar.subheader("Dermatology Console")
    
    uploaded_skin_file = st.sidebar.file_uploader(
        "Upload Skin Photo", 
        type=["png", "jpg", "jpeg", "webp", "bmp"]
    )
    st.sidebar.caption("JPEG • PNG • WEBP • BMP — max 10 Mo")
    
    use_tta = st.sidebar.checkbox(
        "Enable Test-Time Augmentation (TTA)", 
        value=False,
        help="Runs 8 randomized transforms for high accuracy (+8x inference time)"
    )
    topk_slider = st.sidebar.slider("Show Top-K Classes", min_value=1, max_value=5, value=3)
    
    submit_skin = st.sidebar.button("Analyze Skin Image", disabled=uploaded_skin_file is None)
    
    if submit_skin and uploaded_skin_file is not None:
        if health_skin != "healthy":
            st.sidebar.error("Cannot process: Skin Service is offline. Check URL configuration.")
        else:
            file_bytes = uploaded_skin_file.getvalue()
            file_name = uploaded_skin_file.name
            file_type = uploaded_skin_file.type
            
            st.session_state["messages"].append({
                "role": "user",
                "content": f"🔬 **Requested Skin Lesion Analysis:** `{file_name}` (TTA: {'Enabled' if use_tta else 'Disabled'}, Top-{topk_slider})",
                "image": file_bytes
            })
            
            with st.spinner("Analyzing skin condition via EfficientNetV2-S..."):
                status_code, result = _classify_skin_disease(
                    skin_api_url, file_name, file_bytes, file_type, use_tta, topk_slider
                )
                
            if status_code == 200:
                top_pred = result["top_prediction"]
                confidence = result["confidence"]
                percent = result["percent"]
                all_preds = result.get("all_predictions", [])
                
                # Check for severe classes
                is_severe = any(w in top_pred.lower() for w in ["melanoma", "cancer", "basal", "malignant", "lupus"])
                border_c = "#e11d48" if is_severe else "#d97706"
                bg_c = "#fff1f2" if is_severe else "#fef3c7"
                txt_c = "#9f1239" if is_severe else "#92400e"
                
                # Render predictions table with progress bars
                all_preds_html = ""
                for pred in all_preds:
                    p_name = pred["class"]
                    p_pct = pred["percent"]
                    is_pred_severe = any(w in p_name.lower() for w in ["melanoma", "cancer", "basal", "malignant", "lupus"])
                    p_color = "#e11d48" if is_pred_severe else "#0d9488"
                    
                    all_preds_html += f"""
                    <div style="margin-bottom: 8px;">
                        <div style="display: flex; justify-content: space-between; font-size: 0.85rem; font-weight: 600; margin-bottom: 2px;">
                            <span style="color: #334155;">{pred['rank']}. {p_name}</span>
                            <span style="color: {p_color};">{p_pct}%</span>
                        </div>
                        <div style="background-color: #cbd5e1; border-radius: 4px; overflow: hidden; height: 6px; width: 100%;">
                            <div style="background-color: {p_color}; width: {p_pct}%; height: 100%;"></div>
                        </div>
                    </div>
                    """
                
                report_html = f"""
                <div class="report-card" style="border-left: 6px solid {border_c}; background-color: {bg_c};">
                    <div class="report-header" style="color: {txt_c};">🔬 Skin Disease Classification Report</div>
                    <div class="report-grid">
                        <div class="report-item">
                            <span class="report-label">Top Diagnosis</span>
                            <span class="report-value" style="color: {txt_c};">{top_pred}</span>
                        </div>
                        <div class="report-item">
                            <span class="report-label">Match Percentage</span>
                            <span class="report-value" style="color: {border_c}; font-weight: 800;">{percent}%</span>
                        </div>
                    </div>
                    
                    <div style="margin-top: 15px; margin-bottom: 15px;">
                        <div class="recommendation-title">Top Candidates List</div>
                        <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; margin-top: 5px;">
                            {all_preds_html}
                        </div>
                    </div>
                    
                    <div>
                        <div class="recommendation-title">Dermatology Assessment Warning</div>
                        <div class="recommendation-body">
                            {"⚠️ CRITICAL WARNING: Highly suspicious malignant lesion parameters. Urgent biopsy requested." if is_severe 
                             else "Monitor evolution. Consult a doctor if it changes shape, size, color, or begins bleeding."}
                        </div>
                    </div>
                    <div style="display: flex; justify-content: space-between; font-size: 0.75rem; color: #94a3b8; border-top: 1px solid rgba(0,0,0,0.05); padding-top: 8px; margin-top: 15px;">
                        <span>Inference Engine: EfficientNetV2-S (DermNet)</span>
                        <span>Augmentation: {"TTA Enabled" if result.get("model_info", {}).get("tta") else "TTA Disabled"}</span>
                    </div>
                </div>
                """
                st.session_state["messages"].append({
                    "role": "assistant",
                    "content": "Dermatology analysis completed. Reconstructed skin condition report has been logged.",
                    "html": report_html
                })
            else:
                st.session_state["messages"].append({
                    "role": "assistant",
                    "content": f"⚠️ **Error**: Unable to complete skin analysis (API returned status {status_code}). Details: {result}"
                })
            st.rerun()

# Clear Chat Option
st.sidebar.markdown("---")
if st.sidebar.button("Clear Conversation History", use_container_width=True):
    st.session_state["messages"] = [
        {
            "role": "assistant",
            "content": (
                "History cleared. I am your **Smart Clinic Diagnostic Assistant**. 🏥\n\n"
                "Please use the forms on the sidebar to calculate risk parameters or upload scans, "
                "or write questions below regarding clinical symptoms."
            )
        }
    ]

# Render Chat Discussion
chat_container = st.container()
with chat_container:
    for message in st.session_state["messages"]:
        with st.chat_message(message["role"], avatar="🏥" if message["role"] == "assistant" else "👤"):
            if message.get("content"):
                st.markdown(message["content"])
            
            if message.get("image"):
                img_data = Image.open(io.BytesIO(message["image"]))
                st.image(img_data, caption="Uploaded File Scan", width=300)
                
            if message.get("html"):
                st.markdown(message["html"], unsafe_allow_html=True)

# Chat Input field
user_prompt = st.chat_input("Type a message to discuss diagnostics with the Smart Clinic Agent...")

if user_prompt:
    st.session_state["messages"].append({"role": "user", "content": user_prompt})
    
    with st.spinner("Smart Clinic Agent is thinking..."):
        agent_reply = _get_conversational_response(user_prompt)
        
    st.session_state["messages"].append({"role": "assistant", "content": agent_reply})
    st.rerun()

# Footer Warning
st.markdown("---")
st.markdown(
    "<p style='text-align: center; font-size: 0.8rem; color: #94a3b8;'>"
    "⚠️ <b>Clinical Support Warning</b>: This console serves as decision-support technology only and "
    "should not replace professional medical evaluations. Always seek immediate emergency services in acute situations."
    "</p>",
    unsafe_allow_html=True,
)

