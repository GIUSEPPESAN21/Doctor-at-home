# -*- coding: utf-8 -*-
"""
Suite de Diagnóstico Integral - Aplicación Principal
Versión: 28.0 ("Vibrant Dark-Mode Palette & UI Tweaks")
Descripción: Paleta de colores renovada a un índigo vibrante.
Soporte completo para modo oscuro nativo de Streamlit.
Logo movido al pie en login y título de CEO añadido en "Acerca de".
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

# --- MÓdulos PERSONALIZADOS ---
import firebase_utils
from gemini_utils import GeminiUtils

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="SaludIA: Asistente Clínico",
    page_icon="https://github.com/GIUSEPPESAN21/sava-assets/blob/main/logo_sava.png?raw=true", # <-- Icono de pestaña actualizado
    layout="wide"
)

# --- CONSTANTES ---
LOGO_URL = "https://github.com/GIUSEPPESAN21/sava-assets/blob/main/logo_sava.png?raw=true"

# ==============================================================================
# MÓDULO 1: ESTILOS Y CONFIGURACIÓN INICIAL
# ==============================================================================
def apply_custom_styling():
    """Inyecta CSS personalizado para una interfaz de usuario mejorada."""
    custom_css = """
    <style>
        /* --- Importar Fuente Profesional --- */
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&display=swap');
    
        /* --- NUEVA PALETA: Vibrante y compatible con Dark Mode --- */
        :root {
            --primary-color: #4F46E5; /* Índigo vibrante */
            --primary-hover: #4338CA;
            --success-color: #10B981; /* Esmeralda */
            --success-hover: #059669;
            /* Se eliminan: --background-color, --text-color, --card-bg-color, --border-color */
            /* Se deja que Streamlit maneje los fondos y texto para Light/Dark mode */
            --shadow-color: rgba(0, 0, 0, 0.08); /* Sombra más sutil */
        }

        /* --- Estilo General --- */
        .stApp {
            /* Se elimina background-color y color para respetar el tema */
            font-family: 'Poppins', sans-serif; /* <-- FUENTE APLICADA */
        }
        
        /* --- Animación de Entrada --- */
        @keyframes fadeInUp {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .main > div {
            animation: fadeInUp 0.5s ease-out forwards;
        }

        /* --- Estilo de Títulos --- */
        h1, h2, h3 {
            color: var(--primary-color);
            font-weight: 700; 
        }
        h4, h5, h6 {
            font-weight: 600;
        }
        
        /* --- Estilo de Botones (Sin cambios, ya usan --primary-color) --- */
        div[data-testid="stButton"] > button {
            border-radius: 8px;
            padding: 10px 18px;
            font-weight: 600;
            border: none;
            box-shadow: 0 1px 3px var(--shadow-color);
            transition: all 0.2s ease;
        }
        div[data-testid="stButton"] > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 8px var(--shadow-color);
        }
        div[data-testid="stButton"] > button[kind="primary"] {
            background-color: var(--success-color);
            color: white;
        }
        div[data-testid="stButton"] > button[kind="primary"]:hover {
            background-color: var(--success-hover);
        }
        div[data-testid="stButton"] > button[kind="secondary"] {
            /* Usa variables de tema para compatibilidad dark/light */
            background-color: var(--secondary-background-color); 
            color: var(--primary-color);
            border: 1px solid var(--primary-color);
        }
         div[data-testid="stButton"] > button[kind="secondary"]:hover {
            background-color: var(--primary-color);
            color: white;
        }
        
        /* --- Estilo de Contenedores y Tarjetas (MODIFICADO para Dark Mode) --- */
        [data-testid="stVerticalBlock"] [data-testid="stVerticalBlock"] [data-testid="stVerticalBlockBorderWrapper"] {
            background-color: var(--secondary-background-color); /* <-- Variable de Tema */
            border-radius: 12px;
            border: 1px solid transparent; /* <-- Borde sutil */
            box-shadow: 0 2px 6px var(--shadow-color);
            padding: 1.2em;
            border-top: 4px solid var(--primary-color);
        }
        
        /* --- Estilo de Pestañas (Tabs) (MODIFICADO para Dark Mode) --- */
        button[data-baseweb="tab"][aria-selected="true"] {
            background-color: var(--secondary-background-color) !important; /* <-- Variable de Tema */
            border-bottom-color: var(--primary-color) !important;
            color: var(--primary-color) !important;
            font-weight: 600;
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
# ... (existing code) ...
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
# ... (existing code) ...
    text = text.replace('\n', '<br/>')
    return text

def create_patient_report_pdf(patient_info, history_df):
# ... (existing code) ...
    doc = SimpleDocTemplate(buffer, pagesize=(8.5 * inch, 11 * inch))
    styles = getSampleStyleSheet()
# ... (existing code) ...
    story.append(Paragraph(f"Reporte Clínico de {str(patient_info.get('nombre', 'N/A'))}", styles['h1']))
# ... (existing code) ...
    story.append(Paragraph(f"Edad: {patient_info.get('edad', 'N/A')} años", styles['Normal']))
    story.append(Spacer(1, 0.25 * inch))

# ... (existing code) ...
    for _, row in history_df.sort_values('timestamp').iterrows():
        story.append(Paragraph(f"Consulta del {row['timestamp'].strftime('%d de %B, %Y')}", styles['h2']))
# ... (existing code) ...
        story.append(Paragraph(f"<b>Motivo:</b> {motivo}", styles['Normal']))
        pa_s = str(row.get('presion_sistolica', 'N/A'))
# ... (existing code) ...
        story.append(Paragraph(f"<b>Signos Vitales:</b> PA: {pa_s}/{pa_d} mmHg", styles['Normal']))
        
        if 'ai_analysis' in row and pd.notna(row['ai_analysis']):
# ... (existing code) ...
            story.append(Paragraph("<b>--- Análisis por IA (SaludIA) ---</b>", styles['Normal']))
            raw_text = str(row['ai_analysis'])
# ... (existing code) ...
            analysis_text = clean_html_for_reportlab(raw_text)
            try:
# ... (existing code) ...
                story.append(Paragraph(analysis_text, styles['Normal']))
            except Exception as e:
# ... (existing code) ...
                story.append(Paragraph(f"Error al renderizar análisis: {e}", styles['Normal']))
        story.append(Spacer(1, 0.25 * inch))
# ... (existing code) ...
    doc.build(story)
    buffer.seek(0)
# ... (existing code) ...
    return buffer.getvalue()

# ==============================================================================
# MÓDULO 3: VISTAS Y COMPONENTES DE UI (Sección "Acerca de" actualizada)
# ==============================================================================
def render_login_page():
    # --- MODIFICADO: Título añadido, Logo movido al final ---
    st.markdown("<h1 style='text-align: center; color: var(--primary-color);'>Bienvenido a SaludIA</h1>", unsafe_allow_html=True)
    st.markdown("<h4 style='text-align: center; color: var(--text-color);'>Tu Asistente Clínico Inteligente</h4>", unsafe_allow_html=True)
    st.markdown("---")
    
    _, col2, _ = st.columns([1, 1.5, 1])
# ... (existing code) ...
        with st.container(border=True):
            login_tab, register_tab = st.tabs(["**Iniciar Sesión**", "**Registrarse**"])
# ... (existing code) ...
            with login_tab:
                with st.form("login_form"):
# ... (existing code) ...
                    email = st.text_input("Correo Electrónico del Médico", key="login_email")
                    password = st.text_input("Contraseña", type="password", key="login_password")
# ... (existing code) ...
                    login_button = st.form_submit_button("Acceder a la Plataforma", use_container_width=True, type="primary")
                    if login_button:
# ... (existing code) ...
                        try:
                            user = auth.get_user_by_email(email)
# ... (existing code) ...
                            st.session_state.logged_in = True
                            st.session_state.physician_email = user.email
# ... (existing code) ...
                            st.session_state.page = 'control_panel'
                            st.rerun()
# ... (existing code) ...
                        except Exception: st.error("Error: Verifique sus credenciales.")
            with register_tab:
# ... (existing code) ...
                with st.form("register_form"):
                    new_email = st.text_input("Correo para Registro", key="register_email")
# ... (existing code) ...
                    new_password = st.text_input("Crear Contraseña", type="password", key="register_password")
                    confirm_password = st.text_input("Confirmar Contraseña", type="password", key="confirm_password")
# ... (existing code) ...
                    register_button = st.form_submit_button("Crear Cuenta", use_container_width=True)
                    if register_button:
# ... (existing code) ...
                        if new_password == confirm_password:
                            try:
# ... (existing code) ...
                                user = auth.create_user(email=new_email, password=new_password)
                                st.success(f"¡Cuenta para {user.email} creada! Ya puede iniciar sesión.")
# ... (existing code) ...
                                st.balloons()
                            except Exception as e: st.error(f"Error de registro: {e}")
# ... (existing code) ...
                        else: st.error("Las contraseñas no coinciden.")

    # --- MODIFICADO: Logo movido al final, más pequeño y sutil ---
    st.markdown(
        f"""
        <div style="display: flex; justify-content: center; margin-top: 40px; opacity: 0.7;">
            <img src="{LOGO_URL}" alt="SAVA Logo" style="width: 150px;">
        </div>
        """, 
        unsafe_allow_html=True
    )

def render_header():
# ... (existing code) ...
    with st.container(border=True):
        col1, col2, col3 = st.columns([4, 1.5, 1.5])
# ... (existing code) ...
        with col1:
            # --- Logo y Email alineados (Sin cambios) ---
            st.markdown(
# ... (existing code) ...
                f"""
                <div style="display: flex; align-items: center; gap: 15px; height: 100%; min-height: 40px;">
                    <img src="{LOGO_URL}" alt="SAVA Logo" style="height: 40px;">
                    <span style="font-weight: 600; font-size: 1.1em; color: var(--text-color);">
# ... (existing code) ...
                        👨‍⚕️ {st.session_state.get('physician_email', 'Cargando...')}
                    </span>
                </div>
# ... (existing code) ...
                """,
                unsafe_allow_html=True
            )
# ... (existing code) ...
        with col2:
            if st.button("Panel de Control", use_container_width=True):
# ... (existing code) ...
                st.session_state.page = 'control_panel'; st.session_state.selected_patient_id = None; st.rerun()
        with col3:
# ... (existing code) ...
            if st.button("Cerrar Sesión", use_container_width=True, type="secondary"):
                for key in list(st.session_state.keys()): del st.session_state[key]
# ... (existing code) ...
                st.rerun()
    st.markdown("<br>", unsafe_allow_html=True)
# ... (existing code) ...

def render_main_app():
    render_header()
# ... (existing code) ...
    if st.session_state.page == 'control_panel': render_control_panel()
    elif st.session_state.page == 'patient_dashboard': render_patient_dashboard()
# ... (existing code) ...

def render_control_panel():
    st.title("Panel de Control de SaludIA")
# ... (existing code) ...
    tab1, tab2 = st.tabs(["✍️ Gestión de Pacientes", "👥 Acerca de"])
    with tab1:
# ... (existing code) ...
        st.header("Registrar Nuevo Paciente")
        with st.form("new_patient_form", clear_on_submit=True):
# ... (existing code) ...
            cols = st.columns(3)
            nombre = cols[0].text_input("Nombres Completos")
# ... (existing code) ...
            cedula = cols[1].text_input("Documento de Identidad (ID único)")
            edad = cols[2].number_input("Edad", 0, 120)
# ... (existing code) ...
            direccion, telefono = st.columns(2)
            direccion = direccion.text_input("Dirección de Residencia")
# ... (existing code) ...
            telefono = telefono.text_input("Teléfono")
            if st.form_submit_button("Registrar Paciente", use_container_width=True, type="primary"):
# ... (existing code) ...
                if nombre and cedula:
                    firebase_utils.save_new_patient(st.session_state.physician_email, {"nombre": nombre, "cedula": cedula, "edad": edad, "telefono": telefono, "direccion": direccion})
# ... (existing code) ...
                    st.rerun()
        st.divider()
# ... (existing code) ...
        st.header("Seleccionar Paciente Existente")
        patients = firebase_utils.get_physician_patients(st.session_state.physician_email)
# ... (existing code) ...
        if not patients: st.info("No hay pacientes registrados.")
        else:
# ... (existing code) ...
            for patient in patients:
                with st.container(border=True):
# ... (existing code) ...
                    col1, col2 = st.columns([3, 1])
                    with col1:
# ... (existing code) ...
                        st.subheader(patient['nombre'])
                        st.caption(f"ID: {patient['cedula']} | Edad: {patient.get('edad', 'N/A')} años")
# ... (existing code) ...
                    if col2.button("Ver Historial", key=patient['id'], use_container_width=True, type="primary"):
                        st.session_state.selected_patient_id = patient['id']
# ... (existing code) ...
                        st.session_state.page = 'patient_dashboard'
                        st.rerun()
# ... (existing code) ...
    
    # [MODIFICADO] Sección "Acerca de" actualizada con título de CEO
    with tab2:
# ... (existing code) ...
        st.header("👥 Sobre el Proyecto y su Creador")
        with st.container(border=True):
# ... (existing code) ...
            col_img, col_info = st.columns([1, 3])
            with col_img:
                # --- MODIFICADO: Título de CEO añadido ---
                st.image(LOGO_URL)
                st.caption("Joseph Javier Sánchez Acuña")
                st.caption("**CEO de SAVA**")
            with col_info:
# ... (existing code) ...
                st.title("Joseph Javier Sánchez Acuña")
                st.subheader("_Estudiante de Ingeniería Industrial_")
# ... (existing code) ...
                st.subheader("_Experto en Inteligencia Artificial y Desarrollo de Software._")
                st.markdown(
# ... (existing code) ...
                    """
                    - 🔗 **LinkedIn:** [joseph-javier-sánchez-acuña](https://www.linkedin.com/in/joseph-javier-sánchez-acuña-150410275)
                    - 📂 **GitHub:** [GIUSEPPESAN21](https://github.com/GIUSEPPESAN21)
# ... (existing code) ...
                    - 📧 **Email:** [joseph.sanchez@uniminuto.edu.co](mailto:joseph.sanchez@uniminuto.edu.co)
                    """
                )
# ... (existing code) ...

def render_patient_dashboard():
    patient_id = st.session_state.selected_patient_id
# ... (existing code) ...
    patient_info = firebase_utils.get_patient_details(st.session_state.physician_email, patient_id)
    st.title(f"Dashboard del Paciente: {patient_info.get('nombre', 'N/A')}")
# ... (existing code) ...
    st.caption(f"Documento: {patient_info.get('cedula', 'N/A')} | Edad: {patient_info.get('edad', 'N/A')} años")
    df_history = firebase_utils.load_patient_history(st.session_state.physician_email, patient_id)
# ... (existing code) ...
    if not df_history.empty:
        pdf_data = create_patient_report_pdf(patient_info, df_history)
# ... (existing code) ...
        st.download_button("📄 Descargar Reporte Completo", data=pdf_data, file_name=f"Reporte_{patient_info.get('cedula')}.pdf", mime="application/pdf")
    
    tab1, tab2 = st.tabs(["📈 Historial", "✍️ Nueva Consulta"])
# ... (existing code) ...
    with tab1:
        if df_history.empty: st.info("Este paciente no tiene consultas registradas.")
# ... (existing code) ...
        else:
            if st.session_state.ai_analysis_running:
# ... (existing code) ...
                consultation_id = st.session_state.last_clicked_ai
                row = df_history[df_history['id'] == consultation_id].iloc[0]
# ... (existing code) ...
                history_summary = "Resumen del historial médico previo relevante."
                ai_report = GEMINI.generate_ai_holistic_review(patient_info, row.to_dict(), history_summary)
# ... (existing code) ...
                firebase_utils.update_consultation_with_ai_analysis(st.session_state.physician_email, patient_id, consultation_id, ai_report)
                st.session_state.ai_analysis_running = False; st.session_state.last_clicked_ai = None; st.rerun()
# ... (existing code) ...
            
            for _, row in df_history.iterrows():
# ... (existing code) ...
                with st.expander(f"Consulta del {row['timestamp'].strftime('%d/%m/%Y %H:%M')}"):
                    st.write(f"**Motivo:** {row.get('motivo_consulta', 'N/A')}")
# ... (existing code) ...
                    if 'ai_analysis' in row and pd.notna(row['ai_analysis']):
                        st.markdown("---"); st.markdown(row['ai_analysis'])
# ... (existing code) ...
                    elif st.button("Generar Análisis con IA", key=f"ai_{row['id']}", disabled=st.session_state.ai_analysis_running or not IS_MODEL_CONFIGURED):
                        st.session_state.ai_analysis_running = True; st.session_state.last_clicked_ai = row['id']; st.rerun()
# ... (existing code) ...
    with tab2:
        render_new_consultation_form(patient_id)
# ... (existing code) ...

def render_new_consultation_form(patient_id):
    with st.form("new_consultation_form"):
# ... (existing code) ...
        st.header("Datos de la Consulta")
        with st.expander("1. Anamnesis y Vitales", expanded=True):
# ... (existing code) ...
            motivo = st.text_area("Motivo de Consulta y Notas")
            cols = st.columns(5)
# ... (existing code) ...
            sistolica = cols[0].number_input("PA Sistólica", 0, value=120)
            diastolica = cols[1].number_input("PA Diastólica", 0, value=80)
# ... (existing code) ...
            frec_cardiaca = cols[2].number_input("Frec. Cardíaca", 0, value=70)
            glucemia = cols[3].number_input("Glucemia (mg/dL)", 0, value=95)
# ... (existing code) ...
            imc = cols[4].number_input("IMC (kg/m²)", 0.0, format="%.1f", value=24.5)

        with st.expander("2. Revisión por Sistemas (Síntomas)"):
# ... (existing code) ...
            sintomas_cardio = st.multiselect("Cardiovascular", ["Dolor de pecho", "Disnea", "Palpitaciones", "Edema", "Síncope"])
            sintomas_resp = st.multiselect("Respiratorio", ["Tos", "Expectoración", "Sibilancias", "Hemoptisis"])
# ... (existing code) ...
            sintomas_metabolico = st.multiselect("Metabólico/Endocrino", ["Polidipsia", "Poliuria", "Pérdida de peso", "Intolerancia al frío/calor"])

        with st.expander("3. Factores de Riesgo y Estilo de Vida"):
# ... (existing code) ...
            c1, c2 = st.columns(2)
            dieta = c1.selectbox("Calidad de la Dieta", ["Saludable (DASH/Mediterránea)", "Regular", "Poco saludable (Procesados)"])
# ... (existing code) ...
            ejercicio = c2.slider("Ejercicio Aeróbico (min/semana)", 0, 500, 150)

        if st.form_submit_button("Guardar Consulta", use_container_width=True, type="primary"):
# ... (existing code) ...
            data = {"motivo_consulta": motivo, "presion_sistolica": sistolica, "presion_diastolica": diastolica, "frec_cardiaca": frec_cardiaca, "glucemia": glucemia, "imc": imc, "sintomas_cardio": sintomas_cardio, "sintomas_resp": sintomas_resp, "sintomas_metabolico": sintomas_metabolico, "dieta": dieta, "ejercicio": ejercicio}
            firebase_utils.save_consultation(st.session_state.physician_email, patient_id, data)
# ... (existing code) ...
            st.rerun()

# ==============================================================================
# MÓDULO 4: CONTROLADOR PRINCIPAL
# ==============================================================================
# ... (existing code) ...
def main():
    apply_custom_styling()
# ... (existing code) ...
    if st.session_state.get('logged_in', False): render_main_app()
    else: render_login_page()
# ... (existing code) ...

if __name__ == "__main__":
    main()
# ... (existing code) ...

