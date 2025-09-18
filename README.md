# Modelo de Tamizaje de Enfermedades - Prototipo Autónomo GEMS
Versión: 5.0.1 (Estable y Unificada)
Desarrollado por: Joseph Sanchez

## Descripción
Este repositorio contiene la versión final, estable y consolidada del prototipo de **herramienta de tamizaje para múltiples perfiles de enfermedades**. La arquitectura ha sido completamente unificada en un solo archivo (`app.py`) para garantizar la máxima compatibilidad, eliminar errores de importación y optimizar el rendimiento en Streamlit Community Cloud.

## 🚀 Demo en Vivo
La aplicación se puede desplegar directamente desde este repositorio en [Streamlit Community Cloud](https://streamlit.io/cloud).

## Arquitectura y Decisiones Finales (v5.0.1)
* **Lógica Totalmente Unificada:** Todo el código (manejo de datos, motor de reglas, conexión a Firebase y explicabilidad) está contenido en `app.py`.
* **Flujo de Usuario Corregido:** Se ha solucionado el error que impedía completar el tamizaje, garantizando que los resultados se muestren correctamente tras enviar el formulario.
* **Interfaz Limpia:** Se ha eliminado el panel lateral (sidebar) para una experiencia de usuario más centrada y directa.
* **Persistencia en Firebase:** Cada evaluación se guarda de forma segura y anónima en Firestore.
* **Gráficos Robustos con Altair:** Se utiliza `altair` para visualizaciones dinámicas y sin errores.

## Cómo Desplegar
1.  **Crea un repositorio en GitHub** y sube los archivos `app.py`, `requirements.txt`, `README.md` y `PRIVACY.md`.
2.  **Conéctalo a Streamlit Cloud** y despliega la aplicación.
3.  **(Recomendado)** Para activar el guardado de datos, configura tus **Secrets** de Streamlit con las credenciales de tu proyecto de Firebase.
