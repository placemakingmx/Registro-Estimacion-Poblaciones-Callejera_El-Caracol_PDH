"""
Pagina 3 - Pendientes de sincronizar.
Sincroniza entrevistas y ediciones guardadas offline.
"""

from __future__ import annotations

import base64
from datetime import datetime
from io import BytesIO
from pathlib import Path
import sys

import streamlit as st
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.connectivity import banner_sin_conexion, verificar_conexion
from utils.drive_handler import subir_fotos_drive
from utils.sheets_handler import actualizar_registro_sheets, subir_entrevista_sheets


st.set_page_config(
    page_title="Pendientes",
    page_icon="",
    layout="wide",
    initial_sidebar_state="collapsed",
)

def render_header_sesion() -> None:
    """Header local para evitar dependencias de import en esta pagina."""
    if st.session_state.get("logged_in"):
        st.markdown(
            f"""
            <div style='background-color: #1E3A8A; padding: 10px; border-radius: 5px; color: white;'>
                <strong>{st.session_state.get('entrevistador_nombre', 'Entrevistador/a')}</strong> |
                ID: {st.session_state.get('entrevistador_id', '-')} |
                Ruta: {st.session_state.get('ruta_nombre', '-')} ({st.session_state.get('ruta_id', '-')})
            </div>
            """,
            unsafe_allow_html=True,
        )

        ruta_link_maps = st.session_state.get("ruta_link_maps")
        if ruta_link_maps:
            st.markdown(f"[Ver Ruta en Google Maps]({ruta_link_maps})")

        st.markdown("---")


if not st.session_state.get("logged_in", False):
    st.error("Debes iniciar sesión primero")
    st.stop()


render_header_sesion()
st.title("Pendientes de Sincronizar")


class _MemoryUpload:
    """Objeto minimo compatible con uploader para reutilizar subir_fotos_drive."""

    def __init__(self, name: str, content: bytes, mime_type: str):
        self.name = name
        self.type = mime_type
        self._buf = BytesIO(content)

    def read(self) -> bytes:
        self._buf.seek(0)
        return self._buf.read()


def _decode_base64_fotos(fotos_base64: list[dict]) -> list[_MemoryUpload]:
    """Reconstruye fotos desde base64; omite entradas corruptas sin romper el flujo."""
    resultado: list[_MemoryUpload] = []
    for item in fotos_base64 or []:
        try:
            raw = base64.b64decode(item.get("data", ""))
            image = Image.open(BytesIO(raw))
            image.verify()
            formato = (image.format or "JPEG").upper()
            mime = "image/png" if formato == "PNG" else "image/jpeg"
            nombre = item.get("nombre") or f"foto_{datetime.now().strftime('%H%M%S')}.jpg"
            resultado.append(_MemoryUpload(nombre, raw, mime))
        except Exception:
            # Una foto danada no debe bloquear toda la sincronizacion.
            continue
    return resultado


def _mostrar_pendientes(entrevistas_pendientes: list[dict], ediciones_pendientes: list[dict]) -> None:
    if entrevistas_pendientes:
        st.subheader("Entrevistas Pendientes")
        for entrevista in entrevistas_pendientes:
            titulo = (
                f"{entrevista.get('ID_Persona', '-')} - "
                f"{entrevista.get('Nombre_Alias', '-') or entrevista.get('Nombre', '-')} | "
                f"{entrevista.get('Timestamp', '-')}"
            )
            with st.expander(titulo):
                c1, c2 = st.columns(2)
                with c1:
                    st.write(f"**Edad:** {entrevista.get('Edad', '-')}")
                    st.write(f"**Genero:** {entrevista.get('Genero', '-')}")
                    st.write(f"**Anos en calle:** {entrevista.get('Anos_Calle', '-')}")
                with c2:
                    st.write(f"**Personas conocidas:** {entrevista.get('Personas_Conocidas', '-')}")
                    st.write(f"**Fotos:** {len(entrevista.get('fotos_base64', []))}")
                    st.write(f"**Ruta:** {entrevista.get('ID_Ruta', '-')}")

    if ediciones_pendientes:
        st.subheader("Ediciones Pendientes")
        for edicion in ediciones_pendientes:
            titulo = (
                f"{edicion.get('ID_Persona', '-')} [EDITADO] - "
                f"{edicion.get('timestamp_edicion', '-') or edicion.get('Ultima_Edicion_Timestamp', '-') }"
            )
            with st.expander(titulo):
                st.write(f"**Editado por:** {edicion.get('editado_por', '-')}")
                st.write("**Cambios:**")
                for campo, valor in (edicion.get("cambios", {}) or {}).items():
                    st.write(f"- {campo}: {valor}")
                if edicion.get("fotos_nuevas_base64"):
                    st.write(f"**Fotos nuevas:** {len(edicion.get('fotos_nuevas_base64', []))}")


def _sincronizar(
    entrevistas_pendientes: list[dict],
    ediciones_pendientes: list[dict],
) -> tuple[int, int, list[dict], list[dict]]:
    """Sincroniza entrevistas y ediciones pendientes."""
    total_pendientes = len(entrevistas_pendientes) + len(ediciones_pendientes)
    progreso = st.progress(0)
    estado = st.empty()

    total_items = max(total_pendientes, 1)
    items_procesados = 0
    entrevistas_restantes: list[dict] = []
    ediciones_restantes: list[dict] = []
    exitos = 0
    fallos = 0

    for entrevista in entrevistas_pendientes:
        estado.info(f"Sincronizando entrevista {entrevista.get('ID_Persona', '-')}...")
        try:
            payload = dict(entrevista)
            payload.pop("fotos_base64", None)

            fotos_reconstruidas = _decode_base64_fotos(entrevista.get("fotos_base64", []))
            if fotos_reconstruidas:
                enlaces = subir_fotos_drive(
                    fotos_reconstruidas,
                    entrevista.get("ID_Persona", ""),
                    entrevista.get("ID_Ruta", ""),
                    str(entrevista.get("Timestamp", ""))[:10] or datetime.now().strftime("%Y-%m-%d"),
                    nombre_persona=entrevista.get("Nombre_Alias", ""),
                    id_entrevistador=entrevista.get("ID_Entrevistador", st.session_state.get("entrevistador_id", "")),
                    nombre_entrevistador=st.session_state.get("entrevistador_nombre", ""),
                    nombre_ruta=st.session_state.get("ruta_nombre", ""),
                )
                payload["Enlaces_Fotos"] = ",".join(enlaces)

            ok = subir_entrevista_sheets(payload)
            if ok:
                exitos += 1
            else:
                fallos += 1
                entrevistas_restantes.append(entrevista)
        except Exception:
            fallos += 1
            entrevistas_restantes.append(entrevista)

        items_procesados += 1
        progreso.progress(items_procesados / total_items)

    for edicion in ediciones_pendientes:
        estado.info(f"Sincronizando edicion {edicion.get('ID_Persona', '-')}...")
        try:
            cambios = dict(edicion.get("cambios", {}) or {})
            fotos_reconstruidas = _decode_base64_fotos(edicion.get("fotos_nuevas_base64", []))

            if fotos_reconstruidas:
                enlaces_previos = str(cambios.get("Enlaces_Fotos", ""))
                existentes_count = len([e for e in enlaces_previos.split(",") if e.strip()])
                enlaces_nuevos = subir_fotos_drive(
                    fotos_reconstruidas,
                    edicion.get("ID_Persona", ""),
                    st.session_state.get("ruta_id", ""),
                    datetime.now().strftime("%Y-%m-%d"),
                    fotos_existentes=existentes_count,
                    nombre_persona=edicion.get("cambios", {}).get("Nombre_Alias", ""),
                    id_entrevistador=st.session_state.get("entrevistador_id", ""),
                    nombre_entrevistador=st.session_state.get("entrevistador_nombre", ""),
                    nombre_ruta=st.session_state.get("ruta_nombre", ""),
                )
                if enlaces_previos:
                    cambios["Enlaces_Fotos"] = enlaces_previos + "," + ",".join(enlaces_nuevos)
                else:
                    cambios["Enlaces_Fotos"] = ",".join(enlaces_nuevos)

            cambios["Ultima_Edicion_Timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cambios["Editado_Por"] = edicion.get("editado_por", st.session_state.get("entrevistador_id"))

            ok = actualizar_registro_sheets(edicion.get("ID_Persona", ""), cambios)
            if ok:
                exitos += 1
            else:
                fallos += 1
                ediciones_restantes.append(edicion)
        except Exception:
            fallos += 1
            ediciones_restantes.append(edicion)

        items_procesados += 1
        progreso.progress(items_procesados / total_items)

    estado.empty()
    return exitos, fallos, entrevistas_restantes, ediciones_restantes


tiene_conexion = verificar_conexion()
if not tiene_conexion:
    banner_sin_conexion()
    st.error("Necesitas conexion para sincronizar")


entrevistas_pendientes = st.session_state.get("entrevistas_pendientes", [])
ediciones_pendientes = st.session_state.get("ediciones_pendientes", [])
total_pendientes = len(entrevistas_pendientes) + len(ediciones_pendientes)


col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Total Pendientes", total_pendientes)
with col2:
    st.metric("Entrevistas Nuevas", len(entrevistas_pendientes))
with col3:
    st.metric("Ediciones", len(ediciones_pendientes))

st.markdown("---")


if total_pendientes == 0:
    st.success("No hay datos pendientes de sincronizar")
    st.info("Todas las entrevistas y ediciones estan al dia")
    st.stop()


_mostrar_pendientes(entrevistas_pendientes, ediciones_pendientes)

st.markdown("---")


if st.button("Sincronizar Ahora", type="primary", use_container_width=True, disabled=not tiene_conexion):
    exitos, fallos, entrevistas_restantes, ediciones_restantes = _sincronizar(
        entrevistas_pendientes,
        ediciones_pendientes,
    )

    st.session_state["entrevistas_pendientes"] = entrevistas_restantes
    st.session_state["ediciones_pendientes"] = ediciones_restantes

    if exitos:
        st.success(f"Sincronizacion completada: {exitos} elemento(s) sincronizado(s).")
    if fallos:
        st.warning(f"{fallos} elemento(s) fallaron y quedaron pendientes para reintento.")

    st.rerun()


if st.button("Limpiar pendientes (descartar)", use_container_width=True):
    st.session_state["entrevistas_pendientes"] = []
    st.session_state["ediciones_pendientes"] = []
    st.success("Pendientes eliminados")
    st.rerun()
