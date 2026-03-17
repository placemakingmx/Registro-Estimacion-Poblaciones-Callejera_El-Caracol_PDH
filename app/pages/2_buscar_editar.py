import streamlit as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.sheets_handler import buscar_en_sheets, obtener_registro_completo
from utils.connectivity import verificar_conexion, banner_sin_conexion

st.set_page_config(
    page_title="Buscar y Editar",
    page_icon="",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Verificar login
if not st.session_state.get("logged_in", False):
    st.error("Debes iniciar sesión primero")
    st.stop()


def _header_seguro() -> None:
    """Intenta usar header_sesion desde Inicio y hace fallback local si falla."""
    try:
        from main import header_sesion

        header_sesion()
    except Exception:
        st.markdown(
            f"""
            <div style='background-color: #1E3A8A; padding: 10px; border-radius: 5px; color: white;'>
                <strong>{st.session_state.get('entrevistador_nombre', 'Entrevistador/a')}</strong> |
                ID: {st.session_state.get('entrevistador_id', '-') } |
                Ruta: {st.session_state.get('ruta_id', '-')}
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("---")


_header_seguro()

st.title("Buscar y Editar Registros")

# Verificar conexion
tiene_conexion = verificar_conexion()
if not tiene_conexion:
    banner_sin_conexion()
    st.warning("La busqueda requiere conexion a internet")
    st.stop()

# Busqueda
st.subheader("Buscar Registro")

col1, col2 = st.columns([3, 1])
with col1:
    termino_busqueda = st.text_input(
        "Buscar por ID, nombre o alias",
        placeholder="Ej: P3K9M2L, Juan, El Coyote",
        help="Busqueda parcial - encuentra coincidencias en cualquier parte del texto",
    )

with col2:
    buscar_btn = st.button("Buscar", use_container_width=True, type="primary")

if buscar_btn and termino_busqueda:
    with st.spinner("Buscando..."):
        resultados = buscar_en_sheets(termino_busqueda)

        if not resultados:
            st.info("No se encontraron resultados")
        elif len(resultados) == 1:
            # Un solo resultado: ir directo a edicion
            st.session_state.registro_seleccionado = resultados[0]
            st.session_state.modo_edicion = True
        else:
            # Multiples resultados: mostrar cards
            st.success(f"Se encontraron {len(resultados)} resultado(s)")

            for i, registro in enumerate(resultados):
                timestamp = str(registro.get("Timestamp", ""))
                fecha_txt = timestamp[:10] if timestamp else "-"
                with st.expander(
                    f"**{registro.get('ID_Persona', '-')}** - {registro.get('Nombre_Alias', '-')} | "
                    f"{registro.get('Edad', '-')} años | {registro.get('Género', '-')} | "
                    f"Registrado: {fecha_txt}"
                ):
                    c1, c2, c3 = st.columns(3)

                    with c1:
                        st.metric("Edad", registro.get("Edad", "-"))
                        st.metric("Género", registro.get("Género", "-"))
                    with c2:
                        st.metric("Años en calle", registro.get("Años_Calle", "-"))
                        st.metric("Personas conocidas", registro.get("Personas_Conocidas", "-"))

                    with c3:
                        st.write(f"**Entrevistador:** {registro.get('ID_Entrevistador', '-')}")
                        st.write(f"**Ruta:** {registro.get('ID_Ruta', '-')}")
                        st.write(
                            f"**Ubicacion:** {registro.get('Latitud', '-')}, {registro.get('Longitud', '-')}"
                        )

                    nombre_alias = str(registro.get("Nombre_Alias", ""))
                    if termino_busqueda.lower() in nombre_alias.lower():
                        st.markdown(f"*Coincidencia en nombre: **{nombre_alias}***")

                    if st.button("Editar este registro", key=f"edit_{i}"):
                        st.session_state.registro_seleccionado = registro
                        st.session_state.modo_edicion = True
                        st.rerun()

# MODO EDICION
if st.session_state.get("modo_edicion", False):
    st.markdown("---")
    st.subheader("Editando Registro")

    registro = st.session_state.registro_seleccionado
    id_persona = registro.get("ID_Persona", "")
    registro_completo = obtener_registro_completo(id_persona) or registro
    timestamp = str(registro_completo.get("Timestamp", registro.get("Timestamp", "")))

    st.markdown(
        f"""
        <div style='background-color: #1E3A8A; color: white; padding: 15px;
                    border-radius: 5px; text-align: center; margin-bottom: 20px;'>
            <h2 style='margin: 0; color: white;'>ID: {id_persona}</h2>
            <p style='margin: 5px 0 0 0; color: #FCD34D;'>
                Registrado por {registro.get('ID_Entrevistador', '-')} el {timestamp[:10] if timestamp else '-'}
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Formulario de edicion
    with st.form("formulario_edicion"):
        st.markdown("### Datos Editables")

        col1, col2 = st.columns(2)

        with col1:
            nombre_alias_nuevo = st.text_input(
                "Nombre y/o Alias",
                value=str(registro.get("Nombre_Alias", "")),
            )

            edad_actual = int(str(registro.get("Edad", "0") or "0"))
            edad_nuevo = st.number_input(
                "Edad",
                min_value=0,
                max_value=120,
                value=edad_actual,
                step=1,
            )

            anos_calle_nuevo = st.text_input(
                "Años en calle",
                value=str(registro.get("Años_Calle", "")),
            )

        with col2:
            genero_options = ["Hombre", "Mujer", "No binario", "Prefiere no decirlo"]
            genero_actual = str(registro.get("Género", "Hombre"))
            genero_index = genero_options.index(genero_actual) if genero_actual in genero_options else 0
            genero_nuevo = st.selectbox(
                "Género",
                options=genero_options,
                index=genero_index,
            )

            personas_actual = int(str(registro.get("Personas_Conocidas", "0") or "0"))
            personas_conocidas_nuevo = st.number_input(
                "Personas conocidas",
                min_value=0,
                value=personas_actual,
                step=1,
            )

        st.markdown("---")
        st.markdown("### Fotos")

        # Mostrar fotos existentes
        enlaces_actuales = str(registro.get("Enlaces_Fotos", "") or "")
        if enlaces_actuales:
            enlaces = [e.strip() for e in enlaces_actuales.split(",") if e.strip()]
            st.info(f"{len(enlaces)} foto(s) guardada(s) actualmente")

            cols = st.columns(min(len(enlaces), 3))
            for idx, enlace in enumerate(enlaces[:3]):
                with cols[idx]:
                    st.markdown(f"[Ver Foto {idx+1}]({enlace})")
        else:
            st.info("No hay fotos asociadas a este registro")

        # Subir fotos nuevas
        fotos_nuevas = st.file_uploader(
            "Agregar nuevas fotos",
            type=["jpg", "jpeg", "png"],
            accept_multiple_files=True,
            help="Se agregaran a las fotos existentes",
        )

        if fotos_nuevas:
            st.success(f"{len(fotos_nuevas)} foto(s) nueva(s) para agregar")

        st.markdown("---")

        # Botones
        c1, c2, c3 = st.columns([1, 1, 1])

        with c1:
            cancelar = st.form_submit_button("Cancelar", use_container_width=True)

        with c3:
            guardar = st.form_submit_button(
                "Guardar Cambios",
                use_container_width=True,
                type="primary",
            )

        if cancelar:
            st.session_state.modo_edicion = False
            st.session_state.registro_seleccionado = None
            st.rerun()

        if guardar:
            # Detectar cambios
            cambios = {}

            if nombre_alias_nuevo != str(registro.get("Nombre_Alias", "")):
                cambios["Nombre_Alias"] = nombre_alias_nuevo
            if edad_nuevo != edad_actual:
                cambios["Edad"] = edad_nuevo
            if str(anos_calle_nuevo) != str(registro.get("Anos_Calle", "")):
                cambios["Anos_Calle"] = anos_calle_nuevo
            if genero_nuevo != str(registro.get("Genero", "")):
                cambios["Genero"] = genero_nuevo
            if personas_conocidas_nuevo != personas_actual:
                cambios["Personas_Conocidas"] = personas_conocidas_nuevo

            # Si hay conexion: actualizar
            if tiene_conexion:
                from datetime import datetime
                from utils.sheets_handler import actualizar_registro_sheets
                from utils.drive_handler import subir_fotos_drive

                with st.spinner("Guardando cambios..."):
                    # Subir fotos nuevas si hay
                    if fotos_nuevas:
                        fecha_original = str(registro.get("Timestamp", ""))[:10] or datetime.now().strftime("%Y-%m-%d")
                        enlaces_nuevos = subir_fotos_drive(
                            fotos_nuevas,
                            registro.get("ID_Persona", ""),
                            registro.get("ID_Ruta", st.session_state.get("ruta_id", "")),
                            fecha_original,
                            fotos_existentes=len([e for e in enlaces_actuales.split(",") if e.strip()]),
                            nombre_persona=registro.get("Nombre_Alias", ""),
                            id_entrevistador=st.session_state.get("entrevistador_id", ""),
                            nombre_entrevistador=st.session_state.get("entrevistador_nombre", ""),
                            nombre_ruta=st.session_state.get("ruta_nombre", ""),
                        )

                        # Agregar a enlaces existentes
                        if enlaces_actuales:
                            cambios["Enlaces_Fotos"] = enlaces_actuales + "," + ",".join(enlaces_nuevos)
                        else:
                            cambios["Enlaces_Fotos"] = ",".join(enlaces_nuevos)

                    # Agregar metadata de edicion
                    cambios["Ultima_Edicion_Timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    cambios["Editado_Por"] = st.session_state.entrevistador_id
                    cambios["Numero_Ediciones"] = int(str(registro.get("Numero_Ediciones", "0") or "0")) + 1

                    # Actualizar en Sheets
                    exito = actualizar_registro_sheets(registro.get("ID_Persona", ""), cambios)

                    if exito:
                        st.success(f"Registro {registro.get('ID_Persona', '')} actualizado exitosamente")

                        # Mostrar resumen de cambios
                        if cambios:
                            st.info("**Cambios realizados:**")
                            for campo, valor in cambios.items():
                                if campo not in ["Ultima_Edicion_Timestamp", "Editado_Por", "Numero_Ediciones"]:
                                    st.write(f"- {campo}: {valor}")

                        # Resetear modo edicion
                        st.session_state.modo_edicion = False
                        st.session_state.registro_seleccionado = None
                    else:
                        st.error("Error al actualizar. Intenta nuevamente.")

            # Sin conexion: guardar para sincronizar
            else:
                from datetime import datetime
                import base64

                # Convertir fotos a base64
                fotos_base64 = []
                if fotos_nuevas:
                    for foto in fotos_nuevas:
                        foto_bytes = foto.read()
                        foto_b64 = base64.b64encode(foto_bytes).decode()
                        fotos_base64.append({
                            "nombre": foto.name,
                            "data": foto_b64,
                        })

                # Guardar en pendientes
                if "ediciones_pendientes" not in st.session_state:
                    st.session_state.ediciones_pendientes = []

                edicion = {
                    "tipo": "EDICION",
                    "ID_Persona": registro.get("ID_Persona", ""),
                    "cambios": cambios,
                    "fotos_nuevas_base64": fotos_base64,
                    "timestamp_edicion": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "editado_por": st.session_state.entrevistador_id,
                }

                st.session_state.ediciones_pendientes.append(edicion)

                # Generar texto para WhatsApp
                texto_backup = f"""EDICION_CARACOL
ID_Persona: {registro.get('ID_Persona', '')} [EDITADO]
Editado_Por: {st.session_state.entrevistador_id}
Timestamp: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
---
Cambios:
"""
                for campo, valor in cambios.items():
                    texto_backup += f"{campo}: {valor}\\n"

                if fotos_nuevas:
                    texto_backup += f"Fotos_Nuevas: {len(fotos_nuevas)} [pendiente subir]\\n"

                st.warning("Sin conexion - Edicion guardada localmente")
                st.code(texto_backup)

                # Link WhatsApp
                texto_encoded = texto_backup.replace("\n", "%0A").replace(" ", "%20")
                whatsapp_url = f"https://wa.me/32490358282?text={texto_encoded}"

                st.markdown(f"[Enviar por WhatsApp]({whatsapp_url})", unsafe_allow_html=True)

                st.session_state.modo_edicion = False
