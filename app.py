# -*- coding: utf-8 -*-
"""
Suite de Diagnóstico Integral
Versión: 15.0 ("Suite Clínica Definitiva")
Descripción: Versión final que corrige un error crítico en el motor de PDF,
restaura el formulario de consulta clínica exhaustivo para una captura de datos
rica y precisa, e integra la edad del paciente en el registro, dashboard y
reportes. Esta versión representa la culminación del desarrollo, resultando en
una herramienta robusta y profesional.
"""
# --- LIBRERías ---
import streamlit as st
import pandas as pd
from datetime import datetime, timezone
import firebase_admin
from firebase_admin import credentials, firestore, auth
import google.generativeai as genai
from fpdf import FPDF

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Suite Clínica Definitiva",
    page_icon="🩺",
    layout="wide"
)

# --- CONSTANTES ---
APP_VERSION = "15.0.0 (Suite Clínica Definitiva)"

# ==============================================================================
# MÓDULO 1: CONEXIONES Y GESTIÓN DE ESTADO
# ==============================================================================
@st.cache_resource
def init_connections():
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
    if not DB: return None
    timestamp = datetime.now(timezone.utc)
    doc_id = timestamp.strftime('%Y-%m-%d_%H-%M-%S')
    consultation_data['timestamp_utc'] = timestamp.isoformat()
    clean_data = {k: v for k, v in consultation_data.items() if v is not None and v != ''}
    DB.collection('physicians').document(physician_email).collection('patients').document(patient_id).collection('consultations').document(doc_id).set(clean_data)
    st.toast("Consulta guardada.", icon="✅")
    return doc_id

def update_consultation_with_ai_analysis(physician_email, patient_id, consultation_id, ai_report):
    if not DB: return
    consultation_ref = DB.collection('physicians').document(physician_email).collection('patients').document(patient_id).collection('consultations').document(consultation_id)
    consultation_ref.update({"ai_analysis": ai_report})
    st.toast("Análisis de IA guardado en el historial.", icon="🧠")

def load_patient_history(physician_email, patient_id):
    if not DB: return pd.DataFrame()
    consultations_ref = DB.collection('physicians').document(physician_email).collection('patients').document(patient_id).collection('consultations').order_by('timestamp_utc', direction=firestore.Query.DESCENDING).stream()
    records = []
    for doc in consultations_ref:
        record = doc.to_dict()
        record['id'] = doc.id
        records.append(record)
    if not records: return pd.DataFrame()
    df = pd.DataFrame(records)
    df['timestamp'] = pd.to_datetime(df['timestamp_utc'])
    return df

# ==============================================================================
# MÓDULO 3: INTELIGENCIA ARTIFICIAL (GEMINI)
# ==============================================================================
@st.cache_data(show_spinner="Generando análisis y recomendaciones con IA...", ttl=300)
def generate_ai_holistic_review(latest_consultation, history_summary):
    if not GEMINI_MODEL: return "Servicio de IA no disponible."
    prompt = f"""
    **ROL:** Eres un médico especialista en medicina interna y cardiología.
    **TAREA:** Analiza la última consulta en el contexto del historial del paciente para generar un reporte clínico estructurado.
    **DATOS DE LA ÚLTIMA CONSULTA:**
    - Motivo: {latest_consultation.get('motivo_consulta', 'No especificado')}
    - Signos Vitales: PA {latest_consultation.get('presion_sistolica', 'N/A')}/{latest_consultation.get('presion_diastolica', 'N/A')} mmHg, Glucemia {latest_consultation.get('glucemia', 'N/A')} mg/dL.
    - Síntomas Relevantes: {latest_consultation.get('sintomas_cardio', [])}, {latest_consultation.get('sintomas_resp', [])}, {latest_consultation.get('sintomas_metabolico', [])}
    **HISTORIAL DE CONSULTAS (resumen):**
    {history_summary}
    **GENERAR REPORTE CON LA SIGUIENTE ESTRUCTURA:**
    ### Análisis Clínico Integral por IA
    **1. Impresión Diagnóstica Principal y Diferenciales:**
    **2. Estratificación del Riesgo:**
    **3. Plan de Manejo Sugerido:**
    * **Estudios Diagnósticos:**
    * **Tratamiento Farmacológico:**
    * **Metas Terapéuticas:**
    **4. Educación para el Paciente:**
    """
    try:
        response = GEMINI_MODEL.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"**Error al generar recomendaciones:** {e}"

# ==============================================================================
# MÓDULO 4: GENERACIÓN DE REPORTES PDF
# ==============================================================================
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'Reporte Clínico del Paciente', 0, 1, 'C')
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')

def create_patient_report_pdf(patient_info, history_df):
    pdf = PDF()
    pdf.add_page()
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(0, 10, str(patient_info.get('nombre', 'N/A')), 0, 1)
    
    pdf.set_font('Arial', '', 12)
    pdf.cell(0, 10, f"Documento: {patient_info.get('cedula', 'N/A')}", 0, 1)
    pdf.cell(0, 10, f"Edad: {patient_info.get('edad', 'N/A')} años", 0, 1)
    pdf.cell(0, 10, f"Dirección: {patient_info.get('direccion', 'N/A')}", 0, 1)
    pdf.ln(10)

    for _, row in history_df.sort_values('timestamp').iterrows():
        pdf.set_font('Arial', 'B', 12)
        pdf.cell(0, 10, f"Consulta del {row['timestamp'].strftime('%d de %B, %Y')}", 0, 1)
        pdf.set_font('Arial', '', 10)
        
        pdf.multi_cell(0, 5, f"Motivo: {str(row.get('motivo_consulta', 'N/A'))}")
        
        vitales = (f"PA: {str(row.get('presion_sistolica', 'N/A'))}/{str(row.get('presion_diastolica', 'N/A'))} mmHg | "
                   f"Glucemia: {str(row.get('glucemia', 'N/A'))} mg/dL | "
                   f"IMC: {str(row.get('imc', 'N/A'))}")
        pdf.multi_cell(0, 5, vitales)
        
        if 'ai_analysis' in row and pd.notna(row['ai_analysis']):
            pdf.set_font('Arial', 'I', 10)
            pdf.ln(5)
            pdf.multi_cell(0, 5, "--- Análisis por IA ---")
            pdf.multi_cell(0, 5, str(row['ai_analysis']))
        
        pdf.ln(10)
    
    return pdf.output()

# ==============================================================================
# MÓDULO 5: VISTAS Y COMPONENTES DE UI
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
        st.write(st.session_state.get('physician_email', 'Cargando...'))
        st.divider()
        if st.button("Panel de Pacientes", use_container_width=True):
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
    with st.expander("➕ Registrar Nuevo Paciente", expanded=False):
        with st.form("new_patient_form", clear_on_submit=True):
            nombre = st.text_input("Nombres Completos")
            cedula = st.text_input("Documento de Identidad (ID único)")
            edad = st.number_input("Edad", min_value=0, max_value=120)
            direccion = st.text_input("Dirección de Residencia")
            telefono = st.text_input("Teléfono")
            submitted = st.form_submit_button("Registrar Paciente")
            if submitted and nombre and cedula:
                save_new_patient(st.session_state.physician_email, {"nombre": nombre, "cedula": cedula, "edad": edad, "telefono": telefono, "direccion": direccion})
                st.rerun()

    st.divider()
    st.header("Seleccionar Paciente")
    patients = get_physician_patients(st.session_state.physician_email)
    if not patients:
        st.info("No hay pacientes registrados.")
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
    st.title(f"Dashboard Clínico de: {patient_info.get('nombre', 'N/A')}")
    st.caption(f"Documento: {patient_info.get('cedula', 'N/A')} | Edad: {patient_info.get('edad', 'N/A')} años")
    
    df_history = load_patient_history(st.session_state.physician_email, patient_id)

    if not df_history.empty:
        pdf_data = create_patient_report_pdf(patient_info, df_history)
        st.download_button(
            label="📄 Descargar Reporte Completo en PDF",
            data=pdf_data,
            file_name=f"Reporte_{patient_info.get('cedula', 'N/A')}.pdf",
            mime="application/pdf",
        )

    tab1, tab2 = st.tabs(["📈 Historial de Consultas", "✍️ Registrar Nueva Consulta"])

    with tab1:
        if df_history.empty:
            st.info("Este paciente no tiene consultas.")
        else:
            for _, row in df_history.iterrows():
                with st.expander(f"Consulta del {row['timestamp'].strftime('%d/%m/%Y %H:%M')}"):
                    st.write(f"**Motivo:** {row.get('motivo_consulta', 'N/A')}")
                    if 'ai_analysis' in row and pd.notna(row['ai_analysis']):
                        st.markdown("**Análisis por IA:**")
                        st.info(row['ai_analysis'])
                    else:
                        if st.button("Generar Análisis con IA", key=f"ai_{row['id']}"):
                            history_summary = "..."
                            ai_report = generate_ai_holistic_review(row.to_dict(), history_summary)
                            update_consultation_with_ai_analysis(st.session_state.physician_email, patient_id, row['id'], ai_report)
                            st.rerun()

    with tab2:
        with st.form("new_consultation_form"):
            st.header("Datos de la Consulta")
            with st.expander("1. Anamnesis y Vitales", expanded=True):
                motivo_consulta = st.text_area("Motivo de Consulta y Notas de Evolución")
                c1, c2, c3, c4, c5 = st.columns(5)
                presion_sistolica = c1.number_input("PA Sistólica", min_value=0)
                presion_diastolica = c2.number_input("PA Diastólica", min_value=0)
                frec_cardiaca = c3.number_input("Frec. Cardíaca", min_value=0)
                glucemia = c4.number_input("Glucemia (mg/dL)", min_value=0)
                imc = c5.number_input("IMC (kg/m²)", min_value=0.0, format="%.1f")
            
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
                    "frec_cardiaca": frec_cardiaca, "glucemia": glucemia, "imc": imc,
                    "sintomas_cardio": sintomas_cardio, "sintomas_resp": sintomas_resp, "sintomas_metabolico": sintomas_metabolico,
                    "dieta": dieta, "ejercicio": ejercicio
                }
                save_consultation(st.session_state.physician_email, patient_id, consultation_data)
                st.rerun()

# ==============================================================================
# MÓDULO 6: CONTROLADOR PRINCIPAL
# ==============================================================================
def main():
    if st.session_state.get('logged_in', False):
        render_main_app()
    else:
        render_login_page()

if __name__ == "__main__":
    main()

