# Política de Privacidad y Manejo de Datos
Última actualización: 18 de septiembre de 2025

Este documento describe las prácticas de privacidad para el prototipo del "Modelo de Tamizaje de Enfermedades".

## 1. Compromiso con la Privacidad
La confidencialidad y seguridad de los datos de salud son nuestra máxima prioridad. Este sistema ha sido diseñado para minimizar la recolección de datos personales y maximizar la seguridad, en línea con normativas como la Ley 1581 de 2012 de Colombia (Habeas Data).

## 2. Recolección y Uso de Datos
La plataforma recolecta únicamente los datos clínicos y demográficos anónimos necesarios para el funcionamiento del modelo de tamizaje. **NO se solicita ni almacena ninguna Información de Identificación Personal (PII)** como nombres, cédulas o correos.

## 3. Proceso de Pseudonimización Irreversible
Para garantizar el anonimato, se genera un `patient_id` único aplicando un hash criptográfico (SHA-256) a una combinación de los datos clínicos. Este proceso es irreversible y solo sirve para agrupar registros de un mismo perfil anónimo.

## 4. Seguridad de la Base de Datos (Firebase Firestore)
La conexión a la base de datos se realiza a través de credenciales seguras, gestionadas exclusivamente a través del sistema de "Secrets" de Streamlit Cloud, garantizando que nunca son expuestas en el código público.

## 5. Consentimiento Informado
La plataforma requiere que el usuario acepte explícitamente estos términos antes de poder enviar cualquier dato.

**Advertencia:** Este sistema es una herramienta de apoyo y tamizaje. **No sustituye, bajo ninguna circunstancia, un diagnóstico o consulta médica profesional.**
