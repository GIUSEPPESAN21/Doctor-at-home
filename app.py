# -*- coding: utf-8 -*-
"""
Suite de Diagnóstico Integral - Aplicación Principal
Versión: 23.0 ("Modern UI/UX")
Descripción: Versión con una interfaz de usuario rediseñada. Elimina el panel
lateral en favor de una navegación superior, introduce CSS personalizado para
mejorar colores, botones y contenedores, y añade animaciones sutiles para
una experiencia de usuario más moderna y fluida.
"""
# --- LIBRERÍAS ---
import streamlit as st
import pandas as pd
from firebase_admin import auth
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch

# --- MÓDulos PERSONALIZADOS ---
import firebase_utils
from gemini_utils import GeminiUtils

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Suite Clínica Moderna",
    page_icon="🩺",
    layout="wide"
)

# ==============================================================================
# MÓDULO 1: ESTILOS Y CONFIGURACIÓN INICIAL
# ==============================================================================
def apply_custom_styling():
    """Inyecta CSS personalizado para una interfaz de usuario mejorada."""
    custom_css = """
    <style>
        /* --- Paleta de Colores y Variables --- */
        :root {
            --primary-color: #0d6efd; /* Azul profesional y moderno */
            --primary-hover: #0a58ca;
            --secondary-color: #e9ecef; /* Un gris claro para acentos */
            --background-color: #f8f9fa; /* Fondo ligeramente gris */
            --text-color: #212529;
            --card-bg-color: #ffffff;
            --border-color: #dee2e6;
            --shadow-color: rgba(0, 0, 0, 0.075);
        }

        /* --- Estilo General del Body --- */
        .stApp {
            background-color: var(--background-color);
            color: var(--text-color);
        }
        
        /* --- Animación de Entrada --- */
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(15px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .main > div {
            animation: fadeIn 0.6s ease-out;
        }

        /* --- Estilo de Botones Personalizado --- */
        div[data-testid="stButton"] > button {
            border-radius: 0.5rem; /* Bordes redondeados */
            padding: 0.6em 1.2em;
            font-weight: 600;
            transition: all 0.25s ease-in-out;
            box-shadow: 0 4px 6px rgba(0,0,0,0.05);
            border: 1px solid var(--primary-color);
        }
        div[data-testid="stButton"] > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 12px rgba(0,0,0,0.1);
        }
        
        /* Botones Primarios (Guardar, Registrar, etc.) */
        div[data-testid="stButton"] > button[kind="primary"] {
            background-color: var(--primary-color);
            color: white;
        }
        div[data-testid="stButton"] > button[kind="primary"]:hover {
            background-color: var(--primary-hover);
            border-color: var(--primary-hover);
        }
        
        /* Botones Secundarios (Cerrar Sesión, etc.) */
        div[data-testid="stButton"] > button[kind="secondary"] {
            background-color: var(--card-bg-color);
            color: var(--primary-color);
        }
         div[data-testid="stButton"] > button[kind="secondary"]:hover {
            background-color: #eef5ff; /* Un azul muy claro al pasar el mouse */
        }
        
        /* --- Estilo de Contenedores y Tarjetas --- */
        [data-testid="stVerticalBlock"] [data-testid="stVerticalBlock"] [data-testid="stVerticalBlockBorderWrapper"] {
            background-color: var(--card-bg-color);
            border-radius: 0.75rem;
            border: 1px solid var(--border-color);
            box-shadow: 0 4px 12px var(--shadow-color);
            padding: 1em;
        }
        
        /* --- Estilo de Expanders --- */
        .st-emotion-cache-1h9usn1 { /* Cabecera del expander */
            border-radius: 0.5rem;
            border: 1px solid var(--border-color);
            background-color: #f7faff;
        }
    </style>
    """
    st.markdown(custom_css, unsafe_allow_html=True)

# Inicializa Firebase y Gemini
DB = firebase_utils.DB
try:
    GEMINI = GeminiUtils()
    IS_MODEL_CONFIGURED = True
except (ValueError, Exception) as e:
    st.error(e, icon="🔑")
    GEMINI = None
    IS_MODEL_CONFIGURED = False

# Inicialización del estado de la sesión
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.physician_email = None
    st.session_state.page = 'login'
    st.session_state.selected_patient_id = None
    st.session_state.ai_analysis_running = False
    st.session_state.last_clicked_ai = None

# ==============================================================================
# MÓDULO 2: GENERACIÓN DE REPORTES PDF (Sin cambios)
# ==============================================================================
def create_patient_report_pdf(patient_info, history_df):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=(8.5 * inch, 11 * inch))
    styles = getSampleStyleSheet()
    story = []
    story.append(Paragraph(str(patient_info.get('nombre', 'N/A')), styles['h1']))
    story.append(Paragraph(f"Documento: {patient_info.get('cedula', 'N/A')}", styles['Normal']))
    story.append(Paragraph(f"Edad: {patient_info.get('edad', 'N/A')} años", styles['Normal']))
    story.append(Paragraph(f"Dirección: {patient_info.get('direccion', 'N/A')}", styles['Normal']))
    story.append(Spacer(1, 0.25 * inch))
    for _, row in history_df.sort_values('timestamp').iterrows():
        story.append(Paragraph(f"Consulta del {row['timestamp'].strftime('%d de %B, %Y')}", styles['h2']))
        motivo = str(row.get('motivo_consulta', 'N/A')).replace('\n', '<br/>')
        story.append(Paragraph(f"<b>Motivo:</b> {motivo}", styles['Normal']))
        pa_s = str(row.get('presion_sistolica', 'N/A'))
        pa_d = str(row.get('presion_diastolica', 'N/A'))
        gluc = str(row.get('glucemia', 'N/A'))
        imc = str(row.get('imc', 'N/A'))
        vitales = f"<b>PA:</b> {pa_s}/{pa_d} mmHg | <b>Glucemia:</b> {gluc} mg/dL | <b>IMC:</b> {imc}"
        story.append(Paragraph(vitales, styles['Normal']))
        if 'ai_analysis' in row and pd.notna(row['ai_analysis']):
            story.append(Spacer(1, 0.1 * inch))
            story.append(Paragraph("<b>--- Análisis por IA ---</b>", styles['h3']))
            analysis_text = str(row['ai_analysis']).replace('\n', '<br/>').replace('**', '<b>').replace('**', '</b>')
            story.append(Paragraph(analysis_text, styles['Normal']))
        story.append(Spacer(1, 0.25 * inch))
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

# ==============================================================================
# MÓDULO 3: VISTAS Y COMPONENTES DE UI (Actualizado)
# ==============================================================================
def render_login_page():
    st.title("Plataforma de Gestión Clínica")
    st.text("Una herramienta moderna para el seguimiento y análisis de pacientes.")
    st.markdown("---")
    
    with st.container(border=True):
      with st.form("login_form"):
          email = st.text_input("Correo Electrónico del Médico")
          password = st.text_input("Contraseña", type="password")
          login_button = st.form_submit_button("Iniciar Sesión", use_container_width=True, type="primary")
          register_button = st.form_submit_button("Registrarse", use_container_width=True)
          
      if login_button:
          try:
              user = auth.get_user_by_email(email)
              st.session_state.logged_in = True
              st.session_state.physician_email = user.email
              st.session_state.page = 'control_panel'
              st.rerun()
          except Exception as e: st.error(f"Error de inicio de sesión: {e}")
      if register_button:
          try:
              user = auth.create_user(email=email, password=password)
              st.success(f"Médico {user.email} registrado. Por favor, inicie sesión.")
          except Exception as e: st.error(f"Error de registro: {e}")

def render_header():
    """Renderiza la nueva barra de navegación superior."""
    with st.container(border=True):
        col1, col2, col3 = st.columns([4, 1.5, 1.5])
        with col1:
            st.markdown(f"##### 👨‍⚕️ **Médico:** {st.session_state.get('physician_email', 'Cargando...')}")
        with col2:
            if st.button("Panel de Control", use_container_width=True):
                st.session_state.page = 'control_panel'
                st.session_state.selected_patient_id = None
                st.rerun()
        with col3:
            if st.button("Cerrar Sesión", use_container_width=True, type="secondary"):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.rerun()
    st.markdown("<br>", unsafe_allow_html=True)


def render_main_app():
    """Renderiza la aplicación principal, incluyendo la nueva cabecera."""
    render_header()
    if st.session_state.page == 'control_panel':
        render_control_panel()
    elif st.session_state.page == 'patient_dashboard':
        render_patient_dashboard()

def render_control_panel():
    st.title("Panel de Control Médico")

    tab1, tab2 = st.tabs(["✍️ Gestión de Pacientes", "ℹ️ Acerca de"])
    with tab1:
        st.header("Registrar Nuevo Paciente")
        with st.form("new_patient_form", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            nombre = c1.text_input("Nombres Completos")
            cedula = c2.text_input("Documento de Identidad (ID único)")
            edad = c3.number_input("Edad", min_value=0, max_value=120)
            direccion = st.text_input("Dirección de Residencia")
            telefono = st.text_input("Teléfono")
            submitted = st.form_submit_button("Registrar Paciente", use_container_width=True, type="primary")
            if submitted and nombre and cedula:
                firebase_utils.save_new_patient(st.session_state.physician_email, {"nombre": nombre, "cedula": cedula, "edad": edad, "telefono": telefono, "direccion": direccion})
                st.rerun()
        
        st.divider()
        st.header("Seleccionar Paciente Existente")
        patients = firebase_utils.get_physician_patients(st.session_state.physician_email)
        if not patients:
            st.info("No hay pacientes registrados. Agregue uno nuevo para comenzar.")
        else:
            for patient in patients:
                with st.container(border=True):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.subheader(patient['nombre'])
                        st.caption(f"ID: {patient['cedula']} | Edad: {patient.get('edad', 'N/A')} años")
                    with col2:
                        if st.button("Ver Historial", key=patient['id'], use_container_width=True, type="primary"):
                            st.session_state.selected_patient_id = patient['id']
                            st.session_state.page = 'patient_dashboard'
                            st.rerun()
    with tab2:
        st.markdown("### Acerca de esta Herramienta")
        st.markdown("Esta suite de software modular asiste a profesionales de la salud en el seguimiento y análisis de pacientes, utilizando inteligencia artificial para generar recomendaciones y optimizar el flujo de trabajo.")
        st.divider()
        st.write("**Autor:** Joseph Javier Sánchez Acuña")
        st.write("_Ingeniero Industrial, Experto en IA y Desarrollo de Software._")
        st.write("🔗 [LinkedIn](https://www.linkedin.com/in/joseph-javier-sánchez-acuña-150410275) | 📂 [GitHub](https://github.com/GIUSEPPESAN21)")

def render_patient_dashboard():
    patient_id = st.session_state.selected_patient_id
    patient_info_ref = DB.collection('physicians').document(st.session_state.physician_email).collection('patients').document(patient_id)
    patient_info = patient_info_ref.get().to_dict() if patient_info_ref.get().exists else {}

    st.title(f"Dashboard Clínico de: {patient_info.get('nombre', 'N/A')}")
    st.caption(f"Documento: {patient_info.get('cedula', 'N/A')} | Edad: {patient_info.get('edad', 'N/A')} años")
    
    df_history = firebase_utils.load_patient_history(st.session_state.physician_email, patient_id)

    if not df_history.empty:
        pdf_data = create_patient_report_pdf(patient_info, df_history)
        st.download_button("📄 Descargar Reporte Completo en PDF", data=pdf_data, file_name=f"Reporte_{patient_info.get('cedula', 'N/A')}.pdf", mime="application/pdf")

    tab1, tab2 = st.tabs(["📈 Historial de Consultas", "✍️ Registrar Nueva Consulta"])
    with tab1:
        if df_history.empty:
            st.info("Este paciente aún no tiene consultas registradas.")
        else:
            if st.session_state.ai_analysis_running:
                consultation_id = st.session_state.last_clicked_ai
                row = df_history[df_history['id'] == consultation_id].iloc[0]
                history_summary = "Resumen del historial médico previo relevante del paciente."
                ai_report = GEMINI.generate_ai_holistic_review(patient_info, row.to_dict(), history_summary)
                firebase_utils.update_consultation_with_ai_analysis(st.session_state.physician_email, patient_id, consultation_id, ai_report)
                st.session_state.ai_analysis_running = False
                st.session_state.last_clicked_ai = None
                st.rerun()

            for _, row in df_history.iterrows():
                with st.expander(f"Consulta del {row['timestamp'].strftime('%d/%m/%Y %H:%M')}"):
                    st.write(f"**Motivo:** {row.get('motivo_consulta', 'N/A')}")
                    if 'ai_analysis' in row and pd.notna(row['ai_analysis']):
                        st.markdown("---"); st.markdown(row['ai_analysis'])
                    else:
                        if st.button("Generar Análisis con IA", key=f"ai_{row['id']}", disabled=st.session_state.ai_analysis_running or not IS_MODEL_CONFIGURED):
                            st.session_state.ai_analysis_running = True
                            st.session_state.last_clicked_ai = row['id']
                            st.rerun()
    with tab2:
        render_new_consultation_form(patient_id)

def render_new_consultation_form(patient_id):
    with st.form("new_consultation_form"):
        st.header("Datos de la Consulta")
        with st.expander("1. Anamnesis y Vitales", expanded=True):
            motivo_consulta = st.text_area("Motivo de Consulta y Notas de Evolución")
            cols = st.columns(5)
            presion_sistolica = cols[0].number_input("PA Sistólica", 0, value=120)
            presion_diastolica = cols[1].number_input("PA Diastólica", 0, value=80)
            frec_cardiaca = cols[2].number_input("Frec. Cardíaca", 0, value=70)
            glucemia = cols[3].number_input("Glucemia (mg/dL)", 0, value=95)
            imc = cols[4].number_input("IMC (kg/m²)", 0.0, format="%.1f", value=24.5)
        with st.expander("2. Revisión por Sistemas (Síntomas)"):
            sintomas_cardio = st.multiselect("Cardiovascular", ["Dolor de pecho", "Disnea", "Palpitaciones", "Edema"])
            sintomas_resp = st.multiselect("Respiratorio", ["Tos", "Expectoración", "Sibilancias"])
            sintomas_metabolico = st.multiselect("Metabólico", ["Polidipsia (mucha sed)", "Poliuria (mucha orina)", "Pérdida de peso"])
        with st.expander("3. Factores de Riesgo y Estilo de Vida"):
            cols = st.columns(2)
            dieta = cols[0].selectbox("Calidad de la Dieta", ["Saludable (DASH/Mediterránea)", "Regular", "Poco saludable (Procesados)"])
            ejercicio = cols[1].slider("Ejercicio Aeróbico (min/semana)", 0, 500, 150)
        
        submitted = st.form_submit_button("Guardar Consulta", use_container_width=True, type="primary")
        if submitted:
            consultation_data = {
                "motivo_consulta": motivo_consulta, "presion_sistolica": presion_sistolica, "presion_diastolica": presion_diastolica,
                "frec_cardiaca": frec_cardiaca, "glucemia": glucemia, "imc": imc,
                "sintomas_cardio": sintomas_cardio, "sintomas_resp": sintomas_resp, "sintomas_metabolico": sintomas_metabolico,
                "dieta": dieta, "ejercicio": ejercicio
            }
            firebase_utils.save_consultation(st.session_state.physician_email, patient_id, consultation_data)
            st.rerun()

# ==============================================================================
# MÓDULO 4: CONTROLADOR PRINCIPAL
# ==============================================================================
def main():
    """Controlador principal que aplica estilos y decide qué página mostrar."""
    apply_custom_styling()
    if st.session_state.get('logged_in', False):
        render_main_app()
    else:
        render_login_page()

if __name__ == "__main__":
    main()

