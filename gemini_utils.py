# -*- coding: utf-8 -*-
"""
Módulo de Utilidades de Gemini AI
Descripción: Maneja la conexión con la API de Google Generative AI,
la selección automática de modelos disponibles y la generación de
análisis clínicos a partir de los datos del paciente.
"""
# --- LIBRERÍAS ---
import streamlit as st
import google.generativeai as genai
import logging

# Configuración del logging para monitorear la selección de modelos
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GeminiUtils:
    def __init__(self):
        """
        Inicializa la conexión con la API de Gemini y selecciona un modelo funcional.
        """
        self.api_key = st.secrets.get('gemini_api_key')
        if not self.api_key:
            raise ValueError("La 'gemini_api_key' no fue encontrada en los secretos de Streamlit.")
        
        genai.configure(api_key=self.api_key)
        self.model = self._get_available_model()

    def _get_available_model(self):
        """
        Intenta inicializar modelos de una lista predefinida en orden de preferencia.
        Retorna la primera instancia de modelo que funcione.
        """
        # Lista de modelos actualizada para 2025, de más nuevo a más estable
        model_list = [
            "gemini-flash-latest",      # Alias oficial de Google: siempre apunta al Flash vigente
            "gemini-flash-lite-latest", # Alias oficial: Flash-Lite vigente (fallback)
        ]
        
        for model_name in model_list:
            try:
                model = genai.GenerativeModel(model_name)
                logger.info(f"Éxito: Modelo '{model_name}' inicializado correctamente.")
                # st.toast(f"Modelo IA conectado: {model_name}", icon="🤖")
                return model
            except Exception as e:
                logger.warning(f"Fallo: Modelo '{model_name}' no disponible. Error: {e}")
                continue
        
        logger.error("Error crítico: No se pudo inicializar ningún modelo de Gemini.")
        raise Exception("No se pudo conectar con ningún modelo de IA. Verifique la API Key y la disponibilidad del servicio.")

    @st.cache_data(show_spinner="Generando análisis y recomendaciones con IA...", ttl=300)
    def generate_ai_holistic_review(_self, patient_info, latest_consultation, history_summary):
        """
        Genera un análisis clínico integral utilizando el modelo de IA seleccionado.
        El guion bajo en _self es una convención para que st.cache_data ignore el
        parámetro 'self' del objeto y cachee la función correctamente.
        """
        if not _self.model:
            return "Error: El modelo de IA no está inicializado. No se puede generar el análisis."

        generation_config = {
            "temperature": 0.3,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 4096,
        }
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"},
        ]

        prompt = f"""
        **ROL Y OBJETIVO:** Eres un médico especialista en medicina interna y cardiología. Tu objetivo es actuar como un co-piloto para otro médico, analizando los datos de un paciente para generar un reporte clínico estructurado, profesional y accionable.

        **CONTEXTO DEL PACIENTE:**
        - Nombre: {str(patient_info.get('nombre', 'No especificado'))}
        - Edad: {str(patient_info.get('edad', 'No especificada'))} años
        
        **DATOS DE LA CONSULTA ACTUAL:**
        - Motivo: {str(latest_consultation.get('motivo_consulta', 'No especificado'))}
        - Signos Vitales: PA {str(latest_consultation.get('presion_sistolica', 'N/A'))}/{str(latest_consultation.get('presion_diastolica', 'N/A'))} mmHg, Glucemia {str(latest_consultation.get('glucemia', 'N/A'))} mg/dL, IMC {str(latest_consultation.get('imc', 'N/A'))} kg/m².
        - Síntomas Relevantes: Cardiovascular({str(latest_consultation.get('sintomas_cardio', []))}), Respiratorio({str(latest_consultation.get('sintomas_resp', []))}), Metabólico({str(latest_consultation.get('sintomas_metabolico', []))})

        **RESUMEN DEL HISTORIAL PREVIO:**
        {history_summary}

        **TAREA: Genera el reporte usando estrictamente el siguiente formato Markdown:**

        ### Análisis Clínico Integral por IA
        **1. RESUMEN DEL CASO:**
        (Presenta un resumen conciso del paciente, su edad, y el motivo de la consulta actual en el contexto de su historial.)
        **2. IMPRESIÓN DIAGNÓSTICA Y DIFERENCIALES:**
        (Basado en la constelación de signos, síntomas y factores de riesgo, ¿cuál es el diagnóstico más probable? Menciona 2 o 3 diagnósticos diferenciales.)
        **3. ESTRATIFICACIÓN DEL RIESGO:**
        (Evalúa el riesgo cardiovascular y/o metabólico global del paciente. Clasifícalo como BAJO, MODERADO, ALTO o MUY ALTO y justifica.)
        **4. PLAN DE MANEJO SUGERIDO:**
        - **Estudios Diagnósticos:** (Lista de exámenes necesarios.)
        - **Tratamiento No Farmacológico:** (Recomendaciones clave sobre estilo de vida.)
        - **Tratamiento Farmacológico:** (Sugiere clases de medicamentos.)
        - **Metas Terapéuticas:** (Establece objetivos numéricos claros.)
        **5. PUNTOS CLAVE PARA EDUCACIÓN DEL PACIENTE:**
        (Proporciona 3-4 puntos en lenguaje sencillo.)
        """
        
        try:
            response = _self.model.generate_content(
                prompt,
                generation_config=generation_config,
                safety_settings=safety_settings
            )
            return response.text
        except Exception as e:
            logger.error(f"Error al generar contenido con la IA: {e}")
            return f"""
            **Error al contactar al asistente de IA.**
            **Detalle:** {str(e)}
            
            **Posibles Causas:**
            1.  **Contenido Bloqueado:** La consulta puede haber activado un filtro de seguridad.
            2.  **Problemas de Red:** Falla en la comunicación con los servidores de Google AI.
            3.  **Sobrecarga del Servicio:** El servicio de IA puede estar experimentando alta demanda.
            
            Por favor, inténtelo de nuevo más tarde o modifique la consulta.
            """
