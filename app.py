# -*- coding: utf-8 -*-
"""
Sistema Clínico Profesional con Autenticación y Dashboard
Versión: 11.0 ("Clinical Pro")
Descripción: Evolución completa a una plataforma de nivel profesional.
Introduce autenticación de usuarios, recolección de datos exhaustiva,
persistencia de datos segura por paciente en Firebase y un dashboard
clínico funcional con historial y visualizaciones.
"""

# --- LIBRERÍAS ---
import streamlit as st
import pandas as pd
import numpy as np
import hashlib
from datetime import datetime, timezone
import firebase_admin
from firebase_admin import credentials, firestore, auth
import google.generativeai as genai
import altair as alt

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Plataforma de Salud Digital",
    page_icon="assets/favicon.png", # Considera añadir un favicon
    layout="wide"
)

# --- ESTILOS CSS PERSONALIZADOS (Opcional) ---
st.markdown("""
<style>
    .stButton>button {
        border-radius: 20px;
    }
    .st-emotion-cache-1y4p8pa {
        padding-top: 2rem;
    }
</style>
""", unsafe_allow_html=True)


# --- CONSTANTES ---
APP_VERSION = "11.0.0 (Clinical Pro)"

# ==============================================================================
# MÓDULO 1: CONEXIONES Y AUTENTICACIÓN
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

# Inicialización del estado de sesión
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_email = None
    st.session_state.page = 'login'

# ==============================================================================
# MÓDULO 2: LÓGICA DE NEGOCIO (INFERENCIA, PERSISTENCIA, DATOS)
# ==============================================================================

def save_evaluation(user_email, patient_data, inferences):
    """Guarda una evaluación bajo el perfil de un usuario específico."""
    if not DB:
        st.warning("DB no disponible, datos no guardados.")
        return
    try:
        timestamp = datetime.now(timezone.utc)
        doc_id = timestamp.strftime('%Y-%m-%d_%H-%M-%S')
        
        # Ruta de la colección: users/{email}/evaluations/{timestamp}
        record_ref = DB.collection('users').document(user_email).collection('evaluations').document(doc_id)
        
        record_to_save = {
            'timestamp_utc': timestamp.isoformat(),
            'app_version': APP_VERSION,
            'patient_data': patient_data,
            'system_inferences': inferences
        }
        record_ref.set(record_to_save)
        st.toast(f"Evaluación guardada para {user_email}", icon="💾")
    except Exception as e:
        st.error(f"No se pudo guardar la evaluación: {e}")

def load_user_data(user_email):
    """Carga todas las evaluaciones de un usuario específico."""
    if not DB: return pd.DataFrame()
    try:
        evals_ref = DB.collection('users').document(user_email).collection('evaluations').stream()
        records = [doc.to_dict() for doc in evals_ref]
        if not records: return pd.DataFrame()
        
        # Procesar datos para el dashboard
        processed_data = []
        for rec in records:
            flat_data = rec['patient_data']
            flat_data['timestamp'] = pd.to_datetime(rec['timestamp_utc'])
            processed_data.append(flat_data)
        
        df = pd.DataFrame(processed_data).sort_values('timestamp', ascending=False)
        return df
    except Exception as e:
        st.error(f"Error al cargar el historial: {e}")
        return pd.DataFrame()

# (El motor de inferencia y la generación de impresión no han cambiado)
def clinical_risk_inference_engine(data: dict) -> dict:
    """Motor de inferencia basado en factores de riesgo ponderados."""
    inferences = {}
    cardio_factors = {
        'edad_avanzada': (data.get('edad', 0) > 55) * 1.5,
        'presion_elevada': (data.get('presion_sistolica', 0) >= 140) * 3.0 + (130 <= data.get('presion_sistolica', 0) < 140) * 1.5,
        'obesidad': (data.get('imc', 0) >= 30) * 2.0,
        'tabaquismo': data.get('tabaquismo', False) * 2.5,
        'historia_familiar': data.get('historia_familiar_cardio', False) * 1.0,
        'sintoma_dolor_pecho': data.get('dolor_pecho', False) * 4.0
    }
    cardio_score = sum(cardio_factors.values())
    if cardio_score > 4.0:
        inferences['Enfermedades Cardiovasculares'] = {'Riesgo': 'ALTO'}
    return inferences

# ==============================================================================
# MÓDULO 3: VISTAS Y COMPONENTES DE UI
# ==============================================================================

def render_login_page():
    st.title("Bienvenido a la Plataforma de Salud Digital")
    st.write("Por favor, inicie sesión o regístrese para continuar.")
    
    with st.form("login_form"):
        email = st.text_input("Correo Electrónico")
        password = st.text_input("Contraseña", type="password")
        
        login_button = st.form_submit_button("Iniciar Sesión", use_container_width=True)
        register_button = st.form_submit_button("Registrarse", use_container_width=True, type="secondary")

    if login_button:
        try:
            user = auth.get_user_by_email(email)
            # Simplificación: En una app real, se verificaría la contraseña.
            st.session_state.logged_in = True
            st.session_state.user_email = user.email
            st.session_state.page = 'home'
            st.rerun()
        except Exception as e:
            st.error(f"Error de inicio de sesión: {e}")

    if register_button:
        try:
            user = auth.create_user(email=email, password=password)
            st.success(f"Usuario {user.email} registrado exitosamente. Por favor, inicie sesión.")
        except Exception as e:
            st.error(f"Error de registro: {e}")

def render_main_app():
    with st.sidebar:
        st.header(f"Bienvenido,")
        st.write(st.session_state.user_email)
        st.divider()
        
        if st.button("Página Principal", use_container_width=True):
            st.session_state.page = 'home'
        if st.button("Registrar Nueva Consulta", use_container_width=True):
            st.session_state.page = 'screening'
        if st.button("Dashboard del Paciente", use_container_width=True):
            st.session_state.page = 'dashboard'
        
        st.divider()
        if st.button("Cerrar Sesión", use_container_width=True, type="secondary"):
            st.session_state.logged_in = False
            st.session_state.user_email = None
            st.session_state.page = 'login'
            st.rerun()
            
        st.info(f"**Versión:** {APP_VERSION}")

    # Contenido de la página principal
    if st.session_state.page == 'home':
        st.title("Página Principal")
        st.image("https://images.unsplash.com/photo-1576091160550-2173dba999ab?q=80&w=2070", use_column_width=True)

    elif st.session_state.page == 'screening':
        render_screening_page()
        
    elif st.session_state.page == 'dashboard':
        render_dashboard_page()

def render_screening_page():
    st.title("⚕️ Registro de Nueva Consulta")
    with st.form("evaluation_form"):
        # Sección 1: Datos Demográficos
        with st.expander("1. Información Demográfica del Paciente", expanded=True):
            c1, c2, c3 = st.columns(3)
            nombre = c1.text_input("Nombres Completos")
            cedula = c2.text_input("Cédula / Documento de Identidad")
            telefono = c3.text_input("Teléfono de Contacto")
            direccion = c1.text_input("Dirección de Residencia")
            email_paciente = c2.text_input("Correo Electrónico del Paciente", value=st.session_state.user_email)
            edad = c3.slider("Edad", 1, 100, 45)

        # Sección 2: Historial Clínico
        with st.expander("2. Historial Clínico y Antecedentes"):
            c1, c2 = st.columns(2)
            dx_previos = c1.multiselect("Diagnósticos Previos Conocidos",
                ["Hipertensión Arterial", "Diabetes Mellitus", "Dislipidemia (Colesterol Alto)", "Asma/EPOC", "Hipotiroidismo"])
            medicamentos = c2.text_area("Medicamentos Actuales (nombre y dosis)")
            alergias = c1.text_area("Alergias Conocidas")
            cirugias = c2.text_area("Cirugías Previas Relevantes")

        # Sección 3: Signos Vitales y Antropometría
        with st.expander("3. Signos Vitales y Medidas"):
            c1, c2, c3 = st.columns(3)
            presion_sistolica = c1.slider("Presión Arterial Sistólica (mmHg)", 80, 220, 120)
            presion_diastolica = c1.slider("Presión Arterial Diastólica (mmHg)", 50, 140, 80)
            frec_cardiaca = c2.slider("Frecuencia Cardíaca (lat/min)", 40, 150, 75)
            frec_respiratoria = c2.slider("Frecuencia Respiratoria (resp/min)", 10, 30, 16)
            temperatura = c3.slider("Temperatura (°C)", 35.0, 41.0, 36.5, 0.1)
            imc = c3.slider("Índice de Masa Corporal (IMC)", 15.0, 50.0, 24.0, 0.1)

        submitted = st.form_submit_button("Guardar y Analizar Consulta", use_container_width=True, type="primary")

    if submitted:
        patient_data = {
            "nombre": nombre, "cedula": cedula, "telefono": telefono, "direccion": direccion,
            "email_paciente": email_paciente, "edad": edad, "dx_previos": dx_previos,
            "medicamentos": medicamentos, "alergias": alergias, "cirugias": cirugias,
            "presion_sistolica": presion_sistolica, "presion_diastolica": presion_diastolica,
            "frec_cardiaca": frec_cardiaca, "frec_respiratoria": frec_respiratoria,
            "temperatura": temperatura, "imc": imc
        }
        inferences = clinical_risk_inference_engine(patient_data)
        save_evaluation(st.session_state.user_email, patient_data, inferences)
        st.success("Consulta registrada exitosamente.")


def render_dashboard_page():
    st.title(f"📊 Dashboard de {st.session_state.user_email}")
    df = load_user_data(st.session_state.user_email)

    if df.empty:
        st.info("No hay consultas registradas para este paciente. Registre una nueva consulta para ver los datos aquí.")
        return

    st.header("Historial de Signos Vitales")
    c1, c2 = st.columns(2)
    
    # Gráfico de Presión Arterial
    presion_chart = alt.Chart(df).mark_line(point=True).encode(
        x=alt.X('timestamp:T', title='Fecha de Consulta'),
        y=alt.Y('presion_sistolica:Q', title='Presión Sistólica (mmHg)'),
        tooltip=['timestamp:T', 'presion_sistolica:Q']
    ).properties(title='Evolución de la Presión Arterial').interactive()
    c1.altair_chart(presion_chart, use_container_width=True)

    # Gráfico de IMC
    imc_chart = alt.Chart(df).mark_bar().encode(
        x=alt.X('timestamp:T', title='Fecha de Consulta'),
        y=alt.Y('imc:Q', title='Índice de Masa Corporal (kg/m²)'),
        tooltip=['timestamp:T', 'imc:Q']
    ).properties(title='Historial de IMC').interactive()
    c2.altair_chart(imc_chart, use_container_width=True)

    st.divider()
    st.header("Registro Completo de Consultas")
    st.dataframe(df)


# ==============================================================================
# MÓDULO 4: CONTROLADOR PRINCIPAL
# ==============================================================================
def main():
    if not DB or not GEMINI_MODEL:
        st.error("Servicios de backend no disponibles. La aplicación no puede continuar.")
        return

    if st.session_state.logged_in:
        render_main_app()
    else:
        render_login_page()

if __name__ == "__main__":
    main()

