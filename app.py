# -*- coding: utf-8 -*-
"""
Suite de Diagnóstico Integral - Aplicación Principal
Versión: 25.0 ("Clinical UI Refinement")
Descripción: Renovación visual completa con una paleta de colores clínicos
(azules y verdes), botones rediseñados con gradientes y sombras mejoradas,
y animaciones más fluidas para una experiencia de usuario superior.
"""
# --- LIBRERÍAS ---
import streamlit as st
import pandas as pd
from firebase_admin import auth
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
import re 

# --- MÓDulos PERSONALIZADOS ---
import firebase_utils
from gemini_utils import GeminiUtils

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="SaludIA: Asistente Clínico",
    page_icon="🤖",
    layout="wide"
)

# ==============================================================================
# MÓDULO 1: ESTILOS Y CONFIGURACIÓN INICIAL
# ==============================================================================
def apply_custom_styling():
    """Inyecta CSS personalizado para una interfaz de usuario mejorada."""
    custom_css = """
    <style>
        /* --- Paleta de Colores Clínicos y Variables --- */
        :root {
            --primary-color: #0077b6; /* Azul clínico, profesional */
            --primary-hover: #023e8a;
            --success-color: #2a9d8f; /* Verde azulado para acciones positivas */
            --background-color: #f4f7f9; /* Gris azulado muy claro */
            --text-color: #333333;
            --card-bg-color: #ffffff;
            --border-color: #dee2e6;
            --shadow-color: rgba(0, 0, 0, 0.08);
        }

        /* --- Estilo General del Body --- */
        .stApp {
            background-color: var(--background-color);
            color: var(--text-color);
        }
        
        /* --- Animación de Entrada Mejorada --- */
        @keyframes fadeInUp {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .main > div {
            animation: fadeInUp 0.5s ease-out forwards;
        }

        /* --- Estilo de Botones Rediseñado --- */
        div[data-testid="stButton"] > button {
            border-radius: 8px;
            padding: 10px 18px;
            font-weight: 600;
            border: none;
            box-shadow: 0 2px 5px var(--shadow-color);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }
        div[data-testid="stButton"] > button:hover {
            transform: translateY(-3px);
            box-shadow: 0 6px 12px rgba(0, 0, 0, 0.15);
        }
        
        /* Botones Primarios */
        div[data-testid="stButton"] > button[kind="primary"] {
            background-color: var(--primary-color);
            color: white;
        }
        div[data-testid="stButton"] > button[kind="primary"]:hover {
            background-color: var(--primary-hover);
        }
        
        /* Botones Secundarios */
        div[data-testid="stButton"] > button[kind="secondary"] {
            background-color: var(--card-bg-color);
            color: var(--primary-color);
            border: 1px solid var(--border-color);
        }
         div[data-testid="stButton"] > button[kind="secondary"]:hover {
            background-color: #e9f5ff;
            border-color: var(--primary-color);
        }
        
        /* --- Estilo de Contenedores y Tarjetas con Transición --- */
        [data-testid="stVerticalBlock"] [data-testid="stVerticalBlock"] [data-testid="stVerticalBlockBorderWrapper"] {
            background-color: var(--card-bg-color);
            border-radius: 12px;
            border: 1px solid var(--border-color);
            box-shadow: 0 4px 12px var(--shadow-color);
            padding: 1.2em;
            transition: box-shadow 0.3s ease;
        }
        [data-testid="stVerticalBlock"] [data-testid="stVerticalBlock"] [data-testid="stVerticalBlockBorderWrapper"]:hover {
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
        }
        
        /* --- Estilo de Expanders --- */
        .st-emotion-cache-1h9usn1 {
            border-radius: 8px;
            border: 1px solid var(--border-color);
            background-color: #f8fcff;
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
def clean_html_for_reportlab(text):
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'###\s?(.*)', r'<b>\1</b>', text)
    text = text.replace('\n', '<br/>')
    return text

def create_patient_report_pdf(patient_info, history_df):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=(8.5 * inch, 11 * inch))
    styles = getSampleStyleSheet()
    story = []
    story.append(Paragraph(f"Reporte Clínico de {str(patient_info.get('nombre', 'N/A'))}", styles['h1']))
    story.append(Paragraph(f"Documento: {patient_info.get('cedula', 'N/A')}", styles['Normal']))
    story.append(Paragraph(f"Edad: {patient_info.get('edad', 'N/A')} años", styles['Normal']))
    story.append(Spacer(1, 0.25 * inch))

    for _, row in history_df.sort_values('timestamp').iterrows():
        story.append(Paragraph(f"Consulta del {row['timestamp'].strftime('%d de %B, %Y')}", styles['h2']))
        motivo = str(row.get('motivo_consulta', 'N/A')).replace('\n', '<br/>')
        story.append(Paragraph(f"<b>Motivo:</b> {motivo}", styles['Normal']))
        pa_s = str(row.get('presion_sistolica', 'N/A'))
        pa_d = str(row.get('presion_diastolica', 'N/A'))
        story.append(Paragraph(f"<b>Signos Vitales:</b> PA: {pa_s}/{pa_d} mmHg", styles['Normal']))
        
        if 'ai_analysis' in row and pd.notna(row['ai_analysis']):
            story.append(Spacer(1, 0.1 * inch))
            story.append(Paragraph("<b>--- Análisis por IA (SaludIA) ---</b>", styles['Normal']))
            raw_text = str(row['ai_analysis'])
            analysis_text = clean_html_for_reportlab(raw_text)
            try:
                story.append(Paragraph(analysis_text, styles['Normal']))
            except Exception as e:
                story.append(Paragraph(f"Error al renderizar análisis: {e}", styles['Normal']))
        story.append(Spacer(1, 0.25 * inch))
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

# ==============================================================================
# MÓDULO 3: VISTAS Y COMPONENTES DE UI (Sin cambios lógicos)
# ==============================================================================
def render_login_page():
    st.markdown("<h1 style='text-align: center; color: var(--primary-color);'>🤖 SaludIA</h1>", unsafe_allow_html=True)
    st.markdown("<h4 style='text-align: center; color: var(--text-color);'>Tu Asistente Clínico Inteligente</h4>", unsafe_allow_html=True)
    st.markdown("---")
    
    _, col2, _ = st.columns([1, 1.5, 1])
    with col2:
        with st.container(border=True):
            login_tab, register_tab = st.tabs(["**Iniciar Sesión**", "**Registrarse**"])
            with login_tab:
                with st.form("login_form"):
                    email = st.text_input("Correo Electrónico del Médico", key="login_email")
                    password = st.text_input("Contraseña", type="password", key="login_password")
                    login_button = st.form_submit_button("Acceder a la Plataforma", use_container_width=True, type="primary")
                    if login_button:
                        try:
                            user = auth.get_user_by_email(email)
                            st.session_state.logged_in = True
                            st.session_state.physician_email = user.email
                            st.session_state.page = 'control_panel'
                            st.rerun()
                        except Exception: st.error("Error: Verifique sus credenciales.")
            with register_tab:
                with st.form("register_form"):
                    new_email = st.text_input("Correo para Registro", key="register_email")
                    new_password = st.text_input("Crear Contraseña", type="password", key="register_password")
                    confirm_password = st.text_input("Confirmar Contraseña", type="password", key="confirm_password")
                    register_button = st.form_submit_button("Crear Cuenta", use_container_width=True)
                    if register_button:
                        if new_password == confirm_password:
                            try:
                                user = auth.create_user(email=new_email, password=new_password)
                                st.success(f"¡Cuenta para {user.email} creada! Ya puede iniciar sesión.")
                                st.balloons()
                            except Exception as e: st.error(f"Error de registro: {e}")
                        else: st.error("Las contraseñas no coinciden.")

def render_header():
    with st.container(border=True):
        col1, col2, col3 = st.columns([4, 1.5, 1.5])
        with col1:
            st.markdown(f"##### 👨‍⚕️ **Médico:** {st.session_state.get('physician_email', 'Cargando...')}")
        with col2:
            if st.button("Panel de Control", use_container_width=True):
                st.session_state.page = 'control_panel'; st.session_state.selected_patient_id = None; st.rerun()
        with col3:
            if st.button("Cerrar Sesión", use_container_width=True, type="secondary"):
                for key in list(st.session_state.keys()): del st.session_state[key]
                st.rerun()
    st.markdown("<br>", unsafe_allow_html=True)

def render_main_app():
    render_header()
    if st.session_state.page == 'control_panel': render_control_panel()
    elif st.session_state.page == 'patient_dashboard': render_patient_dashboard()

def render_control_panel():
    st.title("Panel de Control de SaludIA")
    tab1, tab2 = st.tabs(["✍️ Gestión de Pacientes", "ℹ️ Acerca de"])
    with tab1:
        st.header("Registrar Nuevo Paciente")
        with st.form("new_patient_form", clear_on_submit=True):
            cols = st.columns(3)
            nombre = cols[0].text_input("Nombres Completos")
            cedula = cols[1].text_input("Documento de Identidad (ID único)")
            edad = cols[2].number_input("Edad", 0, 120)
            direccion, telefono = st.columns(2)
            direccion = direccion.text_input("Dirección de Residencia")
            telefono = telefono.text_input("Teléfono")
            if st.form_submit_button("Registrar Paciente", use_container_width=True, type="primary"):
                if nombre and cedula:
                    firebase_utils.save_new_patient(st.session_state.physician_email, {"nombre": nombre, "cedula": cedula, "edad": edad, "telefono": telefono, "direccion": direccion})
                    st.rerun()
        st.divider()
        st.header("Seleccionar Paciente Existente")
        patients = firebase_utils.get_physician_patients(st.session_state.physician_email)
        if not patients: st.info("No hay pacientes registrados.")
        else:
            for patient in patients:
                with st.container(border=True):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.subheader(patient['nombre'])
                        st.caption(f"ID: {patient['cedula']} | Edad: {patient.get('edad', 'N/A')} años")
                    if col2.button("Ver Historial", key=patient['id'], use_container_width=True, type="primary"):
                        st.session_state.selected_patient_id = patient['id']
                        st.session_state.page = 'patient_dashboard'
                        st.rerun()
    with tab2:
        st.markdown("### Acerca de SaludIA")
        st.markdown("Esta suite asiste a profesionales de la salud en el seguimiento y análisis de pacientes, utilizando IA para generar recomendaciones y optimizar el flujo de trabajo.")
        st.write("**Autor:** Joseph Javier Sánchez Acuña")

def render_patient_dashboard():
    patient_id = st.session_state.selected_patient_id
    patient_info = firebase_utils.get_patient_details(st.session_state.physician_email, patient_id)
    st.title(f"Dashboard del Paciente: {patient_info.get('nombre', 'N/A')}")
    st.caption(f"Documento: {patient_info.get('cedula', 'N/A')} | Edad: {patient_info.get('edad', 'N/A')} años")
    df_history = firebase_utils.load_patient_history(st.session_state.physician_email, patient_id)
    if not df_history.empty:
        pdf_data = create_patient_report_pdf(patient_info, df_history)
        st.download_button("📄 Descargar Reporte Completo", data=pdf_data, file_name=f"Reporte_{patient_info.get('cedula')}.pdf", mime="application/pdf")
    
    tab1, tab2 = st.tabs(["📈 Historial", "✍️ Nueva Consulta"])
    with tab1:
        if df_history.empty: st.info("Este paciente no tiene consultas registradas.")
        else:
            if st.session_state.ai_analysis_running:
                consultation_id = st.session_state.last_clicked_ai
                row = df_history[df_history['id'] == consultation_id].iloc[0]
                history_summary = "Resumen del historial médico previo relevante."
                ai_report = GEMINI.generate_ai_holistic_review(patient_info, row.to_dict(), history_summary)
                firebase_utils.update_consultation_with_ai_analysis(st.session_state.physician_email, patient_id, consultation_id, ai_report)
                st.session_state.ai_analysis_running = False; st.session_state.last_clicked_ai = None; st.rerun()
            
            for _, row in df_history.iterrows():
                with st.expander(f"Consulta del {row['timestamp'].strftime('%d/%m/%Y %H:%M')}"):
                    st.write(f"**Motivo:** {row.get('motivo_consulta', 'N/A')}")
                    if 'ai_analysis' in row and pd.notna(row['ai_analysis']):
                        st.markdown("---"); st.markdown(row['ai_analysis'])
                    elif st.button("Generar Análisis con IA", key=f"ai_{row['id']}", disabled=st.session_state.ai_analysis_running or not IS_MODEL_CONFIGURED):
                        st.session_state.ai_analysis_running = True; st.session_state.last_clicked_ai = row['id']; st.rerun()
    with tab2:
        render_new_consultation_form(patient_id)

def render_new_consultation_form(patient_id):
    with st.form("new_consultation_form"):
        st.header("Datos de la Consulta")
        with st.expander("1. Anamnesis y Vitales", expanded=True):
            motivo = st.text_area("Motivo de Consulta y Notas")
            cols = st.columns(5)
            sistolica = cols[0].number_input("PA Sistólica", 0, value=120)
            diastolica = cols[1].number_input("PA Diastólica", 0, value=80)
            frec_cardiaca = cols[2].number_input("Frec. Cardíaca", 0, value=70)
            glucemia = cols[3].number_input("Glucemia (mg/dL)", 0, value=95)
            imc = cols[4].number_input("IMC (kg/m²)", 0.0, format="%.1f", value=24.5)

        with st.expander("2. Revisión por Sistemas (Síntomas)"):
            sintomas_cardio = st.multiselect("Cardiovascular", ["Dolor de pecho", "Disnea", "Palpitaciones", "Edema", "Síncope"])
            sintomas_resp = st.multiselect("Respiratorio", ["Tos", "Expectoración", "Sibilancias", "Hemoptisis"])
            sintomas_metabolico = st.multiselect("Metabólico/Endocrino", ["Polidipsia", "Poliuria", "Pérdida de peso", "Intolerancia al frío/calor"])

        with st.expander("3. Factores de Riesgo y Estilo de Vida"):
            c1, c2 = st.columns(2)
            dieta = c1.selectbox("Calidad de la Dieta", ["Saludable (DASH/Mediterránea)", "Regular", "Poco saludable (Procesados)"])
            ejercicio = c2.slider("Ejercicio Aeróbico (min/semana)", 0, 500, 150)

        if st.form_submit_button("Guardar Consulta", use_container_width=True, type="primary"):
            data = {"motivo_consulta": motivo, "presion_sistolica": sistolica, "presion_diastolica": diastolica, "frec_cardiaca": frec_cardiaca, "glucemia": glucemia, "imc": imc, "sintomas_cardio": sintomas_cardio, "sintomas_resp": sintomas_resp, "sintomas_metabolico": sintomas_metabolico, "dieta": dieta, "ejercicio": ejercicio}
            firebase_utils.save_consultation(st.session_state.physician_email, patient_id, data)
            st.rerun()

# ==============================================================================
# MÓDULO 4: CONTROLADOR PRINCIPAL
# ==============================================================================
def main():
    apply_custom_styling()
    if st.session_state.get('logged_in', False): render_main_app()
    else: render_login_page()

if __name__ == "__main__":
    main()

