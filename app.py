# -*- coding: utf-8 -*-
"""
Aplicación Principal de Streamlit para el Modelo Predictor de Riesgo Cardiovascular
Versión: 3.2.0 (Estable con Gráfico Altair y Lógica Unificada)
Descripción: Versión estable que utiliza Altair para la visualización de datos,
solucionando errores de gráficos y consolidando toda la lógica para máxima
compatibilidad con Streamlit Cloud.
"""

# --- LIBRERÍAS PRINCIPALES ---
import streamlit as st
import pandas as pd
import numpy as np
import hashlib
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
import altair as alt

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(
    page_title="Predictor de Riesgo Cardiovascular",
    page_icon="❤️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CONSTANTES ---
MODEL_VERSION = "3.2.0"
FEATURES = [
    'edad', 'sexo', 'imc', 'presion_sistolica', 
    'frecuencia_cardiaca', 'diabetes', 'tabaquismo'
]
RISK_COLORS_MAP = {
    "ALTO": "#FF4B4B",
    "MODERADO": "#FFA500",
    "BAJO": "#008000"
}
RISK_LEVEL_ORDER = ["BAJO", "MODERADO", "ALTO"]

# ==============================================================================
# MÓDULO 1: LÓGICA DE FIREBASE
# ==============================================================================

def check_firestore_credentials() -> bool:
    return "firebase_credentials" in st.secrets

@st.cache_resource
def init_firestore():
    try:
        creds_dict = st.secrets["firebase_credentials"]
        creds = credentials.Certificate(creds_dict)
        try:
            firebase_admin.initialize_app(creds)
        except ValueError:
            pass
        return firestore.client()
    except Exception:
        return None

def save_prediction_to_firestore(db, patient_id: str, timestamp: str, data: dict):
    if db:
        try:
            doc_id = f"{patient_id}_{timestamp}"
            record_ref = db.collection('predictions').document(doc_id)
            record_ref.set(data)
            st.toast("Predicción guardada.")
        except Exception as e:
            st.error(f"Error al guardar en Firestore: {e}")

def get_all_records(db) -> pd.DataFrame:
    if not db:
        return pd.DataFrame()
    try:
        all_records = [doc.to_dict() for doc in db.collection('predictions').stream()]
        return pd.DataFrame(all_records) if all_records else pd.DataFrame()
    except Exception as e:
        st.error(f"Error al leer de Firestore: {e}")
        return pd.DataFrame()

# ==============================================================================
# MÓDULO 2: LÓGICA DEL MODELO Y DATOS
# ==============================================================================

def generate_synthetic_data(n_samples: int) -> pd.DataFrame:
    data = {
        'edad': np.random.randint(25, 85, size=n_samples),
        'sexo': np.random.choice([0, 1], size=n_samples, p=[0.55, 0.45]),
        'imc': np.random.uniform(18.0, 45.0, size=n_samples).round(1),
        'presion_sistolica': np.random.randint(90, 200, size=n_samples),
        'frecuencia_cardiaca': np.random.randint(55, 110, size=n_samples),
        'diabetes': np.random.choice([0, 1], size=n_samples, p=[0.8, 0.2]),
        'tabaquismo': np.random.choice([0, 1], size=n_samples, p=[0.7, 0.3])
    }
    return pd.DataFrame(data)

@st.cache_resource
def get_or_create_model():
    with st.spinner("Inicializando modelo de IA..."):
        synthetic_data = generate_synthetic_data(n_samples=500)
        pipeline = Pipeline([
            ('scaler', StandardScaler()),
            ('kmeans', KMeans(n_clusters=3, random_state=42, n_init=10))
        ])
        pipeline.fit(synthetic_data[FEATURES])
    return pipeline

def make_prediction(model, patient_data: pd.DataFrame) -> tuple:
    patient_features = patient_data[FEATURES]
    centroids = model.named_steps['kmeans'].cluster_centers_
    centroid_magnitudes = np.linalg.norm(centroids, axis=1)
    sorted_indices = np.argsort(centroid_magnitudes)
    low_risk_idx, high_risk_idx = sorted_indices[0], sorted_indices[-1]
    
    patient_scaled = model.named_steps['scaler'].transform(patient_features)
    dist_low = np.linalg.norm(patient_scaled - centroids[low_risk_idx])
    dist_high = np.linalg.norm(patient_scaled - centroids[high_risk_idx])
    
    total_dist = dist_low + dist_high + 1e-6
    risk_score = (dist_low / total_dist) * 100
    
    if risk_score < 40: level = "BAJO"
    elif risk_score < 70: level = "MODERADO"
    else: level = "ALTO"
    return float(risk_score), level

# ==============================================================================
# MÓDULO 3: EXPLICABILIDAD (IA SIMULADA)
# ==============================================================================

def generate_explanation(patient_data: pd.Series, risk_score: float, risk_level: str) -> str:
    factors = []
    if patient_data['edad'] > 65: factors.append("la **edad avanzada**")
    if patient_data['imc'] >= 30: factors.append("un **IMC en rango de obesidad**")
    if patient_data['presion_sistolica'] >= 140: factors.append("una **presión arterial elevada**")
    if patient_data['diabetes'] == 1: factors.append("el diagnóstico de **diabetes**")
    if patient_data['tabaquismo'] == 1: factors.append("el **hábito de tabaquismo**")
    
    explanation = f"El paciente presenta un riesgo **{risk_level}** ({risk_score:.1f}/100).\n\n"
    if factors:
        explanation += "Factores contribuyentes: " + ", ".join(factors) + "."
    else:
        explanation += "No se identificaron factores de riesgo mayores."
    
    return explanation

# ==============================================================================
# NÚCLEO DE LA APLICACIÓN STREAMLIT
# ==============================================================================

IS_CONNECTED_TO_DB = check_firestore_credentials()
DB = init_firestore() if IS_CONNECTED_TO_DB else None
MODEL = get_or_create_model()

with st.sidebar:
    st.image("https://i.imgur.com/2s4rhk1.png", width=100)
    st.title("Cardio-Predict")
    st.markdown("---")
    if IS_CONNECTED_TO_DB: st.success("MODO CONECTADO")
    else: st.warning("MODO DEMO")
    st.info(f"**Versión del Modelo:** `{MODEL_VERSION}`")

st.title("🩺 Evaluador de Riesgo Cardiovascular")
tab1, tab2 = st.tabs(["👤 Nuevo Paciente", "📊 Dashboard"])

with tab1:
    with st.form("patient_form"):
        st.header("Información del Paciente")
        c1, c2 = st.columns(2)
        edad = c1.slider("Edad", 18, 100, 55)
        sexo = c1.selectbox("Sexo Biológico", ["Masculino", "Femenino"])
        imc = c1.slider("IMC", 15.0, 50.0, 28.5, 0.1)
        presion_sistolica = c2.slider("Presión Arterial Sistólica", 80, 220, 135)
        frecuencia_cardiaca = c2.slider("Frecuencia Cardíaca", 40, 140, 75)
        c3, c4 = st.columns(2)
        diabetes = c3.checkbox("Diabetes diagnosticada")
        tabaquismo = c4.checkbox("Es fumador/a")
        
        consent = st.checkbox("Acepto la [política de privacidad](/PRIVACY.md).")
        submitted = st.form_submit_button("Evaluar Riesgo", disabled=not consent, use_container_width=True)

    if submitted:
        patient_data = {
            'edad': edad, 'sexo': 0 if sexo == "Masculino" else 1, 'imc': imc,
            'presion_sistolica': presion_sistolica, 'frecuencia_cardiaca': frecuencia_cardiaca,
            'diabetes': 1 if diabetes else 0, 'tabaquismo': 1 if tabaquismo else 0
        }
        patient_df = pd.DataFrame([patient_data])
        risk_score, risk_level = make_prediction(MODEL, patient_df)
        
        timestamp = datetime.utcnow().isoformat() + "Z"
        id_source = "".join(map(str, patient_data.values())) + timestamp
        patient_id = hashlib.sha256(id_source.encode()).hexdigest()
        
        results = {
            'patient_id': patient_id, 'timestamp': timestamp, 'risk_score': risk_score,
            'risk_level': risk_level, 'model_version': MODEL_VERSION
        }
        
        if IS_CONNECTED_TO_DB:
            save_prediction_to_firestore(DB, patient_id, timestamp, {**patient_data, **results})
        
        st.header("Resultados de la Evaluación")
        st.metric("Nivel de Riesgo", risk_level)
        st.progress(int(risk_score), text=f"Puntaje: {risk_score:.1f}")
        with st.expander("🤖 Ver Explicación", expanded=True):
            st.markdown(generate_explanation(patient_df.iloc[0], risk_score, risk_level))

with tab2:
    st.header("Análisis de la Población")
    df_records = get_all_records(DB) if IS_CONNECTED_TO_DB else generate_synthetic_data(150)

    if df_records.empty:
        st.info("No hay registros para analizar.")
    else:
        if 'risk_score' not in df_records.columns:
            preds = [make_prediction(MODEL, pd.DataFrame([row])) for _, row in df_records.iterrows()]
            df_records[['risk_score', 'risk_level']] = preds
            
        st.metric("Total de Evaluaciones", len(df_records))
        
        st.markdown("**Distribución de Riesgo**")
        risk_counts = df_records['risk_level'].value_counts().reset_index()
        risk_counts.columns = ['risk_level', 'count']
        
        chart = alt.Chart(risk_counts).mark_bar().encode(
            x=alt.X('risk_level', sort=RISK_LEVEL_ORDER, title="Nivel de Riesgo"),
            y=alt.Y('count', title="Número de Pacientes"),
            color=alt.Color('risk_level',
                            scale=alt.Scale(domain=RISK_LEVEL_ORDER,
                                            range=[RISK_COLORS_MAP.get(l, "#808080") for l in RISK_LEVEL_ORDER]),
                            legend=None),
            tooltip=['risk_level', 'count']
        )
        st.altair_chart(chart, use_container_width=True)

        st.dataframe(df_records)
        st.download_button("Exportar a CSV", df_records.to_csv(index=False).encode('utf-8'),
                           "predicciones_poblacion.csv", "text/csv")
