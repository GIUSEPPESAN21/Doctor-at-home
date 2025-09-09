# -*- coding: utf-8 -*-
"""
Plataforma de Gestión Clínica
Versión: 12.0 ("Physician-Centric AI Dashboard")
Descripción: Reingeniería completa del sistema para adoptar un flujo de trabajo
centrado en el médico. La página principal se convierte en un registro de pacientes.
El dashboard es ahora específico para cada paciente seleccionado, mostrando su
historial evolutivo y ofreciendo un análisis con recomendaciones generadas por IA (Gemini).
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
    page_title="Plataforma de Gestión Clínica",
    page_icon="⚕️",
    layout="wide"
)

# --- CONSTANTES ---
APP_VERSION = "12.0.0 (Physician AI Dashboard)"

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

# --- Gestión de estado de sesión ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.physician_email = None
    st.session_state.page = 'login'
    st.session_state.selected_patient_id = None

# ==============================================================================
# MÓDULO 2: LÓGICA DE DATOS (FIRESTORE)
# ==============================================================================

def get_physician_patients(physician_email):
    """Obtiene la lista de pacientes asociados a un médico."""
    if not DB: return []
    patients_ref = DB.collection('patients').where('physician_email', '==', physician_email).stream()
    return [{'id': doc.id, **doc.to_dict()} for doc in patients_ref]

def save_new_patient(physician_email, patient_data):
    """Guarda un nuevo paciente en la base de datos."""
    if not DB: return
    patient_data['physician_email'] = physician_email
    DB.collection('patients').add(patient_data)
    st.success(f"Paciente {patient_data['nombre']} registrado exitosamente.")

def save_consultation(patient_id, consultation_data):
    """Guarda una nueva consulta para un paciente específico."""
    if not DB: return
    timestamp = datetime.now(timezone.utc)
    doc_id = timestamp.strftime('%Y-%m-%d_%H-%M-%S')
    consultation_data['timestamp_utc'] = timestamp.isoformat()
    DB.collection('patients').document(patient_id).collection('consultations').document(doc_id).set(consultation_data)
    st.toast("Consulta guardada.", icon="✅")

def load_patient_history(patient_id):
    """Carga el historial de consultas de un paciente."""
    if not DB: return pd.DataFrame()
    consultations_ref = DB.collection('patients').document(patient_id).collection('consultations').order_by('timestamp_utc', direction=firestore.Query.DESCENDING).stream()
    records = [doc.to_dict() for doc in consultations_ref]
    if not records: return pd.DataFrame()
    df = pd.DataFrame(records)
    df['timestamp'] = pd.to_datetime(df['timestamp_utc'])
    return df

# ==============================================================================
# MÓDULO 3: INTELIGENCIA ARTIFICIAL (GEMINI)
# ==============================================================================

@st.cache_data(show_spinner="Generando análisis y recomendaciones con IA...", ttl=300)
def generate_ai_recommendations(_patient_df_dict):
    """Genera recomendaciones para el paciente basadas en su historial."""
    if not GEMINI_MODEL: return "Servicio de IA no disponible."
    
    patient_df = pd.DataFrame.from_dict(_patient_df_dict)
    # Convertir timestamp de nuevo a datetime si es necesario
    if 'timestamp' in patient_df.columns:
        patient_df['timestamp'] = pd.to_datetime(patient_df['timestamp'])

    # Crear un resumen del historial para el prompt
    history_summary = ""
    for index, row in patient_df.head(5).iterrows(): # Analizar las últimas 5 consultas
        history_summary += f"- En {row['timestamp'].strftime('%d-%b-%Y')}: PA {row['presion_sistolica']}/{row['presion_diastolica']} mmHg, FC {row['frec_cardiaca']} lpm, IMC {row['imc']:.1f}\n"

    prompt = f"""
    **ROL:** Eres un médico especialista en medicina interna y cardiología, actuando como un asistente de soporte a la decisión para otro colega.

    **TAREA:** Analiza el siguiente historial de consultas de un paciente y genera un resumen conciso junto con recomendaciones de manejo y seguimiento. Sé claro, profesional y basa tus sugerencias en la evidencia.

    **HISTORIAL DE CONSULTAS (últimas 5):**
    {history_summary}

    **GENERAR REPORTE CON LA SIGUIENTE ESTRUCTURA:**

    ### Análisis y Recomendaciones por IA

    **1. Resumen de Evolución:**
    (Describe la tendencia general del paciente. ¿Su presión está controlada? ¿Ha variado el IMC? ¿Hay alguna señal de alarma en la evolución?)

    **2. Puntos de Atención Críticos:**
    (Identifica los hallazgos más importantes que requieren atención. Por ejemplo: "La persistencia de cifras de presión arterial sistólica por encima de 140 mmHg a pesar del tratamiento.")

    **3. Recomendaciones de Manejo:**
    * **Farmacológico:** (Sugiere posibles ajustes o consideraciones. Ej: "Considerar optimizar la dosis de Losartán o agregar un segundo antihipertensivo si la meta de control no se ha alcanzado.")
    * **Estudios Complementarios:** (Sugiere pruebas para clarificar el diagnóstico. Ej: "Se recomienda solicitar un perfil lipídico y una hemoglobina glicosilada (HbA1c) para evaluar el riesgo metabólico completo.")
    * **Estilo de Vida (Plan Educacional):** (Proporciona recomendaciones claras para el paciente. Ej: "Reforzar la adherencia a una dieta baja en sodio (dieta DASH). Recomendar un plan de actividad física aeróbica de al menos 150 minutos por semana.")
    
    **4. Próximo Seguimiento Sugerido:**
    (Indica cuándo sería prudente volver a ver al paciente. Ej: "Reevaluación en consulta en 3 meses para valorar la respuesta a los ajustes de tratamiento.")
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
    # (Sin cambios respecto a la versión anterior)
    st.title("Plataforma de Gestión Clínica")
    with st.form("login_form"):
        email = st.text_input("Correo Electrónico del Médico")
        password = st.text_input("Contraseña", type="password")
        c1, c2 = st.columns(2)
        login_button = c1.form_submit_button("Iniciar Sesión", use_container_width=True, type="primary")
        register_button = c2.form_submit_button("Registrarse", use_container_width=True)
    if login_button:
        try:
            user = auth.get_user_by_email(email) # En una app real, se verificaría la contraseña
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
        # --- CORRECCIÓN AÑADIDA ---
        # Se utiliza .get() para solicitar el email de forma segura y evitar el error
        # si la página se recarga y el estado aún no está completamente sincronizado.
        physician_email = st.session_state.get('physician_email', 'Cargando...')
        st.write(physician_email)
        st.divider()
        if st.button("Registro de Pacientes", use_container_width=True):
            st.session_state.page = 'patient_registry'
            st.session_state.selected_patient_id = None # Deseleccionar paciente al volver al registro
            st.rerun()
        st.divider()
        if st.button("Cerrar Sesión", use_container_width=True):
            st.session_state.logged_in = False
            st.rerun()
        st.info(f"**Versión:** {APP_VERSION}")

    # --- Navegación principal ---
    if st.session_state.page == 'patient_registry':
        render_patient_registry()
    elif st.session_state.page == 'patient_dashboard':
        render_patient_dashboard()

def render_patient_registry():
    st.title("Registro de Pacientes")
    patients = get_physician_patients(st.session_state.physician_email)
    
    with st.expander("➕ Registrar Nuevo Paciente", expanded=False):
        with st.form("new_patient_form", clear_on_submit=True):
            nombre = st.text_input("Nombres Completos")
            cedula = st.text_input("Documento de Identidad")
            telefono = st.text_input("Teléfono")
            submitted = st.form_submit_button("Registrar Paciente")
            if submitted and nombre and cedula:
                save_new_patient(st.session_state.physician_email, {"nombre": nombre, "cedula": cedula, "telefono": telefono})
                st.rerun()

    st.divider()
    st.header("Lista de Pacientes")
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
    patient_info = DB.collection('patients').document(patient_id).get().to_dict()
    st.title(f"Dashboard de: {patient_info['nombre']}")
    st.caption(f"Documento: {patient_info['cedula']}")

    tab1, tab2 = st.tabs(["📈 Historial y Gráficos", "✍️ Registrar Nueva Consulta"])

    with tab1:
        df_history = load_patient_history(patient_id)
        if df_history.empty:
            st.info("Este paciente no tiene consultas registradas. Agregue una en la pestaña 'Registrar Nueva Consulta'.")
        else:
            st.header("Evolución de Signos Vitales")
            c1, c2 = st.columns(2)
            presion_chart = alt.Chart(df_history).mark_line(point=True).encode(
                x=alt.X('timestamp:T', title='Fecha'),
                y=alt.Y('presion_sistolica:Q', title='Presión Sistólica'),
                y2='presion_diastolica:Q',
                tooltip=['timestamp', 'presion_sistolica', 'presion_diastolica']
            ).properties(title="Evolución de Presión Arterial").interactive()
            c1.altair_chart(presion_chart, use_container_width=True)

            imc_chart = alt.Chart(df_history).mark_line(point=True, color='green').encode(
                x=alt.X('timestamp:T', title='Fecha'),
                y=alt.Y('imc:Q', title='IMC', scale=alt.Scale(zero=False)),
                tooltip=['timestamp', 'imc']
            ).properties(title="Evolución del IMC").interactive()
            c2.altair_chart(imc_chart, use_container_width=True)

            st.divider()
            if st.button("🧠 Análisis y Recomendaciones por IA", use_container_width=True, type="primary"):
                recommendations = generate_ai_recommendations(df_history.to_dict())
                st.markdown(recommendations)

    with tab2:
        with st.form("new_consultation_form", clear_on_submit=True):
            st.header("Datos de la Consulta Actual")
            c1, c2, c3 = st.columns(3)
            presion_sistolica = c1.number_input("Presión Sistólica", 80, 220, 120)
            presion_diastolica = c1.number_input("Presión Diastólica", 50, 140, 80)
            frec_cardiaca = c2.number_input("Frecuencia Cardíaca", 40, 150, 75)
            imc = c3.number_input("IMC", 15.0, 50.0, 24.0, 0.1)
            motivo_consulta = st.text_area("Motivo de Consulta y Notas de Evolución")
            if st.form_submit_button("Guardar Consulta", use_container_width=True):
                consultation_data = {
                    "presion_sistolica": presion_sistolica, "presion_diastolica": presion_diastolica,
                    "frec_cardiaca": frec_cardiaca, "imc": imc, "motivo_consulta": motivo_consulta
                }
                save_consultation(patient_id, consultation_data)
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


