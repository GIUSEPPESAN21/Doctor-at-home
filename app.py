# -*- coding: utf-8 -*-
"""
Suite de Diagnóstico Integral
Versión: 13.0 ("Comprehensive Clinical Suite")
Descripción: Evolución final hacia una plataforma clínica completa. Se introduce
un formulario de consulta exhaustivo basado en guías de semiología, que abarca
múltiples sistemas y factores de riesgo. El motor de IA (Gemini) se recalibra
para analizar este conjunto de datos enriquecido y proporcionar un análisis
diferencial y un plan de manejo detallado.
"""
# --- LIBRERÍAS ---
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timezone
import firebase_admin
from firebase_admin import credentials, firestore, auth
import google.generativeai as genai
import altair as alt

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Suite de Diagnóstico Integral",
    page_icon="🩺",
    layout="wide"
)

# --- CONSTANTES ---
APP_VERSION = "13.0.0 (Comprehensive Clinical Suite)"

# ==============================================================================
# MÓDULO 1: CONEXIONES Y GESTIÓN DE ESTADO
# ==============================================================================
@st.cache_resource
def init_connections():
    """Inicializa conexiones a Firebase y Gemini."""
    try:
        creds_dict = dict(st.secrets["firebase_credentials"])
        creds_dict['private_key'] = creds_dict['private_key'].replace('\\n', '\n')
        if not firebase_admin._apps:
            creds = credentials.Certificate(creds_dict)
            firebase_admin.initialize_app(creds)
        db_client = firestore.client()
    except Exception as e:
        st.error(f"Error crítico al conectar con Firebase: {e}", icon="🔥")
        db_client = None

    try:
        api_key = st.secrets["gemini_api_key"]
        genai.configure(api_key=api_key)
        model_client = genai.GenerativeModel('gemini-1.5-flash-latest')
    except Exception as e:
        st.error(f"Error crítico al configurar el modelo de IA: {e}", icon="🤖")
        model_client = None
    return db_client, model_client

DB, GEMINI_MODEL = init_connections()

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.physician_email = None
    st.session_state.page = 'login'
    st.session_state.selected_patient_id = None

# ==============================================================================
# MÓDULO 2: LÓGICA DE DATOS (FIRESTORE)
# ==============================================================================
def get_physician_patients(physician_email):
    if not DB: return []
    patients_ref = DB.collection('physicians').document(physician_email).collection('patients').stream()
    return [{'id': doc.id, **doc.to_dict()} for doc in patients_ref]

def save_new_patient(physician_email, patient_data):
    if not DB: return
    DB.collection('physicians').document(physician_email).collection('patients').document(patient_data['cedula']).set(patient_data)
    st.success(f"Paciente {patient_data['nombre']} registrado exitosamente.")

def save_consultation(physician_email, patient_id, consultation_data):
    if not DB: return
    timestamp = datetime.now(timezone.utc)
    doc_id = timestamp.strftime('%Y-%m-%d_%H-%M-%S')
    consultation_data['timestamp_utc'] = timestamp.isoformat()
    DB.collection('physicians').document(physician_email).collection('patients').document(patient_id).collection('consultations').document(doc_id).set(consultation_data)
    st.toast("Consulta guardada.", icon="✅")

def load_patient_history(physician_email, patient_id):
    if not DB: return pd.DataFrame()
    consultations_ref = DB.collection('physicians').document(physician_email).collection('patients').document(patient_id).collection('consultations').order_by('timestamp_utc', direction=firestore.Query.DESCENDING).stream()
    records = [doc.to_dict() for doc in consultations_ref]
    if not records: return pd.DataFrame()
    df = pd.DataFrame(records)
    df['timestamp'] = pd.to_datetime(df['timestamp_utc'])
    return df

# ==============================================================================
# MÓDULO 3: INTELIGENCIA ARTIFICIAL (GEMINI)
# ==============================================================================
@st.cache_data(show_spinner="Generando análisis y recomendaciones con IA...", ttl=300)
def generate_ai_holistic_review(_patient_df_dict):
    if not GEMINI_MODEL: return "Servicio de IA no disponible."
    patient_df = pd.DataFrame.from_dict(_patient_df_dict)
    if 'timestamp' in patient_df.columns:
        patient_df['timestamp'] = pd.to_datetime(patient_df['timestamp'])

    latest_consultation = patient_df.iloc[0]
    history_summary = ""
    for _, row in patient_df.head(5).iterrows():
        history_summary += f"- {row['timestamp'].strftime('%d-%b-%Y')}: PA {row['presion_sistolica']}/{row['presion_diastolica']}, IMC {row.get('imc', 'N/A'):.1f}, Glucemia {row.get('glucemia', 'N/A')} mg/dL\n"
    
    prompt = f"""
    **ROL:** Eres un médico especialista en medicina interna y cardiología, actuando como un asistente de soporte a la decisión para otro colega.
    **TAREA:** Analiza el historial completo y la última consulta de un paciente para generar un reporte clínico estructurado.
    **DATOS DE LA ÚLTIMA CONSULTA:**
    - Motivo: {latest_consultation.get('motivo_consulta', 'No especificado')}
    - Signos Vitales: PA {latest_consultation.get('presion_sistolica', 'N/A')}/{latest_consultation.get('presion_diastolica', 'N/A')} mmHg, FC {latest_consultation.get('frec_cardiaca', 'N/A')} lpm, Glucemia {latest_consultation.get('glucemia', 'N/A')} mg/dL.
    - Síntomas Cardiovasculares: {latest_consultation.get('sintomas_cardio', [])}
    - Síntomas Respiratorios: {latest_consultation.get('sintomas_resp', [])}
    - Síntomas Metabólicos: {latest_consultation.get('sintomas_metabolico', [])}
    - Estilo de Vida: Dieta ({latest_consultation.get('dieta', 'N/A')}), Ejercicio ({latest_consultation.get('ejercicio', 'N/A')} min/sem).
    **HISTORIAL DE CONSULTAS (resumen):**
    {history_summary}
    **GENERAR REPORTE CON LA SIGUIENTE ESTRUCTURA:**
    ### Análisis Clínico Integral por IA
    **1. Impresión Diagnóstica Principal y Diferenciales:**
    (Basado en la constelación de signos, síntomas y factores de riesgo, ¿cuál es el diagnóstico más probable? ¿Qué otras posibilidades deberían considerarse?)
    **2. Estratificación del Riesgo:**
    (Evalúa el riesgo cardiovascular/metabólico global del paciente. ¿Es bajo, moderado, alto o muy alto? Justifica tu respuesta.)
    **3. Plan de Manejo Sugerido:**
    * **Estudios Diagnósticos:** (¿Qué exámenes de laboratorio o imágenes se necesitan para confirmar/descartar los diagnósticos? Ej: EKG, Perfil Lipídico, HbA1c, Ecocardiograma.)
    * **Tratamiento Farmacológico:** (Sugiere clases de medicamentos a considerar. Ej: "Iniciar o ajustar terapia antihipertensiva con un IECA/ARA-II. Considerar estat_ina de moderada-alta intensidad.")
    * **Metas Terapéuticas:** (Establece objetivos claros. Ej: "Meta de PA < 130/80 mmHg. Meta de Colesterol LDL < 100 mg/dL.")
    **4. Educación para el Paciente:**
    (Proporciona puntos clave para discutir con el paciente. Ej: "Explicar la importancia de la adherencia al tratamiento. Discutir un plan de alimentación tipo DASH y la meta de 150 minutos de ejercicio aeróbico semanal.")
    """
    try:
        response = GEMINI_MODEL.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"**Error al generar recomendaciones:** {e}"

# ==============================================================================
# MÓDULO 4: VISTAS Y COMPONENTES DE UI
# ==============================================================================
def render_login_page():
    st.title("Plataforma de Gestión Clínica")
    with st.form("login_form"):
        email = st.text_input("Correo Electrónico del Médico")
        password = st.text_input("Contraseña", type="password")
        c1, c2 = st.columns(2)
        login_button = c1.form_submit_button("Iniciar Sesión", use_container_width=True, type="primary")
        register_button = c2.form_submit_button("Registrarse", use_container_width=True)
    if login_button:
        try:
            user = auth.get_user_by_email(email)
            st.session_state.logged_in = True
            st.session_state.physician_email = user.email
            st.session_state.page = 'patient_registry'
            st.rerun()
        except Exception as e: st.error(f"Error de inicio de sesión: {e}")
    if register_button:
        try:
            user = auth.create_user(email=email, password=password)
            st.success(f"Médico {user.email} registrado. Por favor, inicie sesión.")
        except Exception as e: st.error(f"Error de registro: {e}")

def render_main_app():
    with st.sidebar:
        st.header("Menú del Médico")
        physician_email = st.session_state.get('physician_email', 'Cargando...')
        st.write(physician_email)
        st.divider()
        if st.button("Registro de Pacientes", use_container_width=True):
            st.session_state.page = 'patient_registry'
            st.session_state.selected_patient_id = None
            st.rerun()
        st.divider()
        if st.button("Cerrar Sesión", use_container_width=True):
            st.session_state.logged_in = False
            st.rerun()
        st.info(f"**Versión:** {APP_VERSION}")

    if st.session_state.page == 'patient_registry':
        render_patient_registry()
    elif st.session_state.page == 'patient_dashboard':
        render_patient_dashboard()

def render_patient_registry():
    st.title("Panel de Control de Pacientes")
    patients = get_physician_patients(st.session_state.physician_email)
    
    with st.expander("➕ Registrar Nuevo Paciente", expanded=False):
        with st.form("new_patient_form", clear_on_submit=True):
            nombre = st.text_input("Nombres Completos")
            cedula = st.text_input("Documento de Identidad (será el ID único)")
            telefono = st.text_input("Teléfono")
            submitted = st.form_submit_button("Registrar Paciente")
            if submitted and nombre and cedula:
                save_new_patient(st.session_state.physician_email, {"nombre": nombre, "cedula": cedula, "telefono": telefono})
                st.rerun()

    st.divider()
    st.header("Seleccionar Paciente")
    if not patients:
        st.info("No hay pacientes registrados. Agregue uno nuevo para comenzar.")
    else:
        for patient in patients:
            col1, col2, col3 = st.columns([3, 2, 1])
            col1.subheader(patient['nombre'])
            col2.text(f"ID: {patient['cedula']}")
            if col3.button("Ver Historial", key=patient['id'], use_container_width=True):
                st.session_state.selected_patient_id = patient['id']
                st.session_state.page = 'patient_dashboard'
                st.rerun()

def render_patient_dashboard():
    patient_id = st.session_state.selected_patient_id
    patient_info = DB.collection('physicians').document(st.session_state.physician_email).collection('patients').document(patient_id).get().to_dict()
    st.title(f"Dashboard Clínico de: {patient_info['nombre']}")
    st.caption(f"Documento: {patient_info['cedula']}")

    tab1, tab2 = st.tabs(["📈 Historial y Análisis IA", "✍️ Registrar Nueva Consulta"])

    with tab1:
        df_history = load_patient_history(st.session_state.physician_email, patient_id)
        if df_history.empty:
            st.info("Este paciente no tiene consultas. Agregue una en 'Registrar Nueva Consulta'.")
        else:
            st.header("Evolución de Parámetros Clave")
            # Charts... (similar to previous version, can add more)
            if st.button("🧠 Análisis Clínico Integral por IA", use_container_width=True, type="primary"):
                recommendations = generate_ai_holistic_review(df_history.to_dict())
                st.markdown(recommendations)
            st.dataframe(df_history)

    with tab2:
        with st.form("new_consultation_form"):
            st.header("Datos de la Consulta")
            
            with st.expander("1. Anamnesis y Vitales", expanded=True):
                motivo_consulta = st.text_area("Motivo de Consulta y Notas de Evolución")
                c1, c2, c3, c4 = st.columns(4)
                presion_sistolica = c1.number_input("PA Sistólica", 80, 220, 120)
                presion_diastolica = c2.number_input("PA Diastólica", 50, 140, 80)
                frec_cardiaca = c3.number_input("Frec. Cardíaca", 40, 150, 75)
                glucemia = c4.number_input("Glucemia (mg/dL)", 50, 500, 95)
                
            with st.expander("2. Revisión por Sistemas (Síntomas)"):
                sintomas_cardio = st.multiselect("Cardiovascular", ["Dolor de pecho", "Disnea", "Palpitaciones", "Edema"])
                sintomas_resp = st.multiselect("Respiratorio", ["Tos", "Expectoración", "Sibilancias"])
                sintomas_metabolico = st.multiselect("Metabólico", ["Polidipsia (mucha sed)", "Poliuria (mucha orina)", "Pérdida de peso"])

            with st.expander("3. Factores de Riesgo y Estilo de Vida"):
                c1, c2 = st.columns(2)
                dieta = c1.selectbox("Calidad de la Dieta", ["Saludable (DASH/Mediterránea)", "Regular", "Poco saludable (Procesados)"])
                ejercicio = c2.slider("Ejercicio Aeróbico (min/semana)", 0, 500, 150)
            
            submitted = st.form_submit_button("Guardar Consulta", use_container_width=True, type="primary")
            if submitted:
                consultation_data = {
                    "motivo_consulta": motivo_consulta, "presion_sistolica": presion_sistolica, "presion_diastolica": presion_diastolica,
                    "frec_cardiaca": frec_cardiaca, "glucemia": glucemia,
                    "sintomas_cardio": sintomas_cardio, "sintomas_resp": sintomas_resp, "sintomas_metabolico": sintomas_metabolico,
                    "dieta": dieta, "ejercicio": ejercicio
                }
                save_consultation(st.session_state.physician_email, patient_id, consultation_data)
                st.success("Consulta guardada. El historial se actualizará.")
                
# ==============================================================================
# MÓDULO 5: CONTROLADOR PRINCIPAL
# ==============================================================================
def main():
    if st.session_state.logged_in:
        render_main_app()
    else:
        render_login_page()

if __name__ == "__main__":
    main()

