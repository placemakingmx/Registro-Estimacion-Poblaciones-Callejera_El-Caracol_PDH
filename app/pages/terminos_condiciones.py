import streamlit as st

st.set_page_config(
    page_title="Terminos y Condiciones",
    page_icon="",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.title("Terminos y Condiciones de Uso de Datos")

st.markdown(
    """
## Informacion y Privacidad del Estudio

Este registro forma parte de un estudio academico realizado por el Programa de Derechos
Humanos de la Universidad Iberoamericana en colaboracion con El Caracol A.C., con el
objetivo de documentar y visibilizar la situacion de las personas en calle en la Ciudad de Mexico.

### Uso de tus datos personales

- Confidencialidad: Todos los datos que proporciones (nombre, edad, fecha de nacimiento, etc.)
  seran tratados de manera estrictamente confidencial.
- No divulgacion: Tu informacion personal NO sera compartida, publicada ni divulgada fuera
  del equipo de investigacion.
- Acceso restringido: Solo tendran acceso a tus datos las personas autorizadas del PDH
  Iberoamericana y El Caracol A.C. que participan en este estudio.

### Uso de fotografias

- Proposito: Las fotografias se toman unicamente como evidencia documental de las entrevistas
  realizadas en campo.
- Almacenamiento seguro: Las imagenes se guardan en un sistema protegido y NO seran
  publicadas, compartidas ni utilizadas para ningun otro fin fuera del estudio.
- Privacidad: Tu rostro e identidad estaran protegidos. Las fotos NO se entregaran a ninguna
  institucion gubernamental, medios de comunicacion ni terceros ajenos al estudio.

### Generacion de ID unico

Se te asignara un codigo de identificacion unico (ID) generado con informacion basica
(genero, iniciales, fecha de nacimiento) para proteger tu identidad al analizar los datos.

### Tu consentimiento

Al aceptar participar en esta entrevista, otorgas tu consentimiento libre e informado para:

- El registro de tus datos personales con fines academicos.
- La toma de fotografias como evidencia del trabajo de campo.
- El uso confidencial de esta informacion por parte del equipo de investigacion.

### Tus derechos

En cualquier momento puedes:

- Solicitar informacion sobre los datos que tenemos de ti.
- Solicitar correccion de tus datos si hay errores.
- Negarte a participar sin ninguna consecuencia.

Tu participacion es voluntaria y tu privacidad esta garantizada.

Para cualquier duda, contacta a El Caracol A.C.

Rafael Heliodoro Valle 333, Col. Lorenzo Boturini, Alcaldia Venustiano Carranza, CDMX

Ultima actualizacion: Marzo 2025
"""
)
