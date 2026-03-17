```python name=app/pages/1_nueva_entrevista.py
import base64
from datetime import date, datetime
from pathlib import Path
from io import BytesIO
import re
import sys

from PIL import Image

import streamlit as st
import streamlit.components.v1 as components
from streamlit_geolocation import streamlit_geolocation

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.connectivity import verificar_conexion, banner_sin_conexion
from utils.drive_handler import subir_fotos_drive
from utils.id_generator import generar_id_evento, generar_id_persona, registrar_id_generado
from utils.sheets_handler import (
    cargar_datos_app,
    mostrar_info_cache,
    obtener_datos_entrevistador_por_id,
    obtener_entrevistas_existentes,
    subir_entrevista_sheets,
)


MESES = ["ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"]

st.set_page_config(page_title="Nueva Entrevista", page_icon="", layout="wide")

st.markdown(
    """
    <style>
    div.stButton > button {
        width: 100%;
        height: 3.5rem;
        font-size: 1rem;
        font-weight: 600;
        border-radius: 8px;
        border: none;
        background-color: #1E3A8A;
        color: white;
        margin-bottom: 0.5rem;
        cursor: pointer;
    }
    div.stButton > button:hover {
        background-color: #2563EB;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


if not st.session_state.get("logged_in", False):
    st.error("Debes iniciar sesión para continuar")
    st.stop()


def _header_sesion_local() -> None:
    entrevistador_nombre = st.session_state.get("entrevistador_nombre", "")
    entrevistador_id = st.session_state.get("entrevistador_id", "")
    ruta_id = st.session_state.get("ruta_id", "")
    ruta_link = st.session_state.get("ruta_link")

    st.markdown(
        f"""
        <div style='background-color: #1E3A8A; padding: 10px; border-radius: 5px; color: white;'>
            <strong>{entrevistador_nombre}</strong> |
            ID: {entrevistador_id} |
            Ruta: {ruta_id}
        </div>
        """,
        unsafe_allow_html=True,
    )

    if ruta_link:
        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
        if st.button(
            "Abrir mapa en Google Maps",
            use_container_width=True,
            type="primary",
            key="btn_mapa_nueva",
        ):
            safe_url = str(ruta_link).replace("'", "%27")
            components.html(
                f"<script>window.open('{safe_url}', '_blank');</script>",
                height=0,
            )
        st.markdown("<div style='height: 6px;'></div>", unsafe_allow_html=True)

    st.markdown("---")


def _convertir_texto_a_anos(texto: str) -> float | None:
    if not texto:
        return None

    t = texto.strip().lower().replace(",", ".")
    if not t:
        return None

    match = re.search(r"(\d+(?:\.\d+)?)", t)
    if not match:
        return None

    valor = float(match.group(1))

    if "mes" in t:
        return valor / 12.0
    if "sem" in t:
        return valor / 52.0
    if "dia" in t:
        return valor / 365.0
    return valor


def _parse_int_optional(raw: str) -> int | None:
    valor = str(raw or "").strip()
    if not valor:
        return None
    try:
        return int(valor)
    except ValueError:
        return None


def _perfil_entrevistador_completo() -> bool:
    requeridos = [
        "entrevistador_id",
        "entrevistador_nombre",
        "apellido_entrevistador",
        "genero_entrevistador",
        "dia_nacimiento_entrevistador",
        "mes_nacimiento_entrevistador",
        "anio_nacimiento_entrevistador",
        "fecha_nacimiento_entrevistador",
    ]
    return all(st.session_state.get(k) not in (None, "") for k in requeridos)


def _hidratar_perfil_entrevistador_desde_sheets(tiene_conexion: bool) -> None:
    """Completa session_state del entrevistador usando entrevistas previas en Sheets."""
    if not tiene_conexion:
        return

    entrevistador_id = str(st.session_state.get("entrevistador_id", "")).strip()
    if not entrevistador_id:
        return

    datos = obtener_datos_entrevistador_por_id(entrevistador_id)
    if not datos:
        return

    if not st.session_state.get("entrevistador_nombre") and datos.get("nombre"):
        st.session_state.entrevistador_nombre = datos["nombre"]

    if not st.session_state.get("apellido_entrevistador") and datos.get("apellido"):
        st.session_state.apellido_entrevistador = datos["apellido"]

    if not st.session_state.get("genero_entrevistador") and datos.get("genero"):
        st.session_state.genero_entrevistador = datos["genero"]

    if not st.session_state.get("dia_nacimiento_entrevistador") and datos.get("dia_nacimiento"):
        try:
            st.session_state.dia_nacimiento_entrevistador = int(datos["dia_nacimiento"])
        except ValueError:
            st.session_state.dia_nacimiento_entrevistador = datos["dia_nacimiento"]

    if not st.session_state.get("mes_nacimiento_entrevistador") and datos.get("mes_nacimiento"):
        st.session_state.mes_nacimiento_entrevistador = datos["mes_nacimiento"]

    if not st.session_state.get("anio_nacimiento_entrevistador") and datos.get("anio_nacimiento"):
        try:
            st.session_state.anio_nacimiento_entrevistador = int(datos["anio_nacimiento"])
        except ValueError:
            st.session_state.anio_nacimiento_entrevistador = datos["anio_nacimiento"]

    if not st.session_state.get("fecha_nacimiento_entrevistador") and datos.get("fecha_nacimiento"):
        st.session_state.fecha_nacimiento_entrevistador = datos["fecha_nacimiento"]


def _fecha_ddmmyyyy(fecha: date) -> str:
    return fecha.strftime("%d/%m/%Y")


def validar_formato_id_persona(id_texto: str) -> tuple[bool, str]:
    """Valida ID_Persona con formato [G][NNA][MMMAA]."""
    if not id_texto:
        return False, "El campo está vacío"

    id_upper = str(id_texto).strip().upper()
    if len(id_upper) != 9:
        return False, f"Debe tener exactamente 9 caracteres (tiene {len(id_upper)})"

    if id_upper[0] not in {"H", "M", "N", "D"}:
        return False, "El primer carácter debe ser H, M, N o D"

    if not id_upper[1:4].isalpha():
        return False, "Los caracteres 2-4 deben ser letras"

    if id_upper[4:7] not in set(MESES + ["XXX"]):
        return False, "Los caracteres 5-7 deben ser un mes válido (ENE..DIC o XXX)"

    if not id_upper[7:9].isdigit():
        return False, "Los últimos 2 caracteres deben ser dígitos"

    return True, ""


def verificar_id_referido_existe(id_referido: str, entrevistas_data) -> tuple[bool, str | None]:
    """Verifica si el ID referido existe en distintas estructuras de datos cargadas."""
    if not id_referido or entrevistas_data is None:
        return False, None

    objetivo = str(id_referido).strip().upper()

    # Caso DataFrame (evita dependencia dura de pandas)
    if hasattr(entrevistas_data, "to_dict"):
        try:
            entrevistas_data = entrevistas_data.to_dict("records")
        except Exception:
            entrevistas_data = []

    if isinstance(entrevistas_data, dict):
        entrevistas_data = [entrevistas_data]

    if not isinstance(entrevistas_data, list):
        return False, None

    for row in entrevistas_data:
        if not isinstance(row, dict):
            continue
        current_id = str(row.get("ID_Persona") or row.get("id_persona") or "").strip().upper()
        if current_id == objetivo:
            nombre = str(row.get("Nombre") or row.get("nombre") or row.get("Nombre_Alias") or "").strip()
            return True, nombre or "Persona registrada"

    return False, None


def mostrar_seccion_referencia(entrevistas_data=None) -> str | None:
    st.markdown("---")
    st.subheader("Referencia (Cupón)")

    st.markdown(
        """
        <div style="
            background:#E3F2FD;
            border-left:4px solid #2196F3;
            padding:12px 14px;
            border-radius:6px;
            margin-bottom:12px;
        ">
            <div style="color:#1565C0;font-weight:600;">¿Alguien te invitó a participar y te dio un cupón?</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tiene_cupon = st.radio(
        "Respuesta",
        options=["No", "Sí"],
        index=0,
        horizontal=True,
        key="ref_tiene_cupon",
        label_visibility="collapsed",
    )

    if tiene_cupon == "No":
        st.caption("Sin referencia por cupón.")
        return None

    st.info("Escribe el ID tal como aparece en el cupón. Ejemplo: HJUPABR90")
    id_referido_input = st.text_input(
        "ID del cupón",
        placeholder="Ej: HJUPABR90",
        help="Formato esperado: [G][NNA][MMMAA]",
        key="ref_id_input",
    )

    id_referido = str(id_referido_input or "").strip().upper()
    if not id_referido:
        st.warning("Ingresa el ID del cupón para validar")
        return None

    es_valido, error_msg = validar_formato_id_persona(id_referido)
    if not es_valido:
        st.error(f"ID inválido: {error_msg}")
        return None

    st.success(f"ID válido: {id_referido}")

    existe, nombre_ref = verificar_id_referido_existe(id_referido, entrevistas_data)
    if existe:
        st.success(f"ID encontrado: {nombre_ref}")
    else:
        st.warning("El ID no se encontró en la base. Se guardará de todos modos.")

    return id_referido


def inicializar_gps_session_state() -> None:
    if "gps_permiso_solicitado" not in st.session_state:
        st.session_state.gps_permiso_solicitado = False
    if "gps_permiso_aceptado" not in st.session_state:
        st.session_state.gps_permiso_aceptado = False
    if "gps_intentando_permiso" not in st.session_state:
        st.session_state.gps_intentando_permiso = False
    if "gps_latitud" not in st.session_state:
        st.session_state.gps_latitud = None
    if "gps_longitud" not in st.session_state:
        st.session_state.gps_longitud = None
    if "gps_precision" not in st.session_state:
        st.session_state.gps_precision = None
    if "gps_timestamp" not in st.session_state:
        st.session_state.gps_timestamp = None


def _guardar_gps_desde_location(location: dict) -> bool:
    lat = location.get("latitude")
    lon = location.get("longitude")
    if lat is None or lon is None:
        return False

    st.session_state.gps_latitud = lat
    st.session_state.gps_longitud = lon
    st.session_state.gps_precision = location.get("accuracy")
    st.session_state.gps_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return True


def _capturar_ubicacion_nativa() -> dict | None:
    """Captura ubicación usando streamlit-geolocation (iframe con allow=geolocation + enableHighAccuracy parchado)."""
    try:
        loc = streamlit_geolocation()
        if not loc:
            return None
        lat = loc.get("latitude")
        lon = loc.get("longitude")
        if lat is None or lon is None:
            return {"status": "pending"}
        return {
            "status": "ok",
            "latitude": lat,
            "longitude": lon,
            "accuracy": loc.get("accuracy"),
        }
    except Exception:
        return None


def solicitar_permiso_gps() -> bool:
    if st.session_state.gps_permiso_solicitado:
        aceptado = bool(st.session_state.gps_permiso_aceptado)
        if not aceptado:
            st.info("GPS desactivado para esta sesión.")
            if st.button("Volver a solicitar permiso GPS", use_container_width=True, key="gps_reintentar"):
                st.session_state.gps_permiso_solicitado = False
                st.session_state.gps_permiso_aceptado = False
                st.session_state.gps_intentando_permiso = True
                st.rerun()
        return aceptado

    st.info("Esta aplicación puede usar tu ubicación GPS para registrar dónde se realiza cada entrevista.")

    if not st.session_state.gps_intentando_permiso:
        c1, c2 = st.columns(2)
        with c1:
            activar = st.button("Activar GPS", use_container_width=True, type="primary", key="gps_activar")
        with c2:
            continuar = st.button("Continuar sin GPS", use_container_width=True, key="gps_sin")

        if activar:
            st.session_state.gps_intentando_permiso = True
            st.rerun()

        if continuar:
            st.session_state.gps_permiso_solicitado = True
            st.session_state.gps_permiso_aceptado = False
            st.session_state.gps_intentando_permiso = False
            st.rerun()

        st.stop()

    st.caption(
        "Permite acceso a ubicación en el navegador para continuar con GPS activo. Haz click en 'Permitir siempre' para compartirlo."
        "Realiza lo mismo con el acceso a la cámara y archivos del dispositivo"
    )
    result = _capturar_ubicacion_nativa()
    if result and result.get("status") == "ok" and _guardar_gps_desde_location(result):
        st.session_state.gps_permiso_solicitado = True
        st.session_state.gps_permiso_aceptado = True
        st.session_state.gps_intentando_permiso = False
        st.success("Permiso de ubicación concedido. Se capturarán coordenadas al guardar.")
        st.rerun()

    if result and result.get("status") == "error" and str(result.get("code")) == "1":
        st.session_state.gps_permiso_solicitado = True
        st.session_state.gps_permiso_aceptado = False
        st.session_state.gps_intentando_permiso = False
        st.warning("El navegador denegó el permiso de ubicación. Se guardará sin GPS.")
        st.rerun()

    if result and result.get("status") == "unsupported":
        st.session_state.gps_permiso_solicitado = True
        st.session_state.gps_permiso_aceptado = False
        st.session_state.gps_intentando_permiso = False
        st.warning("Este dispositivo o navegador no soporta geolocalización.")
        st.rerun()

    if result and result.get("status") not in ("ok", "pending", None):
        st.warning("No se pudo obtener ubicación todavía.")

    st.warning("Si no deseas compartir ubicación, selecciona continuar sin GPS.")
    if st.button("Guardar sin GPS", use_container_width=True, key="gps_denegado"):
        st.session_state.gps_permiso_solicitado = True
        st.session_state.gps_permiso_aceptado = False
        st.session_state.gps_intentando_permiso = False
        st.session_state.gps_latitud = None
        st.session_state.gps_longitud = None
        st.session_state.gps_precision = None
        st.session_state.gps_timestamp = None
        st.rerun()

    st.stop()


def capturar_ubicacion_gps() -> dict | None:
    if not st.session_state.get("gps_permiso_aceptado", False):
        return None

    try:
        result = _capturar_ubicacion_nativa()
        if result and result.get("status") == "ok" and _guardar_gps_desde_location(result):
            return {
                "latitud": st.session_state.gps_latitud,
                "longitud": st.session_state.gps_longitud,
                "precision": st.session_state.gps_precision,
                "timestamp": st.session_state.gps_timestamp,
            }

        if result and result.get("status") == "error" and str(result.get("code")) == "1":
            st.session_state.gps_permiso_solicitado = True
            st.session_state.gps_permiso_aceptado = False
            st.session_state.gps_intentando_permiso = False
            return None

        if st.session_state.get("gps_latitud") is not None and st.session_state.get("gps_longitud") is not None:
            return {
                "latitud": st.session_state.gps_latitud,
                "longitud": st.session_state.gps_longitud,
                "precision": st.session_state.gps_precision,
                "timestamp": st.session_state.gps_timestamp,
            }
        return None
    except Exception:
        return None


def mostrar_estado_gps() -> None:
    if st.session_state.get("gps_permiso_aceptado", False):
        lat = st.session_state.get("gps_latitud")
        lon = st.session_state.get("gps_longitud")
        if lat is not None and lon is not None:
            precision = st.session_state.get("gps_precision")
            precision_txt = f" | Precision: +-{float(precision):.0f}m" if precision not in (None, "") else ""
            st.markdown(
                f"""
                <div style="
                    background: #E8F5E9;
                    border-left: 4px solid #4CAF50;
                    padding: 12px 15px;
                    border-radius: 5px;
                    margin: 10px 0;
                ">
                    <div style="color: #2E7D32; font-weight: 600; margin-bottom: 5px;">
                        GPS Activo
                    </div>
                    <div style="color: #1B5E20; font-size: 13px;">
                        Lat: {float(lat):.6f} | Lon: {float(lon):.6f}{precision_txt}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                """
                <div style="
                    background: #FFF3E0;
                    border-left: 4px solid #FF9800;
                    padding: 12px 15px;
                    border-radius: 5px;
                    margin: 10px 0;
                ">
                    <div style="color: #E65100; font-weight: 600;">
                        GPS activo, esperando ubicación...
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            """
            <div style="
                background: #FFEBEE;
                border-left: 4px solid #F44336;
                padding: 12px 15px;
                border-radius: 5px;
                margin: 10px 0;
            ">
                <div style="color: #C62828; font-weight: 600;">
                    GPS no disponible
                </div>
                <div style="color: #B71C1C; font-size: 13px;">
                    Las entrevistas se guardarán sin coordenadas
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.caption("Si no apareció el popup de permisos, usa el botón 'Volver a solicitar permiso GPS'.")


def inicializar_fotos_session_state() -> None:
    if "fotos_capturadas" not in st.session_state:
        st.session_state["fotos_capturadas"] = []
    if "contador_fotos" not in st.session_state:
        st.session_state["contador_fotos"] = 0


class _MemoryUpload:
    def __init__(self, name: str, content: bytes, mime_type: str):
        self.name = name
        self.type = mime_type
        self._content = content

    def read(self) -> bytes:
        return self._content


def _leer_foto_bytes(foto_file) -> bytes:
    if foto_file is None:
        return b""
    if hasattr(foto_file, "getvalue"):
        contenido = foto_file.getvalue()
        if contenido:
            return contenido
    try:
        foto_file.seek(0)
    except Exception:
        pass
    try:
        return foto_file.read()
    except Exception:
        return b""


def agregar_foto(foto_file, origen: str = "camara") -> bool:
    if foto_file is None:
        return False
    contenido = _leer_foto_bytes(foto_file)
    if not contenido:
        return False
    st.session_state["contador_fotos"] += 1
    st.session_state["fotos_capturadas"].append(
        {
            "id": st.session_state["contador_fotos"],
            "bytes": contenido,
            "mime_type": getattr(foto_file, "type", None) or "image/jpeg",
            "origen": origen,
            "nombre": getattr(foto_file, "name", f"foto_{st.session_state['contador_fotos']}.jpg"),
        }
    )
    return True


def eliminar_foto(foto_id: int) -> None:
    st.session_state["fotos_capturadas"] = [
        f for f in st.session_state["fotos_capturadas"] if f["id"] != foto_id
    ]


def limpiar_fotos() -> None:
    st.session_state["fotos_capturadas"] = []
    st.session_state["contador_fotos"] = 0


def obtener_archivos_para_subir() -> list:
    archivos = []
    for f in st.session_state.get("fotos_capturadas", []):
        contenido = f.get("bytes") or b""
        if not contenido:
            continue
        archivos.append(
            _MemoryUpload(
                name=f.get("nombre") or "foto.jpg",
                content=contenido,
                mime_type=f.get("mime_type") or "image/jpeg",
            )
        )
    return archivos


def mostrar_galeria_fotos() -> None:
    fotos = st.session_state.get("fotos_capturadas", [])
    if not fotos:
        st.caption("No hay fotos agregadas aún")
        return

    st.markdown(f"**Fotos agregadas: {len(fotos)}**")
    cols_per_row = 3
    for i in range(0, len(fotos), cols_per_row):
        cols = st.columns(cols_per_row)
        for j in range(cols_per_row):
            idx = i + j
            if idx < len(fotos):
                foto_data = fotos[idx]
                with cols[j]:
                    icono = "📷" if foto_data.get("origen") == "camara" else "📁"
                    nombre_raw = foto_data.get("nombre") or "foto.jpg"
                    nombre_display = (nombre_raw[:24] + "...") if len(nombre_raw) > 24 else nombre_raw
                    tam_bytes = len(foto_data.get("bytes") or b"")
                    tam_kb = max(1, round(tam_bytes / 1024)) if tam_bytes else 0

                    st.markdown(
                        f"""
                        <div style='border:1px solid #E5E7EB;border-radius:10px;padding:12px;text-align:center;background:#F8FAFC;'>
                            <div style='font-size:32px;line-height:1.1'>{icono}</div>
                            <div style='font-size:12px;font-weight:600;color:#1F2937;margin-top:6px;word-break:break-word;'>{nombre_display}</div>
                            <div style='font-size:11px;color:#6B7280;margin-top:4px;'>{tam_kb} KB</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    if st.button(
                        "Eliminar",
                        key=f"eliminar_foto_{foto_data['id']}",
                        use_container_width=True,
                    ):
                        eliminar_foto(foto_data["id"])
                        st.rerun()


def mostrar_id_persona(id_persona: str) -> None:
    """Muestra ID_Persona con diseño visual minimalista de El Caracol."""
    digitos = list(str(id_persona or ""))
    if not digitos:
        return

    html_id = f"""
    <style>
    .id-container {{
        background: #FFC107;
        border-radius: 15px;
        padding: 25px 15px;
        margin: 20px 0;
        box-shadow: 0 6px 20px rgba(0, 0, 0, 0.15);
        text-align: center;
        border: 3px solid #1A237E;
    }}
    .id-digitos {{
        display: flex;
        justify-content: center;
        align-items: center;
        flex-wrap: wrap;
        gap: 6px;
        margin: 10px 0 15px 0;
    }}
    .digito {{
        color: #1A237E;
        font-size: clamp(40px, 9vw, 70px);
        font-weight: 900;
        font-family: 'Courier New', monospace;
        text-align: center;
    }}
    .id-mensaje {{
        color: #1A237E;
        font-size: 13px;
        margin-top: 5px;
        font-weight: 600;
        line-height: 1.4;
    }}
    @media (max-width: 360px) {{
        .id-digitos {{ gap: 4px; }}
    }}
    @media (min-width: 768px) {{
        .id-container {{ padding: 30px 20px; }}
        .id-digitos {{ gap: 8px; }}
    }}
    </style>
    <div class="id-container">
        <div class="id-digitos">
            {' '.join([f'<span class="digito">{{d}}</span>'.replace('{d}', d) for d in digitos])}
        </div>
        <div class="id-mensaje">Escribe este ID en los cupones que entregues a la persona</div>
    </div>
    """
    st.markdown(html_id, unsafe_allow_html=True)


def boton_copiar_id(id_persona: str) -> None:
    """Botón para facilitar copia del ID generado."""
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("📋 Copiar ID", use_container_width=True, type="primary"):
            st.code(id_persona, language=None)
            st.success("ID listo para copiar")


def _obtener_eventos_para_secuencia(fecha_entrevista: str, id_ruta: str, tiene_conexion: bool) -> list[dict]:
    if tiene_conexion:
        return obtener_entrevistas_existentes()

    # En offline, usamos pendientes de sesion para no perder secuencia local.
    pendientes = st.session_state.get("entrevistas_pendientes", []) or []
    salida: list[dict] = []
    for item in pendientes:
        if (
            str(item.get("Fecha_Entrevista", "")).strip() == fecha_entrevista
            and str(item.get("ID_Ruta", "")).strip() == id_ruta
            and item.get("ID_Evento")
        ):
            salida.append(item)
    return salida


_header_sesion_local()
st.title("Nueva Entrevista")

tiene_conexion = verificar_conexion()
if not tiene_conexion:
    banner_sin_conexion()

datos_app = cargar_datos_app()
mostrar_info_cache(datos_app)

_hidratar_perfil_entrevistador_desde_sheets(tiene_conexion)

if not _perfil_entrevistador_completo():
    st.error("Primero debes completar tu perfil de entrevistador en 'Inicio de sesión'")
    st.stop()

inicializar_gps_session_state()
inicializar_fotos_session_state()
solicitar_permiso_gps()
capturar_ubicacion_gps()
mostrar_estado_gps()
st.markdown("---")

st.subheader("Validación")

anos_calle_raw = st.number_input(
    "¿Cuántos años lleva en situación de calle? (aprox.)",
    min_value=0,
    value=0,
    step=1,
    format="%d",
    help="Criterio de validación",
)

anos_calle = int(anos_calle_raw)
personas_conocidas = 0

es_valido = anos_calle >= 1
if es_valido:
    st.success("Validación aceptada")
else:
    st.error("Validación rechazada: debe tener al menos 1 año en situación de calle")

st.markdown("---")

primera_vez_opcion = "Seleccionar..."
if es_valido:
    st.subheader("Pregunta de control")
    primera_vez_opcion = st.selectbox(
        "¿Es la primera vez que realizas esta entrevista? *",
        options=["Seleccionar...", "Sí", "No"],
        index=0,
    )
    if primera_vez_opcion == "No":
        st.info("Continúa con la entrevista :)")

st.markdown("---")

with st.container():
    apellido = ""
    nombre = ""
    alias = ""
    genero = "Desconocido"
    dia_nac = None
    mes_nac = "XXX"
    anio_nac = None
    fecha_nacimiento = None
    edad = None
    sabe_fecha = "No"
    id_referido = ""

    if es_valido:
        st.subheader("Datos de la Persona Entrevistada")

        apellido = st.text_input(
            "Apellido *",
            placeholder="Ingresa el apellido",
            help="Campo obligatorio",
        )

        nombre = st.text_input(
            "Nombre",
            placeholder="Ej. Juan (si no tiene, dejar vacío y usar alias)",
        )

        if nombre.strip() == "":
            alias = st.text_input(
                "Apodo o Alias *",
                placeholder="Ingresa el apodo o alias",
                help="Obligatorio cuando no hay nombre",
            )
            st.info("Como no hay nombre, el apodo/alias es obligatorio")
        else:
            alias = st.text_input(
                "Apodo o Alias (opcional)",
                placeholder="Ingresa el apodo o alias si tiene",
            )

        genero = st.selectbox(
            "Género *",
            options=["Mujer", "Hombre", "No binario", "Desconocido"],
        )

        personas_conocidas = st.number_input(
            "¿Cuántas personas conoce en la misma situación (poblaciones callejeras)?",
            min_value=0,
            value=0,
            step=1,
            format="%d",
        )

        st.markdown("---")
        st.subheader("Fecha de Nacimiento y Edad")

        sabe_fecha = st.radio(
            "¿Se conoce la fecha de nacimiento?",
            options=["Si", "No"],
            horizontal=True,
        )

        if sabe_fecha == "Si":
            col_dia, col_mes, col_anio = st.columns(3)
            with col_dia:
                dia_nac = st.number_input("Dia", min_value=1, max_value=31, value=1, step=1)
            with col_mes:
                mes_nac = st.selectbox("Mes *", options=MESES)
            with col_anio:
                anio_nac = st.number_input(
                    "Anio *",
                    min_value=1900,
                    max_value=datetime.now().year,
                    value=1990,
                    step=1,
                )

            meses_dict = {
                "ENE": 1,
                "FEB": 2,
                "MAR": 3,
                "ABR": 4,
                "MAY": 5,
                "JUN": 6,
                "JUL": 7,
                "AGO": 8,
                "SEP": 9,
                "OCT": 10,
                "NOV": 11,
                "DIC": 12,
            }
            try:
                fecha_nacimiento = date(int(anio_nac), meses_dict[mes_nac], int(dia_nac))
                hoy = date.today()
                edad = hoy.year - fecha_nacimiento.year
                if (hoy.month, hoy.day) < (fecha_nacimiento.month, fecha_nacimiento.day):
                    edad -= 1
                st.info(f"Edad calculada: {edad} años")
            except ValueError:
                st.error("Fecha de nacimiento invalida")
                edad = None
        else:
            edad_aprox_raw = st.text_input(
                "Edad aproximada (años) *",
                placeholder="Ej: 34",
                help="Solo números enteros, sin decimales",
            ).strip()

            if edad_aprox_raw == "":
                edad = None
            elif edad_aprox_raw.isdigit():
                edad = int(edad_aprox_raw)
                if edad < 0 or edad > 120:
                    st.error("La edad aproximada debe estar entre 0 y 120")
                    edad = None
            else:
                st.error("La edad aproximada debe contener solo números enteros (sin decimales)")
                edad = None

            st.warning("Se guardará la edad sin fecha de nacimiento específica")
            mes_nac = "XXX"
            anio_nac = datetime.now().year - int(edad) if edad is not None else None
            dia_nac = None

        st.markdown("---")
        id_referido = mostrar_seccion_referencia(datos_app.get("entrevistas"))

        st.markdown("---")
        st.subheader("Fotografías (Opcional)")

        tab_archivo, tab_camara = st.tabs(["Subir Archivo", "Tomar Foto"])

        with tab_archivo:
            st.write("Selecciona uno o más archivos de imagen:")
            fotos_archivo = st.file_uploader(
                "Seleccionar archivos",
                type=["jpg", "jpeg", "png"],
                accept_multiple_files=True,
                key="file_uploader_fotos",
            )
            if fotos_archivo:
                if st.button("Agregar estas fotos", type="primary", key="guardar_archivos"):
                    for foto in fotos_archivo:
                        agregar_foto(foto, "archivo")
                    st.rerun()

        with tab_camara:
            st.write("Usa la cámara de tu dispositivo para capturar una foto:")
            foto_camara = st.camera_input(
                "Capturar foto",
                key=f"camera_{st.session_state.get('contador_fotos', 0)}",
            )
            if foto_camara is not None:
                if st.button("Agregar esta foto", type="primary", key="guardar_camara"):
                    agregar_foto(foto_camara, "camara")
                    st.rerun()

        st.markdown("---")
        mostrar_galeria_fotos()

    st.markdown("---")
    submitted = st.button(
        "Registrar Entrevista",
        use_container_width=True,
        type="primary",
        disabled=not es_valido or primera_vez_opcion == "Seleccionar...",
    )

    if submitted:
        if not es_valido:
            st.error("No se puede guardar: la validacion no fue aceptada")
            st.stop()

        if primera_vez_opcion == "Seleccionar...":
            st.error("Debes responder si es la primera vez que realizas esta entrevista")
            st.stop()

        if not apellido or apellido.strip() == "":
            st.error("El apellido es obligatorio")
            st.stop()

        if (not nombre or nombre.strip() == "") and (not alias or alias.strip() == ""):
            st.error("Debe ingresar al menos nombre o apodo/alias")
            st.stop()

        if edad is None:
            st.error("La edad es obligatoria y debe ser un número entero sin decimales")
            st.stop()

        if not anio_nac:
            st.error("El año de nacimiento es obligatorio")
            st.stop()

        if sabe_fecha == "Sí" and (not mes_nac or not anio_nac):
            st.error("Mes y año de nacimiento son obligatorios")
            st.stop()

        if id_referido:
            es_valido_ref, msg_ref = validar_formato_id_persona(id_referido)
            if not es_valido_ref:
                st.error(f"Error en ID referido: {msg_ref}")
                st.stop()

        anios_convertidos = float(int(anos_calle))

        fecha_entrevista_dt = date.today()
        fecha_entrevista = _fecha_ddmmyyyy(fecha_entrevista_dt)
        if not fecha_entrevista:
            st.error("La fecha de entrevista es obligatoria")
            st.stop()

        id_ruta = str(st.session_state.get("ruta_id", ""))
        nombre_ruta = str(st.session_state.get("ruta_nombre", ""))

        try:
            id_persona = generar_id_persona(
                genero=genero,
                nombre=nombre,
                apellido=apellido,
                alias=alias,
                mes_nac=mes_nac,
                anio_nac=anio_nac,
            )
        except ValueError as exc:
            st.error(str(exc))
            st.stop()

        entrevistas_existentes = _obtener_eventos_para_secuencia(fecha_entrevista, id_ruta, tiene_conexion)
        id_evento = generar_id_evento(fecha_entrevista, id_ruta, entrevistas_existentes)
        registrar_id_generado(st, id_persona)

        gps_actual = capturar_ubicacion_gps()
        if gps_actual:
            latitud = gps_actual["latitud"]
            longitud = gps_actual["longitud"]
            gps_precision = gps_actual.get("precision")
            gps_timestamp = gps_actual.get("timestamp")
        else:
            latitud = ""
            longitud = ""
            gps_precision = ""
            gps_timestamp = ""
            if st.session_state.get("gps_permiso_aceptado", False):
                st.warning("No se pudo capturar ubicación GPS en este momento. Se guardará sin coordenadas.")

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        datos_entrevista = {
            "ID_Persona": id_persona,
            "Nombre": nombre or "",
            "Alias": alias or "",
            "Edad": int(edad) if edad is not None else "",
            "Genero": genero,
            "ID_Entrevistador": st.session_state.get("entrevistador_id", ""),
            "Nombre_Entrevistador": st.session_state.get("entrevistador_nombre", ""),
            "ID_Ruta": id_ruta,
            "Nombre_Ruta": nombre_ruta,
            "Latitud": latitud if latitud is not None else "",
            "Longitud": longitud if longitud is not None else "",
            "latitud": latitud if latitud is not None else "",
            "longitud": longitud if longitud is not None else "",
            "GPS_Precision": gps_precision if gps_precision is not None else "",
            "GPS_Timestamp": gps_timestamp if gps_timestamp is not None else "",
            "gps_precision": gps_precision if gps_precision is not None else "",
            "gps_timestamp": gps_timestamp if gps_timestamp is not None else "",
            "Fotos_URLs": "",
            "Timestamp": timestamp,
            "Anos_Calle": round(anios_convertidos, 2),
            "Personas_Conocidas": personas_conocidas,
            "ID_Referido": id_referido or "",
            "ID_Evento": id_evento,
            "Apellido": apellido or "",
            "Dia_Nacimiento": dia_nac if dia_nac is not None else "",
            "Mes_Nacimiento": mes_nac,
            "Anio_Nacimiento": int(anio_nac),
            "Fecha_Entrevista": fecha_entrevista,
            "Apellido_Entrevistador": st.session_state.get("apellido_entrevistador", ""),
            "Genero_Entrevistador": st.session_state.get("genero_entrevistador", ""),
            "Dia_Nacimiento_Entrevistador": st.session_state.get("dia_nacimiento_entrevistador", ""),
            "Mes_Nacimiento_Entrevistador": st.session_state.get("mes_nacimiento_entrevistador", ""),
            "Anio_Nacimiento_Entrevistador": st.session_state.get("anio_nacimiento_entrevistador", ""),
            "Fecha_Nacimiento_Entrevistador": st.session_state.get("fecha_nacimiento_entrevistador", ""),
            "CRC": "X" if primera_vez_opcion == "No" else "",
            # Compatibilidad con flujo anterior
            "Nombre_Alias": (nombre or alias or ""),
            "Enlaces_Fotos": "",
            "Numero_Ediciones": 0,
        }

        archivos_fotos = obtener_archivos_para_subir()
        if archivos_fotos and tiene_conexion:
            enlaces_fotos = subir_fotos_drive(
                archivos_fotos,
                id_persona,
                id_ruta,
                fecha_entrevista_dt.strftime("%Y-%m-%d"),
                nombre_persona=(nombre or alias or ""),
                id_entrevistador=st.session_state.get("entrevistador_id", ""),
                nombre_entrevistador=st.session_state.get("entrevistador_nombre", ""),
                nombre_ruta=st.session_state.get("ruta_nombre", ""),
            )
            if len(enlaces_fotos) != len(archivos_fotos):
                st.error(
                    "No se pudieron subir todas las fotos a Google Drive. "
                    "La entrevista no se guardó para evitar datos incompletos."
                )
                st.stop()
            urls = ",".join(enlaces_fotos)
            datos_entrevista["Fotos_URLs"] = urls
            datos_entrevista["Enlaces_Fotos"] = urls

        if tiene_conexion:
            ok = subir_entrevista_sheets(datos_entrevista)
            if ok:
                st.success("Entrevista guardada correctamente")
                mostrar_id_persona(id_persona)
                limpiar_fotos()
            else:
                st.error("No se pudo guardar en línea")
        else:
            fotos_base64 = []
            for foto in st.session_state.get("fotos_capturadas", []):
                foto_bytes = foto.get("bytes") or b""
                if not foto_bytes:
                    continue
                foto_b64 = base64.b64encode(foto_bytes).decode()
                fotos_base64.append({"nombre": foto.get("nombre", "foto.jpg"), "data": foto_b64})

            datos_entrevista["fotos_base64"] = fotos_base64
            if "entrevistas_pendientes" not in st.session_state:
                st.session_state.entrevistas_pendientes = []
            st.session_state.entrevistas_pendientes.append(datos_entrevista)

            st.warning("Sin conexión: entrevista guardada localmente")
            mostrar_id_persona(id_persona)
            st.info(f"ID Evento: {id_evento}")
            limpiar_fotos()
```
