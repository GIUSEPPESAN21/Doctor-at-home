# -*- coding: utf-8 -*-
"""
Módulo de Utilidades de Firebase
Descripción: Centraliza todas las interacciones con Firestore, como la inicialización
de la conexión y las operaciones CRUD (Crear, Leer, Actualizar, Borrar) para
pacientes y consultas.
"""
# --- LIBRERÍAS ---
import streamlit as st
import pandas as pd
from datetime import datetime, timezone
import firebase_admin
from firebase_admin import credentials, firestore, auth

# ==============================================================================
# MÓDULO 1: CONEXIÓN Y CONFIGURACIÓN
# ==============================================================================
@st.cache_resource
def init_firebase():
    """
    Inicializa la conexión con Firebase usando credenciales de Streamlit secrets.
    Retorna el cliente de Firestore.
    """
    try:
        creds_dict = dict(st.secrets["firebase_credentials"])
        # Corrige el formato de la clave privada leída desde secrets
        creds_dict['private_key'] = creds_dict['private_key'].replace('\\n', '\n')
        
        # Inicializa la app de Firebase solo si no existe una ya
        if not firebase_admin._apps:
            creds = credentials.Certificate(creds_dict)
            firebase_admin.initialize_app(creds)
        
        return firestore.client()
    except Exception as e:
        st.error(f"Error crítico al conectar con Firebase: {e}", icon="🔥")
        return None

# Inicializa el cliente de la base de datos para ser usado en este módulo
DB = init_firebase()

# ==============================================================================
# MÓDULO 2: OPERACIONES CON DATOS (FIRESTORE)
# ==============================================================================
def get_physician_patients(physician_email):
    """Obtiene la lista de pacientes asociados a un médico."""
    if not DB: return []
    try:
        patients_ref = DB.collection('physicians').document(physician_email).collection('patients').stream()
        return [{'id': doc.id, **doc.to_dict()} for doc in patients_ref]
    except Exception as e:
        st.error(f"Error al obtener pacientes: {e}")
        return []

def save_new_patient(physician_email, patient_data):
    """Guarda un nuevo paciente en la base de datos."""
    if not DB: return
    try:
        DB.collection('physicians').document(physician_email).collection('patients').document(patient_data['cedula']).set(patient_data)
        st.success(f"Paciente {patient_data['nombre']} registrado exitosamente.")
    except Exception as e:
        st.error(f"Error al guardar paciente: {e}")


def save_consultation(physician_email, patient_id, consultation_data):
    """Guarda una nueva consulta para un paciente."""
    if not DB: return None
    try:
        timestamp = datetime.now(timezone.utc)
        doc_id = timestamp.strftime('%Y-%m-%d_%H-%M-%S')
        consultation_data['timestamp_utc'] = timestamp.isoformat()
        # Limpia datos nulos o vacíos antes de guardar
        clean_data = {k: v for k, v in consultation_data.items() if v is not None and v != ''}
        DB.collection('physicians').document(physician_email).collection('patients').document(patient_id).collection('consultations').document(doc_id).set(clean_data)
        st.toast("Consulta guardada.", icon="✅")
        return doc_id
    except Exception as e:
        st.error(f"Error al guardar consulta: {e}")
        return None

def update_consultation_with_ai_analysis(physician_email, patient_id, consultation_id, ai_report):
    """Actualiza una consulta existente con el análisis de la IA."""
    if not DB: return
    try:
        consultation_ref = DB.collection('physicians').document(physician_email).collection('patients').document(patient_id).collection('consultations').document(consultation_id)
        consultation_ref.update({"ai_analysis": ai_report})
        st.toast("Análisis de IA guardado en el historial.", icon="🧠")
    except Exception as e:
        st.error(f"Error al actualizar con análisis de IA: {e}")

def load_patient_history(physician_email, patient_id):
    """Carga el historial de consultas de un paciente y lo retorna como DataFrame."""
    if not DB: return pd.DataFrame()
    try:
        consultations_ref = DB.collection('physicians').document(physician_email).collection('patients').document(patient_id).collection('consultations').order_by('timestamp_utc', direction=firestore.Query.DESCENDING).stream()
        records = [dict(id=doc.id, **doc.to_dict()) for doc in consultations_ref]
        
        if not records: return pd.DataFrame()
        
        df = pd.DataFrame(records)
        df['timestamp'] = pd.to_datetime(df['timestamp_utc'])
        return df
    except Exception as e:
        st.error(f"Error al cargar historial: {e}")
        return pd.DataFrame()
