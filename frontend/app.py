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

# Base URL setup
# Default is http://avc-api:8000 inside Docker, or http://localhost:8000 for local run
default_url = _env("AVC_SERVICE_URL", "http://localhost:8000")

# Streamlit config
st.set_page_config(
    page_title="AVC Stroke Clinical Assistant",
    page_icon="🧠",
    layout="wide",
)

# Custom Styling (Premium Slate/Teal CSS)
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
  gap: 8px;
  padding: 6px 14px;
  border-radius: 99px;
  font-size: 0.85rem;
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
        response = requests.get(base_url, timeout=5)
        if response.status_code == 200:
            return "healthy", response.json()
        return "error", {"status_code": response.status_code, "payload": response.text}
    except Exception as exc:
        return "unreachable", {"error": str(exc)}

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

# Chat assistant conversational responses (Fallbacks for text questions)
def _get_conversational_response(user_text: str) -> str:
    text = user_text.lower()
    if "hello" in text or "hi" in text or "hey" in text:
        return (
            "Hello! I am your **AVC Stroke Diagnostic Assistant**. 🧠\n\n"
            "I'm here to help analyze patient stroke risks and brain CT scan images. "
            "To begin, use the diagnostic console in the **sidebar**:\n"
            "- Select **Infarctus du Myocarde** to run the Tabular Random Forest Classifier model.\n"
            "- Select **CT Scan Analysis** to upload an image and execute the brain parenchyma morphological model."
        )
    elif "symptom" in text or "signs" in text or "warning" in text:
        return (
            "### ⚠️ Warning Signs of Stroke (B.E. F.A.S.T.)\n\n"
            "If you or someone else shows these symptoms, seek emergency medical services immediately:\n\n"
            "* **B - Balance**: Sudden loss of balance or coordination.\n"
            "* **E - Eyes**: Sudden vision trouble or double vision in one or both eyes.\n"
            "* **F - Face**: One side of the face droops or is numb. Ask the person to smile.\n"
            "* **A - Arms**: One arm drifts downward or is weak/numb. Ask the person to raise both arms.\n"
            "* **S - Speech**: Slurred speech or difficulty speaking/understanding. Ask them to repeat a simple sentence.\n"
            "* **T - Time**: Call emergency services (911 / local emergency) immediately. Every second counts!"
        )
    elif "ischemic" in text:
        return (
            "### 🧠 What is an Ischemic Stroke?\n\n"
            "An **Ischemic Stroke** occurs when a blood vessel supplying blood to the brain becomes blocked, "
            "typically by a blood clot. This cuts off oxygen and nutrient delivery to brain cells, causing them to fail. "
            "It represents approximately 87% of all strokes.\n\n"
            "* **CT Scan Markers**: Typically appears as a **dark, hypodense area** inside the brain parenchyma. "
            "It may also show swelling or asymmetry between the left and right hemispheres of the brain."
        )
    elif "hemorrhagic" in text:
        return (
            "### 🩸 What is a Hemorrhagic Stroke?\n\n"
            "A **Hemorrhagic Stroke** occurs when a weakened blood vessel ruptures and bleeds into the surrounding brain tissue. "
            "The accumulated blood pools and puts pressure on nearby brain structures, causing rapid cell damage.\n\n"
            "* **CT Scan Markers**: Active blood appears as **abnormally bright, hyperdense patches** inside the brain tissue "
            "(distinct from the outer skull bone ring)."
        )
    elif "model" in text or "algorithm" in text or "how does" in text:
        return (
            "### 📊 AVC Machine Learning Models\n\n"
            "I utilize two distinct decision-support algorithms:\n\n"
            "1. **Patient Stroke Predictor**: A **Random Forest Classifier** trained on tabular clinical records. "
            "It scales and analyzes 10 patient features (age, BMI, glucose, hypertension, lifestyle) to output a calibrated stroke probability.\n"
            "2. **Specialist CT Scan Classifier**: A **Computer Vision-inspired rule model** focusing strictly on "
            "brain parenchyma (skull bone and background are mathematically excluded via center cropping and morphological filtering). "
            "It evaluates average density, hemisphere asymmetry, and localized intensity histograms to detect ischemic and hemorrhagic damage."
        )
    else:
        return (
            "I understand you're asking about stroke diagnostics. "
            "To perform an official assessment, please use the specialized forms in the sidebar:\n\n"
            "1. **Patient Risk Form**: Fill in demographic and clinical features to calculate a calibrated risk index.\n"
            "2. **CT Scan Uploader**: Submit a brain CT image to run automated parenchyma classification.\n\n"
            "Let me know if you need information about symptoms, ischemic strokes, or hemorrhagic strokes!"
        )

# Sidebar Design
st.sidebar.markdown("<h2 style='text-align: center; margin-bottom: 0;'>🧠 AVC Console</h2>", unsafe_allow_html=True)
st.sidebar.markdown("<p style='text-align: center; font-size: 0.85rem; color: #94a3b8; margin-top: 0;'>Stroke Decision Support</p>", unsafe_allow_html=True)
st.sidebar.markdown("---")

# API URL Configuration
api_url = st.sidebar.text_input(
    "AVC Service URL",
    value=default_url,
    help="Target API URL endpoint for inference calls",
)

# Health Status Representation
health_status, health_payload = _check_health(api_url)
status_class = f"status-{health_status}"
status_lbl = {
    "healthy": "Connected (API Online)",
    "error": "API Error",
    "unreachable": "API Offline",
    "not_configured": "Not Configured",
}.get(health_status, "Unknown")

st.sidebar.markdown(
    f"""
    <div class="status-badge {status_class}">
        <span class="status-dot"></span>
        <span>{status_lbl}</span>
    </div>
    """,
    unsafe_allow_html=True,
)

if health_status == "healthy":
    with st.sidebar.expander("Model Environment Details", expanded=False):
        st.json(health_payload)
st.sidebar.markdown("---")

# Main Interface Header
st.markdown("<h2 style='margin-bottom: 5px;'>🧠 AVC Stroke Clinical Assistant</h2>", unsafe_allow_html=True)
st.markdown("<p style='color: #64748b; font-size: 1.1rem; margin-top:0;'>Deep diagnostic decision support for patient stroke risk calculations and brain parenchyma CT classification.</p>", unsafe_allow_html=True)

# Session State Initialization
if "messages" not in st.session_state:
    st.session_state["messages"] = [
        {
            "role": "assistant",
            "content": (
                "Welcome! I am your **AVC Stroke Clinical Assistant**. 🧠\n\n"
                "I am fully integrated with the machine learning models. Please use the diagnostic tools on the left "
                "sidebar to analyze a patient's stroke risk profile or classify a brain CT scan. "
                "You can also ask me questions directly in the chat below."
            ),
        }
    ]

# Diagnostic Selector
workflow = st.sidebar.selectbox(
    "Select Diagnostic Mode",
    ["📝 Infarctus du Myocarde", "📷 CT Scan Analysis"],
    help="Pick a diagnostic model to execute",
)

# Render Sidebar Forms based on selection
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
        if health_status != "healthy":
            st.sidebar.error("Cannot process: AVC ML Service is offline. Check URL configuration.")
        else:
            # Format inputs for FastAPI
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
            
            # Add request to chat as User
            user_msg = (
                f"📝 **Requesting Stroke Risk Assessment for Patient:**\n"
                f"- **Demographics**: {gender}, {int(age)} years old, ever married: {'Yes' if ever_married else 'No'}\n"
                f"- **Clinical features**: Hypertension: {'Yes' if hypertension else 'No'}, Heart Disease: {'Yes' if heart_disease else 'No'}\n"
                f"- **Vitals**: Glucose level: {avg_glucose_level:.1f} mg/dL, BMI: {bmi:.1f}\n"
                f"- **Lifestyle**: Work: {work_type}, Residence: {residence_type}, Smoking: {smoking_status}"
            )
            st.session_state["messages"].append({"role": "user", "content": user_msg})
            
            # API Request
            with st.spinner("Calculating patient risk profile..."):
                status_code, result = _predict_patient(api_url, patient_data)
                
            if status_code == 200:
                risk_pct = result["risk_percentage"]
                risk_lvl = result["risk_level"]
                recs = result["recommendations"]
                m_ver = result["model_version"]
                feat_cnt = result["features_used"]
                
                # Determine colors based on Risk Level
                colors = {
                    "LOW": ("#0d9488", "#f0fdfa", "#115e59"),
                    "MODERATE": ("#d97706", "#fef3c7", "#92400e"),
                    "HIGH": ("#e11d48", "#fff1f2", "#9f1239"),
                    "CRITICAL": ("#7f1d1d", "#fef2f2", "#7f1d1d")
                }
                border_c, bg_c, text_c = colors.get(risk_lvl, ("#0d9488", "#f0fdfa", "#115e59"))
                
                # Format response as HTML Card
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
        if health_status != "healthy":
            st.sidebar.error("Cannot process: AVC ML Service is offline. Check URL configuration.")
        else:
            file_bytes = uploaded_file.getvalue()
            file_name = uploaded_file.name
            file_type = uploaded_file.type
            
            # Add user upload image to messages
            st.session_state["messages"].append({
                "role": "user",
                "content": f"📷 **Requested Brain CT Scan Diagnostics on file:** `{file_name}`",
                "image": file_bytes
            })
            
            # API Request
            with st.spinner("Analyzing brain parenchyma (excluding skull bone structure)..."):
                status_code, result = _classify_ct_scan(api_url, file_name, file_bytes, file_type)
                
            if status_code == 200:
                cls_res = result["classification"]
                conf_val = result["confidence"] * 100
                m_ver = result["model_version"]
                
                # Explanations and colors based on classification
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

# Clear Chat Option
st.sidebar.markdown("---")
if st.sidebar.button("Clear Conversation History", use_container_width=True):
    st.session_state["messages"] = [
        {
            "role": "assistant",
            "content": (
                "History cleared. I am your **AVC Stroke Clinical Assistant**. 🧠\n\n"
                "Please use the forms on the sidebar to calculate stroke risk parameters or upload CT scans, "
                "or write questions below regarding stroke clinical signs."
            )
        }
    ]

# Render Chat Discussion
chat_container = st.container()
with chat_container:
    for message in st.session_state["messages"]:
        with st.chat_message(message["role"], avatar="🧠" if message["role"] == "assistant" else "👤"):
            # If message contains text content
            if message.get("content"):
                st.markdown(message["content"])
            
            # If message contains an uploaded image (User uploaded CT scan)
            if message.get("image"):
                img_data = Image.open(io.BytesIO(message["image"]))
                st.image(img_data, caption="Uploaded CT Scan File", width=300)
                
            # If message contains an HTML report card (Assistant results)
            if message.get("html"):
                st.markdown(message["html"], unsafe_allow_html=True)

# Chat Input field
user_prompt = st.chat_input("Type a message to discuss stroke diagnostics with the AVC Agent...")

if user_prompt:
    # Append user question
    st.session_state["messages"].append({"role": "user", "content": user_prompt})
    
    # Generate conversational assistant response
    with st.spinner("AVC Agent is thinking..."):
        agent_reply = _get_conversational_response(user_prompt)
        
    st.session_state["messages"].append({"role": "assistant", "content": agent_reply})
    st.rerun()

# Footer Warning
st.markdown("---")
st.markdown(
    "<p style='text-align: center; font-size: 0.8rem; color: #94a3b8;'>"
    "⚠️ <b>Clinical Support Warning</b>: This console serves as decision-support technology only and "
    "should not replace professional medical evaluations. Always seek immediate emergency services in acute stroke situations."
    "</p>",
    unsafe_allow_html=True,
)
