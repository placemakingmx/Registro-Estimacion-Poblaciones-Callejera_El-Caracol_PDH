"""
Manejador de Google Sheets mediante gspread.

Requiere en st.secrets (secrets.toml):
    [gcp_service_account]
    type = "service_account"
    project_id = "..."
    private_key_id = "..."
    private_key = "..."
    client_email = "..."
    ...

    [sheets]
    spreadsheet_id = "1ABC..."
    worksheet_name = "Entrevistas"
"""
from __future__ import annotations

import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from typing import Optional
from datetime import datetime


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]


def _norm(value) -> str:
    return str(value or "").strip()


def _disponible_en_ruta(row: dict) -> bool:
    cand = _norm(row.get("Disponibilidad")).lower()
    return cand == "x"


def _consolidar_entrevistadores(entrevistas_raw: list[dict]) -> dict:
    entrevistadores: dict[str, dict] = {}
    for reg in entrevistas_raw:
        id_ent = _norm(reg.get("ID_Entrevistador"))
        if not id_ent:
            continue

        actual = entrevistadores.get(id_ent, {"id": id_ent})
        actual["nombre_completo"] = _norm(reg.get("Nombre_Entrevistador")) or actual.get("nombre_completo", "")
        actual["apellido"] = _norm(reg.get("Apellido_Entrevistador")) or actual.get("apellido", "")
        actual["genero"] = _norm(reg.get("Genero_Entrevistador")) or actual.get("genero", "")
        actual["dia_nacimiento"] = _norm(reg.get("Dia_Nacimiento_Entrevistador")) or actual.get("dia_nacimiento", "")
        actual["mes_nacimiento"] = _norm(reg.get("Mes_Nacimiento_Entrevistador")) or actual.get("mes_nacimiento", "")
        actual["anio_nacimiento"] = _norm(reg.get("Anio_Nacimiento_Entrevistador")) or actual.get("anio_nacimiento", "")
        actual["fecha_nacimiento"] = _norm(reg.get("Fecha_Nacimiento_Entrevistador")) or actual.get("fecha_nacimiento", "")
        entrevistadores[id_ent] = actual
    return entrevistadores


@st.cache_data(ttl=300)
def cargar_datos_app() -> dict:
    """Carga entrevistas y rutas en una sola ejecución con caché de 5 minutos."""
    try:
        client = get_gspread_client()
        sheets_cfg = st.secrets.get("sheets", {})
        spreadsheet_id = sheets_cfg.get("spreadsheet_id")
        spreadsheet_name = sheets_cfg.get("spreadsheet_name", "NOMBRE_DE_TU_SPREADSHEET")

        sh = client.open_by_key(spreadsheet_id) if spreadsheet_id else client.open(spreadsheet_name)
        entrevistas_raw = sh.worksheet("Entrevistas").get_all_records()
        rutas_raw = sh.worksheet("Rutas").get_all_records()

        rutas_disponibles = [
            {
                "id": _norm(r.get("ID_Ruta") or r.get("id") or r.get("Ruta_ID")),
                "nombre": _norm(r.get("Nombre_Ruta") or r.get("Ruta") or r.get("nombre")),
                "link": _norm(r.get("GoogleMaps_Link") or r.get("Link") or r.get("Mapa") or ""),
                "raw": r,
            }
            for r in rutas_raw
            if _norm(r.get("ID_Ruta") or r.get("id") or r.get("Ruta_ID")) and _disponible_en_ruta(r)
        ]
        rutas_disponibles.sort(key=lambda x: ((x["nombre"] or "").lower(), x["id"]))

        return {
            "entrevistas": entrevistas_raw,
            "rutas": rutas_disponibles,
            "entrevistadores": _consolidar_entrevistadores(entrevistas_raw),
            "timestamp": datetime.now(),
            "exito": True,
        }
    except Exception as exc:
        return {
            "entrevistas": [],
            "rutas": [],
            "entrevistadores": {},
            "timestamp": None,
            "exito": False,
            "error": str(exc),
        }


def refrescar_cache(rerun: bool = False) -> None:
    """Limpia caché de datos y opcionalmente relanza la app."""
    st.cache_data.clear()
    if rerun:
        st.rerun()


def mostrar_info_cache(datos: dict) -> None:
    """Muestra el estado del caché en la barra lateral."""
    if not datos or not datos.get("timestamp"):
        return

    edad = datetime.now() - datos["timestamp"]
    minutos = int(edad.total_seconds() / 60)
    segundos = int(edad.total_seconds() % 60)

    with st.sidebar:
        st.divider()
        st.caption("Estado de datos")
        if minutos == 0:
            st.caption(f"Actualizados hace {segundos}s")
        else:
            st.caption(f"Actualizados hace {minutos}min {segundos}s")
        st.caption(f"Entrevistas: {len(datos.get('entrevistas', []))}")
        st.caption(f"Rutas: {len(datos.get('rutas', []))}")
        st.caption(f"Entrevistadores: {len(datos.get('entrevistadores', {}))}")
        if st.button("Refrescar datos", use_container_width=True):
            refrescar_cache(rerun=True)


@st.cache_resource(show_spinner=False)
def get_gspread_client() -> gspread.Client:
    """
    Crea y cachea el cliente de gspread usando las credenciales de st.secrets.

    Returns:
        Cliente autenticado de gspread.

    Raises:
        KeyError: Si las credenciales no están configuradas en secrets.
    """
    creds_dict = dict(st.secrets["gcp_service_account"])
    credentials = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return gspread.authorize(credentials)


def get_worksheet() -> gspread.Worksheet:
    """
    Devuelve la hoja de cálculo configurada en secrets.

    Returns:
        Objeto Worksheet listo para leer/escribir.
    """
    client = get_gspread_client()
    spreadsheet_id = st.secrets["sheets"]["spreadsheet_id"]
    worksheet_name = st.secrets["sheets"].get("worksheet_name", "Entrevistas")
    sh = client.open_by_key(spreadsheet_id)
    return sh.worksheet(worksheet_name)


def append_record(record: dict) -> bool:
    """
    Agrega un registro al final de la hoja.

    Args:
        record: Diccionario con los datos del registro.  Las claves deben
                coincidir con los encabezados de la hoja.

    Returns:
        True si la operación fue exitosa, False en caso contrario.
    """
    try:
        ws = get_worksheet()
        headers = ws.row_values(1)
        row = [str(record.get(h, "")) for h in headers]
        ws.append_row(row, value_input_option="USER_ENTERED")
        refrescar_cache()
        return True
    except Exception as exc:
        st.error(f"Error al guardar en Google Sheets: {exc}")
        return False


def get_all_records() -> pd.DataFrame:
    """
    Descarga todos los registros de la hoja como DataFrame.

    Returns:
        DataFrame con todos los registros; DataFrame vacío si falla.
    """
    try:
        data = cargar_datos_app().get("entrevistas", [])
        return pd.DataFrame(data)
    except Exception as exc:
        st.error(f"Error al leer Google Sheets: {exc}")
        return pd.DataFrame()


def obtener_entrevistas_existentes() -> list[dict]:
    """Obtiene todos los registros crudos de la hoja Entrevistas."""
    datos = cargar_datos_app()
    if not datos.get("exito"):
        return []
    return datos.get("entrevistas", [])


def obtener_datos_entrevistador_por_id(id_entrevistador: str) -> dict:
    """
    Recupera los datos de perfil del entrevistador desde entrevistas previas.

    Busca por ID_Entrevistador y toma el valor no vacio mas reciente para cada campo.
    """
    target = _norm(id_entrevistador)
    if not target:
        return {}

    records = obtener_entrevistas_existentes()

    campos = {
        "ID_Entrevistador": "id",
        "Nombre_Entrevistador": "nombre",
        "Apellido_Entrevistador": "apellido",
        "Genero_Entrevistador": "genero",
        "Dia_Nacimiento_Entrevistador": "dia_nacimiento",
        "Mes_Nacimiento_Entrevistador": "mes_nacimiento",
        "Anio_Nacimiento_Entrevistador": "anio_nacimiento",
        "Fecha_Nacimiento_Entrevistador": "fecha_nacimiento",
    }

    datos = {v: "" for v in campos.values()}
    datos["id"] = target

    for row in reversed(records):
        if _norm(row.get("ID_Entrevistador")) != target:
            continue
        for col, key in campos.items():
            if datos[key]:
                continue
            val = _norm(row.get(col))
            if val:
                datos[key] = val
        if all(datos[k] for k in ["nombre", "apellido", "genero", "dia_nacimiento", "mes_nacimiento", "anio_nacimiento", "fecha_nacimiento"]):
            break

    return datos


def update_record(row_index: int, record: dict) -> bool:
    """
    Actualiza una fila existente (1-indexado, sin contar el encabezado).

    Args:
        row_index: Número de fila de datos (1 = primera fila de datos).
        record: Diccionario con los valores actualizados.

    Returns:
        True si la operación fue exitosa, False en caso contrario.
    """
    try:
        ws = get_worksheet()
        headers = ws.row_values(1)
        # La fila real en la hoja incluye el encabezado en fila 1
        sheet_row = row_index + 1
        row = [str(record.get(h, "")) for h in headers]
        cell_range = f"A{sheet_row}:{chr(64 + len(headers))}{sheet_row}"
        ws.update(cell_range, [row])
        refrescar_cache()
        return True
    except Exception as exc:
        st.error(f"Error al actualizar Google Sheets: {exc}")
        return False


def find_record_by_id(record_id: str) -> Optional[tuple[int, dict]]:
    """
    Busca un registro por su ID único.

    Args:
        record_id: ID a buscar (columna 'id_registro').

    Returns:
        Tupla (row_index, record_dict) o None si no se encuentra.
    """
    try:
        ws = get_worksheet()
        cell = ws.find(record_id)
        if cell is None:
            return None
        headers = ws.row_values(1)
        row_values = ws.row_values(cell.row)
        record = dict(zip(headers, row_values))
        return (cell.row - 1, record)  # row_index apunta a la fila de datos
    except Exception:
        return None


def subir_entrevista_sheets(datos_entrevista: dict) -> bool:
    """Wrapper en espanol para guardar entrevista en Google Sheets."""
    return append_record(datos_entrevista)


def buscar_en_sheets(termino_busqueda: str) -> list[dict]:
    """Busca registros por ID, nombre o alias en Google Sheets."""
    termino = _norm(termino_busqueda).lower()
    if not termino:
        return []

    df = get_all_records()
    if df.empty:
        return []

    resultados: list[dict] = []
    for _, row in df.iterrows():
        record = row.to_dict()
        id_persona = _norm(record.get("ID_Persona") or record.get("id_registro"))
        nombre_alias = _norm(
            record.get("Nombre_Alias")
            or record.get("Alias")
            or record.get("Nombre")
            or record.get("nombre")
        )

        if termino in id_persona.lower() or termino in nombre_alias.lower():
            resultados.append(
                {
                    "ID_Persona": id_persona,
                    "Nombre_Alias": nombre_alias,
                    "Edad": _norm(record.get("Edad") or record.get("edad_estimada")),
                    "Genero": _norm(record.get("Genero") or record.get("sexo")),
                    "Anos_Calle": _norm(record.get("Anos_Calle") or record.get("tiempo_calle")),
                    "Personas_Conocidas": _norm(
                        record.get("Personas_Conocidas") or record.get("personas_conocidas")
                    ),
                    "ID_Entrevistador": _norm(
                        record.get("ID_Entrevistador") or record.get("capturista")
                    ),
                    "ID_Ruta": _norm(record.get("ID_Ruta") or record.get("ruta_id")),
                    "Latitud": _norm(record.get("Latitud") or record.get("latitud")),
                    "Longitud": _norm(record.get("Longitud") or record.get("longitud")),
                    "Timestamp": _norm(record.get("Timestamp") or record.get("fecha")),
                    "Enlaces_Fotos": _norm(
                        record.get("Enlaces_Fotos")
                        or record.get("Fotos_URLs")
                        or record.get("enlaces_fotos")
                    ),
                    "Numero_Ediciones": _norm(
                        record.get("Numero_Ediciones") or record.get("numero_ediciones") or "0"
                    ),
                }
            )

    return resultados


def obtener_registro_completo(id_persona: str) -> dict | None:
    """Obtiene el registro completo por ID de persona."""
    target = _norm(id_persona)
    if not target:
        return None

    df = get_all_records()
    if df.empty:
        return None

    for _, row in df.iterrows():
        record = row.to_dict()
        current_id = _norm(record.get("ID_Persona") or record.get("id_registro"))
        if current_id == target:
            return record
    return None


def _col_to_letter(col_idx: int) -> str:
    """Convierte indice de columna (1-based) a letra A1 (A, B, ..., AA)."""
    result = ""
    while col_idx > 0:
        col_idx, rem = divmod(col_idx - 1, 26)
        result = chr(65 + rem) + result
    return result


def actualizar_registro_sheets(id_persona: str, cambios: dict) -> bool:
    """Actualiza un registro por ID de persona/id_registro aplicando solo los cambios recibidos."""
    try:
        ws = get_worksheet()
        headers = ws.row_values(1)
        records = ws.get_all_records()

        row_sheet = None
        current_record = None
        for idx, record in enumerate(records, start=2):
            current_id = _norm(record.get("ID_Persona") or record.get("id_registro"))
            if current_id == _norm(id_persona):
                row_sheet = idx
                current_record = record
                break

        if row_sheet is None or current_record is None:
            return False

        updated = dict(current_record)
        for key, value in cambios.items():
            updated[key] = value

        row = [str(updated.get(h, "")) for h in headers]
        end_col = _col_to_letter(len(headers))
        ws.update(f"A{row_sheet}:{end_col}{row_sheet}", [row])
        refrescar_cache()
        return True
    except Exception as exc:
        st.error(f"Error al actualizar registro en Sheets: {exc}")
        return False
