"""
El Caracol - Sistema de Registro de Poblaciones Callejeras
Pantalla de Inicio de la aplicación.
"""
from pathlib import Path
from typing import Optional

import streamlit as st
import streamlit.components.v1 as components

from utils.id_generator import (
    generar_id_entrevistador,
    inicializar_session_ids,
)
from utils.connectivity import verificar_conexion
from utils.sheets_handler import (
    cargar_datos_app,
    get_gspread_client,
    mostrar_info_cache,
    refrescar_cache,
)

# ── Configuración de página ───────────────────────────────────────────────────
st.set_page_config(
    page_title="Inicio",
    page_icon="🐌",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Estilos mobile-first ──────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    /* Ocultar elementos de navegación por defecto de Streamlit */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* Fondo y tipografía */
    .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
        max-width: 480px;
        margin: 0 auto;
    }

    /* Tarjeta de bienvenida */
    .welcome-card {
        background-color: #1E3A8A;
        color: white;
        padding: 1.5rem;
        border-radius: 12px;
        text-align: center;
        margin-bottom: 1.5rem;
    }

    /* Botones de navegación */
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

# ── PWA ───────────────────────────────────────────────────────────────────────
def inject_pwa() -> None:
    """Inyecta las etiquetas necesarias para registrar el Service Worker y el manifest PWA."""
    pwa_html = """
    <link rel="manifest" href="/static/manifest.json">
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="theme-color" content="#1E3A8A">
    <link rel="apple-touch-icon" href="/static/logo_caracol_192.png">
    """
    components.html(pwa_html, height=0)


inject_pwa()


def _mostrar_aviso_secrets_faltantes() -> None:
    """Muestra un unico aviso cuando no existe configuracion de secrets."""
    if st.session_state.get("_aviso_secrets_mostrado"):
        return

    st.warning(
        "No se encontro secrets.toml. El login se abrira en modo local sin cargar "
        "entrevistadores/rutas desde Google Sheets."
    )
    st.info(
        "Agrega el archivo en una de estas rutas: .streamlit/secrets.toml o "
        "app/.streamlit/secrets.toml"
    )
    st.session_state._aviso_secrets_mostrado = True


def _secrets_disponibles() -> bool:
    """Valida que existan secrets y parametros minimos para abrir Sheets."""
    try:
        has_sa = "gcp_service_account" in st.secrets
        has_sheets = "sheets" in st.secrets
        return bool(has_sa and has_sheets)
    except FileNotFoundError:
        return False


def _open_spreadsheet():
    """Abre el spreadsheet principal usando secrets configurados."""
    if not _secrets_disponibles():
        _mostrar_aviso_secrets_faltantes()
        return None

    try:
        client = get_gspread_client()
        sheets_cfg = st.secrets.get("sheets", {})
        spreadsheet_id = sheets_cfg.get("spreadsheet_id")
        spreadsheet_name = sheets_cfg.get("spreadsheet_name", "NOMBRE_DE_TU_SPREADSHEET")

        if spreadsheet_id:
            return client.open_by_key(spreadsheet_id)
        return client.open(spreadsheet_name)
    except FileNotFoundError:
        _mostrar_aviso_secrets_faltantes()
        return None


def cargar_entrevistadores_existentes() -> list[dict]:
    """
    Carga entrevistadores unicos desde caché de Entrevistas.
    """
    datos = cargar_datos_app()
    entrevistadores_dict = datos.get("entrevistadores", {})

    entrevistadores = [
        {
            "id": eid,
            "nombre": info.get("nombre_completo", ""),
            "apellido": info.get("apellido", ""),
            "genero": info.get("genero", ""),
            "dia_nacimiento": info.get("dia_nacimiento", ""),
            "mes_nacimiento": info.get("mes_nacimiento", ""),
            "anio_nacimiento": info.get("anio_nacimiento", ""),
            "fecha_nacimiento": info.get("fecha_nacimiento", ""),
            "rol": "capturista",
        }
        for eid, info in entrevistadores_dict.items()
    ]

    if entrevistadores:
        entrevistadores.sort(key=lambda x: ((x["nombre"] or "").lower(), x["id"]))
        return entrevistadores

    # Fallback: si no hay entrevistas previas, intenta cargar usuarios desde hojas de catalogo.
    if not _secrets_disponibles():
        return []

    def _first_non_empty(row: dict, keys: list[str]) -> str:
        for key in keys:
            value = str(row.get(key, "") or "").strip()
            if value:
                return value
        return ""

    posibles_hojas = [
        "Entrevistadores",
        "Usuarios",
        "Admins",
        "Administradores",
    ]

    usuarios_por_id: dict[str, dict] = {}
    sh = _open_spreadsheet()
    if sh is None:
        return []

    for hoja in posibles_hojas:
        try:
            records = sh.worksheet(hoja).get_all_records()
        except Exception:
            continue

        for row in records:
            user_id = _first_non_empty(row, ["ID_Entrevistador", "ID", "id", "Id"])
            if not user_id:
                continue

            nombre = _first_non_empty(row, ["Nombre_Entrevistador", "Nombre", "nombre"])
            apellido = _first_non_empty(row, ["Apellido_Entrevistador", "Apellido", "apellido"])
            genero = _first_non_empty(row, ["Genero_Entrevistador", "Genero", "genero"])
            rol = _first_non_empty(row, ["Rol", "rol", "Perfil", "perfil", "Tipo", "tipo"]).lower()
            if rol not in {"admin", "administrador"}:
                rol = "capturista"
            else:
                rol = "admin"

            usuarios_por_id[user_id] = {
                "id": user_id,
                "nombre": f"{nombre} {apellido}".strip() or nombre or user_id,
                "apellido": apellido,
                "genero": genero,
                "dia_nacimiento": "",
                "mes_nacimiento": "",
                "anio_nacimiento": "",
                "fecha_nacimiento": "",
                "rol": rol,
            }

    entrevistadores = list(usuarios_por_id.values())
    entrevistadores.sort(key=lambda x: ((x["nombre"] or "").lower(), x["id"]))
    return entrevistadores


def cargar_rutas_existentes() -> list[dict]:
    """
    Carga rutas disponibles desde caché de hoja Rutas.
    """
    rutas = cargar_datos_app().get("rutas", [])
    if rutas:
        return rutas

    # Fallback: si la cache no trae rutas (p.ej. filtro de disponibilidad/encabezados distintos),
    # leer Rutas directo y aceptar variaciones de columnas.
    if not _secrets_disponibles():
        return []

    sh = _open_spreadsheet()
    if sh is None:
        return []

    try:
        rutas_raw = sh.worksheet("Rutas").get_all_records()
    except Exception:
        return []

    rutas_ok: list[dict] = []
    for row in rutas_raw:
        rid = str(
            row.get("ID_Ruta")
            or row.get("id")
            or row.get("Ruta_ID")
            or ""
        ).strip()
        nombre = str(
            row.get("Nombre_Ruta")
            or row.get("Ruta")
            or row.get("nombre")
            or ""
        ).strip()
        if not rid:
            continue

        disp = str(row.get("Disponibilidad", "") or "").strip().lower()
        if disp and disp not in {"x", "si", "sí", "1", "true", "activa", "activo"}:
            continue

        rutas_ok.append(
            {
                "id": rid,
                "nombre": nombre or rid,
                "link": str(
                    row.get("GoogleMaps_Link")
                    or row.get("Link")
                    or row.get("Mapa")
                    or ""
                ).strip(),
            }
        )

    rutas_ok.sort(key=lambda x: ((x["nombre"] or "").lower(), x["id"]))
    return rutas_ok


def inicializar_sesion() -> None:
    """Inicializa llaves necesarias de session_state para login y ruta."""
    inicializar_session_ids(st)

    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "entrevistador_id" not in st.session_state:
        st.session_state.entrevistador_id = None
    if "entrevistador_nombre" not in st.session_state:
        st.session_state.entrevistador_nombre = None
    if "ruta_id" not in st.session_state:
        st.session_state.ruta_id = None
    if "ruta_nombre" not in st.session_state:
        st.session_state.ruta_nombre = None
    if "ruta_link" not in st.session_state:
        st.session_state.ruta_link = None
    if "ruta_coords" not in st.session_state:
        st.session_state.ruta_coords = None
    if "usuario_id" not in st.session_state:
        st.session_state.usuario_id = None
    if "usuario_nombre" not in st.session_state:
        st.session_state.usuario_nombre = None
    if "logueado" not in st.session_state:
        st.session_state.logueado = False

    # Compatibilidad con paginas ya creadas en Fase 1.
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "username" not in st.session_state:
        st.session_state.username = None
    if "user_role" not in st.session_state:
        st.session_state.user_role = "capturista"
    if "apellido_entrevistador" not in st.session_state:
        st.session_state.apellido_entrevistador = None
    if "genero_entrevistador" not in st.session_state:
        st.session_state.genero_entrevistador = None
    if "dia_nacimiento_entrevistador" not in st.session_state:
        st.session_state.dia_nacimiento_entrevistador = None
    if "mes_nacimiento_entrevistador" not in st.session_state:
        st.session_state.mes_nacimiento_entrevistador = None
    if "anio_nacimiento_entrevistador" not in st.session_state:
        st.session_state.anio_nacimiento_entrevistador = None
    if "fecha_nacimiento_entrevistador" not in st.session_state:
        st.session_state.fecha_nacimiento_entrevistador = None

    # Estado GPS de la sesión (permiso una sola vez por sesión activa).
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


_NUEVO_ENTREVISTADOR = "+ Registrar nuevo/a entrevistador/a"
_NUEVA_RUTA = "+ Registrar nueva ruta"


def pagina_login() -> None:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        logo_path = Path(__file__).resolve().parent / "static" / "logo_caracol.png"
        if logo_path.exists():
            st.image(str(logo_path), width=50)
    
    st.title("El Caracol - Inicio")

    st.markdown("---")

    tiene_conexion = verificar_conexion()
    if not tiene_conexion:
        st.warning("Sin conexión a internet - Modo offline activado")

    entrevistadores = cargar_entrevistadores_existentes()
    rutas = cargar_rutas_existentes()
    mostrar_info_cache(cargar_datos_app())

    # ── Entrevistador ────────────────────────────────────────────────────────
    st.markdown("### Entrevistador/a")

    nombres_entrevistadores = [f"{e['nombre']} ({e['id']})" for e in entrevistadores] + [_NUEVO_ENTREVISTADOR]
    entrevistador_sel_nombre = st.selectbox(
        "Selecciona tu nombre",
        options=nombres_entrevistadores,
        key="login_sel_entrevistador",
    )

    selected_entrevistador_id: Optional[str] = None
    selected_entrevistador_nombre: Optional[str] = None
    selected_entrevistador_apellido: Optional[str] = None
    selected_entrevistador_genero: Optional[str] = None
    selected_entrevistador_dia_nac: Optional[int] = None
    selected_entrevistador_mes_nac: Optional[str] = None
    selected_entrevistador_anio_nac: Optional[int] = None
    selected_entrevistador_fecha_nac: Optional[str] = None
    selected_user_role: str = "capturista"

    if entrevistador_sel_nombre == _NUEVO_ENTREVISTADOR:
        st.info("Completa tu perfil para generar tu ID de entrevistador")

        genero_nuevo = st.selectbox(
            "Género*",
            options=["Mujer", "Hombre", "No binario"],
            key="login_nuevo_entrevistador_genero",
        )
        nombre_nuevo = st.text_input("Nombre(s)*", key="login_nuevo_entrevistador_nombre").strip()
        apellido_nuevo = st.text_input("Apellido(s)*", key="login_nuevo_entrevistador_apellido").strip()

        c1, c2, c3 = st.columns(3)
        with c1:
            dia_nac_nuevo = st.selectbox(
                "Día*",
                options=[""] + [str(i) for i in range(1, 32)],
                key="login_nuevo_entrevistador_dia",
            )
        with c2:
            mes_nac_nuevo = st.selectbox(
                "Mes*",
                options=["Seleccionar...", "ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"],
                key="login_nuevo_entrevistador_mes",
            )
        with c3:
            anio_nac_nuevo_txt = st.text_input("Año*", key="login_nuevo_entrevistador_anio")

        anio_nac_nuevo = None
        if anio_nac_nuevo_txt.strip().isdigit():
            anio_nac_nuevo = int(anio_nac_nuevo_txt.strip())

        if nombre_nuevo and apellido_nuevo and dia_nac_nuevo and mes_nac_nuevo != "Seleccionar..." and anio_nac_nuevo:
            try:
                selected_entrevistador_id = generar_id_entrevistador(
                    genero=genero_nuevo,
                    nombre=nombre_nuevo,
                    apellido=apellido_nuevo,
                    mes_nac=mes_nac_nuevo,
                    anio_nac=anio_nac_nuevo,
                )
                st.success(f"ID generado: {selected_entrevistador_id}")
            except ValueError as exc:
                st.error(str(exc))

        selected_entrevistador_nombre = f"{nombre_nuevo} {apellido_nuevo}".strip()
        selected_entrevistador_apellido = apellido_nuevo
        selected_entrevistador_genero = genero_nuevo
        selected_entrevistador_dia_nac = int(dia_nac_nuevo) if dia_nac_nuevo else None
        selected_entrevistador_mes_nac = mes_nac_nuevo if mes_nac_nuevo != "Seleccionar..." else None
        selected_entrevistador_anio_nac = anio_nac_nuevo
        if selected_entrevistador_dia_nac and selected_entrevistador_mes_nac and selected_entrevistador_anio_nac:
            selected_entrevistador_fecha_nac = (
                f"{selected_entrevistador_dia_nac:02d}/{selected_entrevistador_mes_nac}/{selected_entrevistador_anio_nac}"
            )
    else:
        match = next(
            (e for e in entrevistadores if f"{e['nombre']} ({e['id']})" == entrevistador_sel_nombre),
            None,
        )
        if match:
            selected_entrevistador_id = match["id"]
            selected_entrevistador_nombre = match["nombre"]
            selected_entrevistador_apellido = match.get("apellido")
            selected_entrevistador_genero = match.get("genero")
            selected_entrevistador_dia_nac = int(match["dia_nacimiento"]) if str(match.get("dia_nacimiento", "")).isdigit() else None
            selected_entrevistador_mes_nac = match.get("mes_nacimiento")
            selected_entrevistador_anio_nac = int(match["anio_nacimiento"]) if str(match.get("anio_nacimiento", "")).isdigit() else None
            selected_entrevistador_fecha_nac = match.get("fecha_nacimiento")
            selected_user_role = str(match.get("rol", "capturista") or "capturista")

    # ── Ruta ─────────────────────────────────────────────────────────────────
    st.markdown("### Ruta")

    nombres_rutas = [r["nombre"] for r in rutas] + [_NUEVA_RUTA]
    ruta_sel_nombre = st.selectbox(
        "Selecciona la ruta",
        options=nombres_rutas,
        key="login_sel_ruta",
    )

    selected_ruta_id: Optional[str] = None
    selected_ruta_nombre: Optional[str] = None
    selected_ruta_link: Optional[str] = None

    if ruta_sel_nombre == _NUEVA_RUTA:
        id_ruta_manual = st.text_input(
            "ID_Ruta (manual)*",
            key="login_nueva_ruta_id",
            placeholder="Ej: R01",
        ).strip()
        nombre_ruta_nueva = st.text_input(
            "Nombre de la ruta",
            key="login_nueva_ruta_nombre",
            placeholder="Ej: Centro Historico",
        ).strip()
        link_ruta_nueva = st.text_input(
            "Google Maps link (opcional)",
            key="login_nueva_ruta_link",
            placeholder="https://maps.google.com/...",
        ).strip()
        selected_ruta_id = id_ruta_manual
        selected_ruta_nombre = nombre_ruta_nueva
        selected_ruta_link = link_ruta_nueva or None
    else:
        match_ruta = next((r for r in rutas if r["nombre"] == ruta_sel_nombre), None)
        if match_ruta:
            selected_ruta_id = match_ruta["id"]
            selected_ruta_nombre = match_ruta["nombre"]
            selected_ruta_link = match_ruta["link"] or None

    st.markdown("---")
    if st.button("Iniciar sesión", use_container_width=True, type="primary"):
        if not selected_entrevistador_id:
            st.error("Debes seleccionar o registrar un entrevistador.")
            return
        if not selected_entrevistador_nombre:
            st.error("El nombre del entrevistador es obligatorio.")
            return
        if not selected_ruta_id:
            st.error("Debes seleccionar o registrar una ruta.")
            return
        if not selected_ruta_nombre:
            st.error("El nombre de la ruta es obligatorio.")
            return

        if entrevistador_sel_nombre == _NUEVO_ENTREVISTADOR:
            ids_existentes = {e["id"] for e in entrevistadores}
            if selected_entrevistador_id in ids_existentes:
                st.error(f"El ID {selected_entrevistador_id} ya existe en el sistema")
                return
            if not selected_entrevistador_apellido or not selected_entrevistador_genero:
                st.error("Completa apellido y genero del entrevistador")
                return
            if not selected_entrevistador_dia_nac or not selected_entrevistador_mes_nac or not selected_entrevistador_anio_nac:
                st.error("La fecha de nacimiento completa del entrevistador es obligatoria")
                return

        if ruta_sel_nombre == _NUEVA_RUTA:
            if not _secrets_disponibles():
                st.error(
                    "No se puede registrar la nueva ruta en Google Sheets porque falta secrets.toml."
                )
                return
            try:
                sh = _open_spreadsheet()
                if sh is None:
                    st.error(
                        "No se puede registrar la nueva ruta en Google Sheets porque falta configuracion."
                    )
                    return
                ws_rutas = sh.worksheet("Rutas")
                ws_rutas.append_row(
                    [selected_ruta_id, selected_ruta_nombre, selected_ruta_link or ""],
                    value_input_option="USER_ENTERED",
                )
                refrescar_cache()
            except Exception as exc:
                st.error(f"No se pudo registrar la nueva ruta en Google Sheets: {exc}")
                return

        st.session_state.usuario_id = selected_entrevistador_id
        st.session_state.usuario_nombre = selected_entrevistador_nombre
        st.session_state.ruta_id = selected_ruta_id
        st.session_state.ruta_nombre = selected_ruta_nombre
        st.session_state.ruta_link = selected_ruta_link
        st.session_state.logueado = True

        # Compatibilidad con llaves existentes.
        st.session_state.logged_in = True
        st.session_state.entrevistador_id = selected_entrevistador_id
        st.session_state.entrevistador_nombre = selected_entrevistador_nombre
        st.session_state.authenticated = True
        st.session_state.username = selected_entrevistador_nombre
        st.session_state.user_role = selected_user_role
        st.session_state.apellido_entrevistador = selected_entrevistador_apellido
        st.session_state.genero_entrevistador = selected_entrevistador_genero
        st.session_state.dia_nacimiento_entrevistador = selected_entrevistador_dia_nac
        st.session_state.mes_nacimiento_entrevistador = selected_entrevistador_mes_nac
        st.session_state.anio_nacimiento_entrevistador = selected_entrevistador_anio_nac
        st.session_state.fecha_nacimiento_entrevistador = selected_entrevistador_fecha_nac

        st.success(
            f"Sesión iniciada como {selected_entrevistador_nombre} en la ruta {selected_ruta_nombre}"
        )
        st.rerun()


def header_sesion() -> None:
    """Mostrar header con info de sesion en todas las paginas."""
    if st.session_state.logged_in:
        st.markdown(
            f"""
            <div style='background-color: #1E3A8A; padding: 10px; border-radius: 5px; color: white;'>
                <strong>{st.session_state.entrevistador_nombre}</strong> |
                ID: {st.session_state.entrevistador_id} |
                Ruta: {st.session_state.ruta_id}
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.session_state.ruta_link:
            st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
            if st.button(
                "Abrir mapa en Google Maps",
                use_container_width=True,
                type="primary",
                key="btn_mapa_inicio",
            ):
                safe_url = str(st.session_state.ruta_link).replace("'", "%27")
                components.html(
                    f"<script>window.open('{safe_url}', '_blank');</script>",
                    height=0,
                )
            st.markdown("<div style='height: 6px;'></div>", unsafe_allow_html=True)

        st.markdown("---")


def contenido_principal() -> None:
    """Pantalla de Inicio una vez iniciada la sesión."""
    st.markdown("### ¿Que deseas hacer?")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Nueva Entrevista"):
            st.switch_page("pages/1_nueva_entrevista.py")
        if st.button("Buscar / Editar"):
            st.switch_page("pages/2_buscar_editar.py")

    with col2:
        if st.button("Pendientes"):
            st.switch_page("pages/3_pendientes_sincronizar.py")
        if st.button("Dashboard Admin"):
            st.switch_page("pages/4_dashboard_admin.py")

    st.divider()
    if st.button("Cerrar sesión", type="secondary"):
        for key in [
            "logged_in",
            "entrevistador_id",
            "entrevistador_nombre",
            "ruta_id",
            "ruta_nombre",
            "ruta_link",
            "usuario_id",
            "usuario_nombre",
            "logueado",
            "authenticated",
            "username",
            "user_role",
            "apellido_entrevistador",
            "genero_entrevistador",
            "dia_nacimiento_entrevistador",
            "mes_nacimiento_entrevistador",
            "anio_nacimiento_entrevistador",
            "fecha_nacimiento_entrevistador",
            "gps_permiso_solicitado",
            "gps_permiso_aceptado",
            "gps_intentando_permiso",
            "gps_latitud",
            "gps_longitud",
            "gps_precision",
            "gps_timestamp",
        ]:
            st.session_state[key] = None
        st.session_state.logged_in = False
        st.session_state.logueado = False
        st.session_state.authenticated = False
        st.rerun()


inicializar_sesion()

if not st.session_state.logged_in:
    pagina_login()
else:
    header_sesion()
    contenido_principal()
