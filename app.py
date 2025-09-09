# -*- coding: utf-8 -*-
"""
Suite de Diagnóstico Integral
Versión: 21.0 ("Final UI")
Descripción: Versión final que refina la interfaz de usuario moviendo la
sección "Acerca de" desde la página de login a una nueva pestaña dedicada en
el panel de control principal y eliminando la información de versión para
lograr un diseño más limpio y profesional.
"""
# --- LIBRERÍAS ---
import streamlit as st
import pandas as pd
from datetime import datetime, timezone
import firebase_admin
from firebase_admin import credentials, firestore, auth
import google.generativeai as genai
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Suite Clínica Definitiva",
    page_icon="🩺",
    layout="wide"
)

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

# --- INICIALIZACIÓN DEL ESTADO DE LA SESIÓN ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.physician_email = None
    st.session_state.page = 'login'
    st.session_state.selected_patient_id = None
    st.session_state.ai_analysis_running = False
    st.session_state.last_clicked_ai = None

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
def generate_ai_holistic_review(_patient_info, _latest_consultation, _history_summary):
    if not GEMINI_MODEL: return "Servicio de IA no disponible."
    
    prompt = f"""
    **ROL Y OBJETIVO:** Eres un médico especialista en medicina interna y cardiología. Tu objetivo es actuar como un co-piloto para otro médico, analizando los datos de un paciente para generar un reporte clínico estructurado, profesional y accionable.

    **CONTEXTO DEL PACIENTE:**
    - Nombre: {str(_patient_info.get('nombre', 'No especificado'))}
    - Edad: {str(_patient_info.get('edad', 'No especificada'))} años
    
    **DATOS DE LA CONSULTA ACTUAL:**
    - Motivo: {str(_latest_consultation.get('motivo_consulta', 'No especificado'))}
    - Signos Vitales: PA {str(_latest_consultation.get('presion_sistolica', 'N/A'))}/{str(_latest_consultation.get('presion_diastolica', 'N/A'))} mmHg, Glucemia {str(_latest_consultation.get('glucemia', 'N/A'))} mg/dL, IMC {str(_latest_consultation.get('imc', 'N/A'))} kg/m².
    - Síntomas Relevantes: Cardiovascular({str(_latest_consultation.get('sintomas_cardio', []))}), Respiratorio({str(_latest_consultation.get('sintomas_resp', []))}), Metabólico({str(_latest_consultation.get('sintomas_metabolico', []))})

    **RESUMEN DEL HISTORIAL PREVIO:**
    {_history_summary}

    **TAREA: Genera el reporte usando estrictamente el siguiente formato Markdown:**

    ### Análisis Clínico Integral por IA

    **1. RESUMEN DEL CASO:**
    (Presenta un resumen conciso del paciente, su edad, y el motivo de la consulta actual en el contexto de su historial.)

    **2. IMPRESIÓN DIAGNÓSTICA Y DIFERENCIALES:**
    (Basado en la constelación de signos, síntomas y factores de riesgo, ¿cuál es el diagnóstico más probable? Menciona 2 o 3 diagnósticos diferenciales que deberían ser considerados y por qué.)

    **3. ESTRATIFICACIÓN DEL RIESGO:**
    (Evalúa el riesgo cardiovascular y/o metabólico global del paciente. Clasifícalo como BAJO, MODERADO, ALTO o MUY ALTO y justifica tu respuesta basándote en los datos.)

    **4. PLAN DE MANEJO SUGERIDO:**
    - **Estudios Diagnósticos:** (Lista de exámenes de laboratorio o imágenes necesarios para confirmar/descartar los diagnósticos.)
    - **Tratamiento No Farmacológico:** (Recomendaciones clave sobre estilo de vida.)
    - **Tratamiento Farmacológico:** (Sugiere clases de medicamentos a considerar si aplica.)
    - **Metas Terapéuticas:** (Establece objetivos numéricos claros.)

    **5. PUNTOS CLAVE PARA EDUCACIÓN DEL PACIENTE:**
    (Proporciona 3-4 puntos en lenguaje sencillo para que el médico discuta con el paciente.)
    """
    try:
        response = GEMINI_MODEL.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"**Error al generar recomendaciones:** {e}"

# ==============================================================================
# MÓDULO 4: GENERACIÓN DE REPORTES PDF (CON REPORTLAB)
# ==============================================================================
def create_patient_report_pdf(patient_info, history_df):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph(str(patient_info.get('nombre', 'N/A')), styles['h1']))
    story.append(Paragraph(f"Documento: {patient_info.get('cedula', 'N/A')}", styles['Normal']))
    story.append(Paragraph(f"Edad: {patient_info.get('edad', 'N/A')} años", styles['Normal']))
    story.append(Paragraph(f"Dirección: {patient_info.get('direccion', 'N/A')}", styles['Normal']))
    story.append(Spacer(1, 0.25*inch))

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
            story.append(Spacer(1, 0.1*inch))
            story.append(Paragraph("<b>--- Análisis por IA ---</b>", styles['h3']))
            analysis_text = str(row['ai_analysis']).replace('\n', '<br/>').replace('*', '- ')
            story.append(Paragraph(analysis_text, styles['Normal']))
        story.append(Spacer(1, 0.25*inch))
    
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

# ==============================================================================
# MÓDULO 5: VISTAS Y COMPONENTES DE UI
# ==============================================================================
def render_login_page():
    st.title("Plataforma de Gestión Clínica")
    
    # --- CAMBIO: Formulario de login centrado y sin columnas ---
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

def render_main_app():
    with st.sidebar:
        st.header("Menú del Médico")
        st.write(st.session_state.get('physician_email', 'Cargando...'))
        st.divider()
        if st.button("Panel de Control", use_container_width=True):
            st.session_state.page = 'control_panel'
            st.session_state.selected_patient_id = None
            st.rerun()
        st.divider()
        if st.button("Cerrar Sesión", use_container_width=True):
            st.session_state.logged_in = False
            st.rerun()
        
    if st.session_state.page == 'control_panel':
        render_control_panel()
    elif st.session_state.page == 'patient_dashboard':
        render_patient_dashboard()

def render_control_panel():
    st.title("Panel de Control Médico")

    # --- CAMBIO: Nueva pestaña "Acerca de" ---
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
            submitted = st.form_submit_button("Registrar Paciente", use_container_width=True)
            if submitted and nombre and cedula:
                save_new_patient(st.session_state.physician_email, {"nombre": nombre, "cedula": cedula, "edad": edad, "telefono": telefono, "direccion": direccion})
                st.rerun()
        
        st.divider()
        st.header("Seleccionar Paciente Existente")
        patients = get_physician_patients(st.session_state.physician_email)
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

    # --- CAMBIO: Contenido movido a la nueva pestaña ---
    with tab2:
        st.markdown("### Acerca de esta Herramienta")
        st.markdown(
            "Esta es una suite de software diseñada para asistir a profesionales de la salud en el "
            "seguimiento y análisis de pacientes. Utiliza inteligencia artificial para generar "
            "recomendaciones y reportes clínicos, optimizando el flujo de trabajo."
        )
        st.divider()
        st.markdown("##### Autor")
        st.write("**Joseph Javier Sánchez Acuña**")
        st.write("_Ingeniero Industrial, Experto en Inteligencia Artificial y Desarrollo de Software._")
        st.markdown("---")
        st.markdown("##### Contacto")
        st.write("🔗 [Perfil de LinkedIn](https://www.linkedin.com/in/joseph-javier-sánchez-acuña-150410275)")
        st.write("📂 [Repositorio en GitHub](https://github.com/GIUSEPPESAN21)")
        st.write("📧 joseph.sanchez@uniminuto.edu.co")

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
            if st.session_state.ai_analysis_running:
                consultation_id_to_process = st.session_state.last_clicked_ai
                row_to_process = df_history[df_history['id'] == consultation_id_to_process].iloc[0]
                history_summary = "..."
                with st.spinner("Contactando al asistente de IA..."):
                    ai_report = generate_ai_holistic_review(patient_info, row_to_process.to_dict(), history_summary)
                    update_consultation_with_ai_analysis(st.session_state.physician_email, patient_id, consultation_id_to_process, ai_report)
                st.session_state.ai_analysis_running = False
                st.session_state.last_clicked_ai = None
                st.rerun()

            for _, row in df_history.iterrows():
                with st.expander(f"Consulta del {row['timestamp'].strftime('%d/%m/%Y %H:%M')}"):
                    st.write(f"**Motivo:** {row.get('motivo_consulta', 'N/A')}")
                    if 'ai_analysis' in row and pd.notna(row['ai_analysis']):
                        st.markdown(row['ai_analysis'])
                    else:
                        button_key = f"ai_{row['id']}"
                        if st.button("Generar Análisis con IA", key=button_key, disabled=st.session_state.ai_analysis_running):
                            st.session_state.ai_analysis_running = True
                            st.session_state.last_clicked_ai = row['id']
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

