# -*- coding: utf-8 -*-
"""
Sistema Avanzado de Soporte a la Decisión Clínica para Tamizaje
Versión: 10.0 (Versión de Producción Estable con Persistencia de Datos)
Descripción: Versión final de producción que asegura una conexión estable a
los servicios, limpia de código de diagnóstico. Reintroduce y mejora la
persistencia de datos en Firebase, guardando cada evaluación para análisis
poblacional futuro.
"""

# --- LIBRERÍAS ---
import streamlit as st
import pandas as pd
import numpy as np
import hashlib
from datetime import datetime, timezone
import firebase_admin
from firebase_admin import credentials, firestore
import google.generativeai as genai
import altair as alt

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Sistema de Soporte al Tamizaje Clínico",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CONSTANTES ---
APP_VERSION = "10.0.0 (Producción)"

# ==============================================================================
# MÓDULO 1: CONEXIONES Y PERSISTENCIA DE DATOS
# ==============================================================================

@st.cache_resource
def init_connections():
    """Inicializa y gestiona las conexiones a Firebase y Gemini."""
    db_client, model_client = None, None
    try:
        creds_dict = dict(st.secrets["firebase_credentials"])
        # Corrección crucial para el formato de la private_key de Streamlit
        creds_dict['private_key'] = creds_dict['private_key'].replace('\\n', '\n')
        
        if not firebase_admin._apps:
            creds = credentials.Certificate(creds_dict)
            firebase_admin.initialize_app(creds)
        db_client = firestore.client()
    except Exception as e:
        st.error(f"Error crítico al conectar con Firebase: {e}", icon="🔥")

    try:
        api_key = st.secrets["gemini_api_key"]
        genai.configure(api_key=api_key)
        model_client = genai.GenerativeModel('gemini-1.5-flash-latest')
    except Exception as e:
        st.error(f"Error crítico al configurar el modelo de IA: {e}", icon="🤖")
        
    return db_client, model_client

DB, GEMINI_MODEL = init_connections()

def save_evaluation_to_firestore(patient_data: dict, inferences: dict):
    """Guarda una evaluación completa en Firestore de forma anónima."""
    if not DB:
        st.warning("Conexión a la base de datos no disponible. Los datos no serán guardados.")
        return
    try:
        timestamp = datetime.now(timezone.utc)
        id_source = "".join(map(str, patient_data.values()))
        patient_id = hashlib.sha256(id_source.encode()).hexdigest()
        
        doc_id = f"{timestamp.strftime('%Y%m%d%H%M%S')}_{patient_id[:8]}"
        record_ref = DB.collection('evaluations').document(doc_id)
        
        record_to_save = {
            'patient_id': patient_id,
            'timestamp_utc': timestamp.isoformat(),
            'app_version': APP_VERSION,
            'patient_data': patient_data,
            'system_inferences': inferences
        }
        record_ref.set(record_to_save)
        st.toast("Evaluación guardada anónimamente.", icon="💾")
    except Exception as e:
        st.error(f"No se pudo guardar la evaluación en la base de datos: {e}")

if 'page' not in st.session_state:
    st.session_state.page = 'home'

# ==============================================================================
# MÓDULO 2: MOTOR DE INFERENCIA CLÍNICA
# ==============================================================================
def clinical_risk_inference_engine(data: dict) -> dict:
    """Motor de inferencia basado en factores de riesgo ponderados."""
    inferences = {}
    cardio_factors = {
        'edad_avanzada': (data['edad'] > 55) * 1.5,
        'presion_elevada': (data['presion_sistolica'] >= 140) * 3.0 + (130 <= data['presion_sistolica'] < 140) * 1.5,
        'obesidad': (data['imc'] >= 30) * 2.0,
        'tabaquismo': data['tabaquismo'] * 2.5,
        'historia_familiar': data['historia_familiar_cardio'] * 1.0,
        'sintoma_dolor_pecho': data['dolor_pecho'] * 4.0
    }
    cardio_score = sum(cardio_factors.values())
    diabetes_factors = {
        'sobrepeso_obesidad': (data['imc'] >= 25) * 2.5,
        'historia_familiar': data['historia_familiar_diabetes'] * 2.0,
        'sintoma_fatiga': data['fatiga_excesiva'] * 1.0,
        'sintoma_sed': data['sed_excesiva'] * 1.5
    }
    diabetes_score = sum(diabetes_factors.values())
    def sigmoid(x, k=0.1): return 1 / (1 + np.exp(-k * x))
    if cardio_score > 4.0:
        inferences['Enfermedades Cardiovasculares'] = {
            'Riesgo': 'ALTO', 'Puntuación': round(cardio_score, 2), 
            'Confianza': f"{sigmoid(cardio_score, k=0.25)*100:.1f}%",
            'Factores Clave': [k for k, v in cardio_factors.items() if v > 0]
        }
    if diabetes_score > 3.5:
        inferences['Diabetes Mellitus Tipo 2'] = {
            'Riesgo': 'ALTO', 'Puntuación': round(diabetes_score, 2),
            'Confianza': f"{sigmoid(diabetes_score, k=0.4)*100:.1f}%",
            'Factores Clave': [k for k, v in diabetes_factors.items() if v > 0]
        }
    return inferences

@st.cache_data(show_spinner="Generando impresión clínica con IA...")
def generate_clinical_impression(_patient_data_tuple, _inferences_tuple) -> str:
    if not GEMINI_MODEL: return "Servicio de IA no disponible."
    patient_data = dict(_patient_data_tuple)
    inferences = dict(_inferences_tuple)
    prompt = f"""
    **ROL Y OBJETIVO:** Eres un especialista en medicina interna y análisis de datos clínicos. Tu objetivo es generar una "Impresión Clínica Preliminar" a partir de datos de tamizaje. Debes ser riguroso, basar tus conclusiones en los datos proporcionados y mantener un tono profesional y ético.
    **DATOS DE ENTRADA:**
    - Perfil Demográfico y Antropométrico: Edad {patient_data['edad']} años, Sexo {patient_data['sexo']}, IMC {patient_data['imc']:.1f} kg/m².
    - Factores de Riesgo: Tabaquismo ({'Positivo' if patient_data['tabaquismo'] else 'Negativo'}), Antecedentes Familiares Cardio ({'Positivos' if patient_data['historia_familiar_cardio'] else 'Negativos'}), Antecedentes Familiares Diabetes ({'Positivos' if patient_data['historia_familiar_diabetes'] else 'Negativos'}).
    - Signos y Síntomas: Dolor torácico ({'Reportado' if patient_data['dolor_pecho'] else 'No reportado'}), Fatiga ({'Reportada' if patient_data['fatiga_excesiva'] else 'No reportada'}), Polidipsia ({'Reportada' if patient_data['sed_excesiva'] else 'No reportada'}).
    **INFERENCIAS DEL SISTEMA (ALGORITMO):**
    {inferences if inferences else "No se identificaron perfiles de riesgo algorítmicamente."}
    **TAREA: Genera el reporte con la siguiente estructura estricta en formato Markdown:**
    ### Impresión Clínica Preliminar
    **1. Resumen Ejecutivo:**
    Análisis de un paciente de {patient_data['edad']} años con los siguientes hallazgos clave...
    **2. Análisis por Perfil de Riesgo:**
    * **Perfil Cardiovascular:** (Si aplica) El sistema identifica un riesgo `[Nivel]` con una confianza de `[Confianza]`. Los factores contribuyentes principales son `[Factores Clave]`. La presencia de `[Síntoma principal, ej. dolor torácico]` es un indicador clínico significativo que requiere atención prioritaria.
    * **Perfil Metabólico (Diabetes):** (Si aplica) Se infiere un riesgo `[Nivel]` con una confianza de `[Confianza]`. Factores como `[Factores Clave]` son determinantes.
    **3. Consideraciones y Plan Sugerido:**
    * **Correlación Clínica:** Los hallazgos algorítmicos son consistentes con...
    * **Recomendaciones (Siguiente Paso):** - Se recomienda una consulta médica formal para una evaluación completa. - Pruebas sugeridas a discreción del médico tratante: [Ej: Perfil lipídico, Hemoglobina Glicosilada (HbA1c)]. - Monitorización ambulatoria de la presión arterial (MAPA) si procede.
    * **Manejo de Estilo de Vida:** Se sugiere discutir con un profesional sobre [Ej: cese del tabaquismo, plan nutricional bajo en sodio y carbohidratos simples, actividad física regular].
    **4. Fundamento y Limitaciones:**
    Este análisis se basa en un modelo algorítmico de factores de riesgo y no constituye un diagnóstico. La confianza de la predicción es una métrica de la consistencia de los datos con el modelo y no una probabilidad diagnóstica. La evaluación por un profesional de la salud es indispensable.
    """
    try:
        response = GEMINI_MODEL.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"**Error en la generación del reporte:** No se pudo contactar al servicio de IA. Detalles: {e}"

# ==============================================================================
# MÓDULO 3: VISTAS DE LA INTERFAZ DE USUARIO
# ==============================================================================

def render_home_page():
    st.title("Sistema de Soporte a la Decisión para Tamizaje Clínico")
    st.image("https://images.unsplash.com/photo-1576091160550-2173dba999ab?q=80&w=2070", use_column_width=True)
    st.markdown("Bienvenido a la plataforma avanzada de soporte al tamizaje.")

def render_screening_page():
    st.title("⚕️ Nuevo Tamizaje de Paciente")
    if 'clinical_impression' not in st.session_state:
        with st.form("evaluation_form"):
            st.header("Datos del Paciente")
            col1, col2, col3 = st.columns(3)
            with col1:
                edad = st.slider("Edad", 1, 100, 45, key="edad_slider")
                sexo = st.selectbox("Sexo Biológico", ["Masculino", "Femenino"], key="sexo_select")
            with col2:
                imc = st.slider("Índice de Masa Corporal (IMC)", 15.0, 50.0, 24.0, 0.1, key="imc_slider")
                presion_sistolica = st.slider("Presión Arterial Sistólica (mmHg)", 80, 220, 120, key="presion_slider")
            with col3:
                historia_familiar_cardio = st.checkbox("Antecedentes Familiares (Cardio)", key="hist_cardio")
                historia_familiar_diabetes = st.checkbox("Antecedentes Familiares (Diabetes)", key="hist_diabetes")
                tabaquismo = st.checkbox("Hábito de Tabaquismo", key="tabaquismo_check")
            st.divider()
            st.header("Síntomas Clave Reportados")
            col_s1, col_s2, col_s3 = st.columns(3)
            dolor_pecho = col_s1.checkbox("Dolor o molestia torácica", key="dolor_pecho_check")
            fatiga_excesiva = col_s2.checkbox("Fatiga o astenia marcada", key="fatiga_check")
            sed_excesiva = col_s3.checkbox("Polidipsia (sed excesiva)", key="sed_check")
            st.warning("Consentimiento: Al enviar, confirma que tiene el consentimiento del paciente para procesar estos datos de forma anónima.", icon="⚠️")
            submitted = st.form_submit_button("Procesar, Guardar y Generar Impresión", use_container_width=True, type="primary")

        if submitted:
            patient_data = {'edad': edad, 'sexo': sexo, 'imc': imc, 'presion_sistolica': presion_sistolica, 'historia_familiar_cardio': historia_familiar_cardio, 'historia_familiar_diabetes': historia_familiar_diabetes, 'tabaquismo': tabaquismo, 'dolor_pecho': dolor_pecho, 'fatiga_excesiva': fatiga_excesiva, 'sed_excesiva': sed_excesiva}
            inferences = clinical_risk_inference_engine(patient_data)
            save_evaluation_to_firestore(patient_data, inferences)
            st.session_state.clinical_impression = generate_clinical_impression(tuple(patient_data.items()), tuple(inferences.items()))
            st.rerun()
    else:
        st.header("Análisis Generado")
        st.markdown(st.session_state.clinical_impression)
        if st.button("Iniciar Nuevo Tamizaje", use_container_width=True, key="new_eval_button"):
            del st.session_state.clinical_impression
            st.rerun()

def render_dashboard_page():
    st.title("📊 Dashboard de Analítica Poblacional")
    st.info("Esta sección está en desarrollo.")

# ==============================================================================
# MÓDULO 4: CONTROLADOR PRINCIPAL Y NAVEGACIÓN
# ==============================================================================
def main():
    if not DB or not GEMINI_MODEL:
        st.error("Una o más conexiones críticas no pudieron ser establecidas. Verifique sus 'Secrets' y reinicie la app.")
        return

    with st.sidebar:
        st.header("Menú de Navegación")
        if st.button("Página Principal", use_container_width=True, type="primary" if st.session_state.page == 'home' else "secondary"):
            st.session_state.page = 'home'
        if st.button("Realizar Nuevo Tamizaje", use_container_width=True, type="primary" if st.session_state.page == 'screening' else "secondary"):
            st.session_state.page = 'screening'
        if st.button("Dashboard Poblacional", use_container_width=True, type="primary" if st.session_state.page == 'dashboard' else "secondary"):
            st.session_state.page = 'dashboard'
        st.sidebar.info(f"**Versión:** {APP_VERSION}")

    if st.session_state.page == 'home':
        render_home_page()
    elif st.session_state.page == 'screening':
        render_screening_page()
    elif st.session_state.page == 'dashboard':
        render_dashboard_page()

if __name__ == "__main__":
    main()
