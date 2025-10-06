# -*- coding: utf-8 -*-
"""
Módulo de Utilidades de Firebase
Descripción: Centraliza toda la lógica para interactuar con Firestore,
incluyendo la inicialización de la conexión y las operaciones CRUD
(Crear, Leer, Actualizar, Borrar) para los datos de médicos y pacientes.
"""
# --- LIBRERÍAS ---
import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timezone
import pandas as pd

# --- CONEXIÓN INICIAL ---
@st.cache_resource
def init_firebase():
    """Inicializa y retorna el cliente de la base de datos Firestore."""
    try:
        creds_dict = dict(st.secrets["firebase_credentials"])
        creds_dict['private_key'] = creds_dict['private_key'].replace('\\n', '\n')
        if not firebase_admin._apps:
            creds = credentials.Certificate(creds_dict)
            firebase_admin.initialize_app(creds)
        db_client = firestore.client()
        return db_client
    except Exception as e:
        st.error(f"Error crítico al conectar con Firebase: {e}", icon="🔥")
        return None

DB = init_firebase()

# --- FUNCIONES DE PACIENTES ---
def get_physician_patients(physician_email):
    """Obtiene una lista de todos los pacientes asociados a un médico."""
    if not DB: return []
    patients_ref = DB.collection('physicians').document(physician_email).collection('patients').stream()
    return [{'id': doc.id, **doc.to_dict()} for doc in patients_ref]

def get_patient_details(physician_email, patient_id):
    """
    [FUNCIÓN CORREGIDA] Obtiene los detalles de un paciente específico.
    Soluciona el error AttributeError.
    """
    if not DB: return {}
    try:
        patient_ref = DB.collection('physicians').document(physician_email).collection('patients').document(patient_id)
        patient_doc = patient_ref.get()
        if patient_doc.exists:
            return patient_doc.to_dict()
        else:
            st.warning("No se encontró el documento del paciente.")
            return {}
    except Exception as e:
        st.error(f"No se pudieron cargar los datos del paciente: {e}")
        return {}

def save_new_patient(physician_email, patient_data):
    """Guarda un nuevo paciente en la base de datos."""
    if not DB: return
    DB.collection('physicians').document(physician_email).collection('patients').document(patient_data['cedula']).set(patient_data)
    st.success(f"Paciente {patient_data['nombre']} registrado exitosamente.")

# --- FUNCIONES DE CONSULTAS ---
def save_consultation(physician_email, patient_id, consultation_data):
    """Guarda una nueva consulta para un paciente."""
    if not DB: return None
    timestamp = datetime.now(timezone.utc)
    doc_id = timestamp.strftime('%Y-%m-%d_%H-%M-%S')
    consultation_data['timestamp_utc'] = timestamp.isoformat()
    clean_data = {k: v for k, v in consultation_data.items() if v is not None and v != ''}
    DB.collection('physicians').document(physician_email).collection('patients').document(patient_id).collection('consultations').document(doc_id).set(clean_data)
    st.toast("Consulta guardada.", icon="✅")
    return doc_id

def update_consultation_with_ai_analysis(physician_email, patient_id, consultation_id, ai_report):
    """Actualiza una consulta existente con el análisis de la IA."""
    if not DB: return
    consultation_ref = DB.collection('physicians').document(physician_email).collection('patients').document(patient_id).collection('consultations').document(consultation_id)
    consultation_ref.update({"ai_analysis": ai_report})
    st.toast("Análisis de IA guardado en el historial.", icon="🧠")

def load_patient_history(physician_email, patient_id):
    """Carga el historial completo de consultas de un paciente."""
    if not DB: return pd.DataFrame()
    consultations_ref = DB.collection('physicians').document(physician_email).collection('patients').document(patient_id).collection('consultations').order_by('timestamp_utc', direction=firestore.Query.DESCENDING).stream()
    records = []
    for doc in consultations_ref:
        record = doc.to_dict()
        record['id'] = doc.id
        records.append(record)
    if not records: return pd.DataFrame()
    df = pd.DataFrame(records)
    df['timestamp'] = pd.to_datetime(df['timestamp_utc'], errors='coerce')
    return df

