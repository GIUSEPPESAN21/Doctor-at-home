# -*- coding: utf-8 -*-
"""
Aplicación de Tamizaje de Múltiples Enfermedades
Versión: 5.0.1 (Estable, Unificada, Flujo Corregido)
Descripción: Versión final que consolida toda la lógica en un solo archivo,
corrige el flujo de envío del formulario y elimina el sidebar para una
experiencia de usuario directa y funcional.
"""

# --- LIBRERÍAS PRINCIPALES ---
import streamlit as st
import pandas as pd
import numpy as np
import hashlib
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore
import altair as alt

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(
    page_title="Tamizaje de Salud Integral",
    page_icon="⚕️",
    layout="wide"
)

# --- CONSTANTES ---
APP_VERSION = "5.0.1"

# ==============================================================================
# MÓDULO 1: LÓGICA DE FIREBASE
# ==============================================================================

def check_firestore_credentials() -> bool:
    """Verifica si las credenciales de Firebase están en los Secrets."""
    return "firebase_credentials" in st.secrets

@st.cache_resource
def init_firestore():
    """Inicializa la conexión con Firestore."""
    try:
        creds_dict = st.secrets["firebase_credentials"]
        creds = credentials.Certificate(creds_dict)
        try:
            firebase_admin.initialize_app(creds)
        except ValueError:
            pass # App ya inicializada
        return firestore.client()
    except Exception:
        return None

def save_evaluation_to_firestore(db, patient_id: str, timestamp: str, data: dict):
    """Guarda una evaluación en Firestore."""
    if db:
        try:
            doc_id = f"{patient_id}_{timestamp}"
            record_ref = db.collection('evaluations').document(doc_id)
            record_ref.set(data)
            st.toast("Evaluación guardada en la base de datos.")
        except Exception as e:
            st.error(f"Error al guardar en Firestore: {e}")

def get_all_records(db) -> pd.DataFrame:
    """Obtiene todos los registros de la base de datos."""
    if not db:
        return pd.DataFrame()
    try:
        all_records = [doc.to_dict() for doc in db.collection('evaluations').stream()]
        return pd.DataFrame(all_records) if all_records else pd.DataFrame()
    except Exception as e:
        st.error(f"Error al leer de Firestore: {e}")
        return pd.DataFrame()

# ==============================================================================
# MÓDULO 2: MOTOR DE REGLAS PARA TAMIZAJE
# ==============================================================================

def evaluate_all_diseases(data: dict) -> dict:
    """Motor de reglas que evalúa los datos y devuelve riesgos identificados."""
    results = {}

    cardio_score = sum([
        1 if data['edad'] > 55 else 0,
        3 if data['presion_sistolica'] >= 140 else (1 if data['presion_sistolica'] >= 130 else 0),
        2 if data['imc'] >= 30 else 0,
        2 if data['tabaquismo'] else 0,
        1 if data['historia_familiar_cardio'] else 0,
        3 if data['dolor_pecho'] else 0
    ])
    if cardio_score >= 5: results['Enfermedades Cardiovasculares'] = 'ALTO'
    elif cardio_score >= 2: results['Enfermedades Cardiovasculares'] = 'MODERADO'

    diabetes_score = sum([
        2 if data['imc'] >= 25 else 0,
        2 if data['historia_familiar_diabetes'] else 0,
        1 if data['fatiga_excesiva'] else 0,
        1 if data['sed_excesiva'] else 0
    ])
    if diabetes_score >= 4: results['Diabetes'] = 'ALTO'
    elif diabetes_score >= 2: results['Diabetes'] = 'MODERADO'

    resp_score = sum([
        3 if data['tabaquismo'] else 0,
        2 if data['tos_cronica'] else 0,
        2 if data['falta_aire'] else 0
    ])
    if resp_score >= 4: results['Enfermedades Respiratorias Crónicas'] = 'ALTO'
    elif resp_score >= 2: results['Enfermedades Respiratorias Crónicas'] = 'MODERADO'

    vector_score = sum([
        3 if data['fiebre_alta'] else 0,
        2 if data['dolor_articular_severo'] else 0,
        1 if data['sarpullido'] else 0,
        1 if data['vive_zona_endemica'] else 0
    ])
    if vector_score >= 4: results['Enfermedades por Vectores (Dengue/Chikungunya)'] = 'ALTO'
    elif vector_score >= 2: results['Enfermedades por Vectores (Dengue/Chikungunya)'] = 'MODERADO'

    return results

# ==============================================================================
# MÓDULO 3: EXPLICABILIDAD (IA SIMULADA)
# ==============================================================================

def generate_explanation(data: dict, risks: dict) -> str:
    """Genera una explicación en lenguaje natural de los riesgos."""
    if not risks:
        return "#### Evaluación General\nNo se identificaron riesgos significativos. Se recomienda mantener un estilo de vida saludable."

    explanation = "### Resumen de la Evaluación de Tamizaje\n\n"
    for disease, level in risks.items():
        explanation += f"#### ախ Riesgo de **{disease}**: `{level}`\n"
        reasons = []
        if disease == 'Enfermedades Cardiovasculares':
            if data['presion_sistolica'] >= 140: reasons.append("presión arterial muy elevada")
            if data['dolor_pecho']: reasons.append("reporte de dolor en el pecho")
        elif disease == 'Diabetes':
            if data['historia_familiar_diabetes']: reasons.append("historia familiar de diabetes")
            if data['imc'] >= 25: reasons.append("sobrepeso u obesidad")
        
        if reasons:
            explanation += f"**Factores contribuyentes:** {', '.join(reasons)}.\n"
    
    explanation += "\n---\n**Advertencia:** Este es un análisis preliminar y **no constituye un diagnóstico médico**. Consulte a un profesional de la salud."
    return explanation

# ==============================================================================
# NÚCLEO DE LA APLICACIÓN STREAMLIT
# ==============================================================================

# --- Inicialización ---
IS_CONNECTED_TO_DB = check_firestore_credentials()
DB = init_firestore() if IS_CONNECTED_TO_DB else None

# --- Interfaz ---
st.title("⚕️ Herramienta de Tamizaje de Salud Integral")
st.caption(f"Versión {APP_VERSION} | Modo: {'CONECTADO' if IS_CONNECTED_TO_DB else 'DEMO'}")

tab1, tab2 = st.tabs(["👤 Nueva Evaluación", "📊 Dashboard Poblacional"])

with tab1:
    # Lógica para mostrar el formulario O los resultados
    if 'last_evaluation' not in st.session_state:
        st.session_state.last_evaluation = None

    if st.session_state.last_evaluation:
        st.header("Resultados del Tamizaje")
        evaluation = st.session_state.last_evaluation
        explanation_text = generate_explanation(evaluation['data'], evaluation['risks'])
        st.info("Resumen de la Evaluación", icon="📄")
        st.markdown(explanation_text)
        
        if st.button("Realizar una Nueva Evaluación"):
            st.session_state.last_evaluation = None
            st.rerun()
    else:
        with st.form("evaluation_form"):
            st.header("Información del Paciente")
            with st.expander("Datos Generales y Vitales", expanded=True):
                c1, c2 = st.columns(2)
                edad = c1.slider("Edad", 1, 100, 45)
                sexo = c1.selectbox("Sexo Biológico", ["Masculino", "Femenino"])
                imc = c2.slider("Índice de Masa Corporal (IMC)", 15.0, 50.0, 24.0, 0.1)
                presion_sistolica = c2.slider("Presión Arterial Sistólica (mmHg)", 80, 220, 120)
                vive_zona_endemica = c1.checkbox("¿Vive o ha viajado a zona de mosquitos?")
            with st.expander("Historial Médico y Hábitos"):
                c3, c4 = st.columns(2)
                historia_familiar_cardio = c3.checkbox("¿Familiares con enfermedades del corazón?")
                historia_familiar_diabetes = c3.checkbox("¿Familiares con diabetes?")
                tabaquismo = c4.checkbox("¿Fuma actualmente?")
            with st.expander("Síntomas Reportados"):
                c5, c6 = st.columns(2)
                fiebre_alta = c5.checkbox("Fiebre alta (>38.5°C)")
                fatiga_excesiva = c5.checkbox("Cansancio o fatiga excesiva")
                dolor_pecho = c5.checkbox("Dolor o molestia en el pecho")
                falta_aire = c6.checkbox("Dificultad para respirar")
                tos_cronica = c6.checkbox("Tos por más de 3 semanas")
                sed_excesiva = c6.checkbox("Sed inusual o excesiva")
                dolor_articular_severo = c5.checkbox("Dolor severo de articulaciones")
                sarpullido = c6.checkbox("Sarpullido o erupciones")
            
            st.markdown("---")
            consent = st.checkbox("Acepto la [política de privacidad](/PRIVACY.md) y entiendo que esto no es un diagnóstico.")
            submitted = st.form_submit_button("Realizar Tamizaje", disabled=not consent, use_container_width=True)

        if submitted:
            patient_data = {
                'edad': edad, 'sexo': sexo, 'imc': imc, 'presion_sistolica': presion_sistolica,
                'vive_zona_endemica': vive_zona_endemica, 'historia_familiar_cardio': historia_familiar_cardio,
                'historia_familiar_diabetes': historia_familiar_diabetes, 'tabaquismo': tabaquismo,
                'fiebre_alta': fiebre_alta, 'fatiga_excesiva': fatiga_excesiva,
                'dolor_pecho': dolor_pecho, 'falta_aire': falta_aire, 'tos_cronica': tos_cronica,
                'sed_excesiva': sed_excesiva, 'dolor_articular_severo': dolor_articular_severo,
                'sarpullido': sarpullido
            }
            
            timestamp = datetime.utcnow().isoformat() + "Z"
            id_source = "".join(map(str, patient_data.values())) + timestamp
            patient_id = hashlib.sha256(id_source.encode()).hexdigest()
            risks = evaluate_all_diseases(patient_data)
            
            st.session_state.last_evaluation = {"data": patient_data, "risks": risks}

            if IS_CONNECTED_TO_DB:
                record_to_save = {
                    'patient_id': patient_id, 'timestamp': timestamp, 'app_version': APP_VERSION,
                    **patient_data, 'identified_risks': risks
                }
                save_evaluation_to_firestore(DB, patient_id, timestamp, record_to_save)
            
            st.rerun()

with tab2:
    st.header("Dashboard de Salud Poblacional")
    df_records = get_all_records(DB)

    if df_records.empty:
        st.info("No hay registros en la base de datos para analizar.")
    else:
        st.metric("Total de Evaluaciones Realizadas", len(df_records))
        risk_counts = {}
        if 'identified_risks' in df_records.columns:
            for risks in df_records['identified_risks'].dropna():
                if isinstance(risks, dict):
                    for disease, level in risks.items():
                        key = f"{disease} ({level})"
                        risk_counts[key] = risk_counts.get(key, 0) + 1
        
        if not risk_counts:
            st.success("No se han identificado riesgos mayores en la población registrada.")
        else:
            st.markdown("**Prevalencia de Riesgos Identificados**")
            df_risks = pd.DataFrame(list(risk_counts.items()), columns=['Riesgo', 'Casos'])
            df_risks = df_risks.sort_values('Casos', ascending=False)
            
            chart = alt.Chart(df_risks).mark_bar().encode(
                x=alt.X('Casos:Q'),
                y=alt.Y('Riesgo:N', sort='-x'),
                tooltip=['Riesgo', 'Casos']
            ).properties(title='Frecuencia de Perfiles de Riesgo')
            st.altair_chart(chart, use_container_width=True)

        st.markdown("---")
        st.markdown("#### Base de Datos de Evaluaciones")
        st.dataframe(df_records)
        st.download_button("Exportar a CSV", df_records.to_csv(index=False).encode('utf-8'),
                           "registros_poblacion.csv", "text/csv")
