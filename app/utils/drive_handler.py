"""
Manejador de Google Drive para subir/descargar archivos (fotos, exportaciones).

Requiere las mismas credenciales de st.secrets que sheets_handler.

Uso:
    from utils.drive_handler import upload_file, get_file_url
"""
from __future__ import annotations

import io
import json
import streamlit as st
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from googleapiclient.errors import HttpError


SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
]


def _extraer_detalle_http_error(exc: HttpError) -> tuple[str, str, int | None]:
    """Extrae reason/message/status de errores de Google API cuando sea posible."""
    reason = "unknown"
    message = str(exc)
    status_code = getattr(getattr(exc, "resp", None), "status", None)

    content = getattr(exc, "content", None)
    if not content:
        return reason, message, status_code

    try:
        raw = content.decode("utf-8") if isinstance(content, (bytes, bytearray)) else str(content)
        payload = json.loads(raw)
        err = payload.get("error", {}) if isinstance(payload, dict) else {}
        message = err.get("message", message)

        detalles = err.get("errors", [])
        if isinstance(detalles, list) and detalles:
            first = detalles[0] if isinstance(detalles[0], dict) else {}
            reason = first.get("reason", reason)
            message = first.get("message", message)
    except Exception:
        pass

    return reason, message, status_code


def _formatear_http_error(contexto: str, exc: HttpError) -> str:
    reason, message, status_code = _extraer_detalle_http_error(exc)
    status_txt = str(status_code) if status_code is not None else "N/A"
    return f"{contexto} (HTTP {status_txt}) - reason: {reason} - detalle: {message}"


def _safe_name(value: str | None, fallback: str) -> str:
    """Limpia nombre para usarlo en Drive evitando caracteres conflictivos."""
    raw = (value or "").strip()
    if not raw:
        raw = fallback
    return raw.replace("/", "-").replace("\\", "-").strip()


def _get_or_create_folder(service, folder_name: str, parent_id: str) -> str | None:
    """Busca carpeta por nombre en parent; si no existe, la crea y devuelve su ID."""
    safe_folder_name = folder_name.replace("'", "\\'")
    query = (
        f"mimeType='application/vnd.google-apps.folder' and trashed=false "
        f"and name='{safe_folder_name}' and '{parent_id}' in parents"
    )

    try:
        found = (
            service.files()
            .list(
                q=query,
                fields="files(id,name)",
                pageSize=1,
                includeItemsFromAllDrives=True,
                supportsAllDrives=True,
            )
            .execute()
            .get("files", [])
        )
    except HttpError as exc:
        st.error(_formatear_http_error("Error listando carpeta en Drive", exc))
        return None

    if found:
        return found[0].get("id")

    body = {
        "name": folder_name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }
    try:
        created = (
            service.files()
            .create(body=body, fields="id", supportsAllDrives=True)
            .execute()
        )
    except HttpError as exc:
        st.error(_formatear_http_error("Error creando carpeta en Drive", exc))
        return None
    return created.get("id")


@st.cache_resource(show_spinner=False)
def get_drive_service():
    """
    Crea y cachea el servicio de Google Drive API v3.

    Returns:
        Recurso autenticado de Drive API.

    Raises:
        KeyError: Si las credenciales no están configuradas en secrets.
    """
    creds_dict = dict(st.secrets["gcp_service_account"])
    credentials = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def upload_file(
    file_bytes: bytes,
    filename: str,
    mime_type: str = "image/jpeg",
    folder_id: str | None = None,
) -> str | None:
    """
    Sube un archivo a Google Drive.

    Args:
        file_bytes: Contenido binario del archivo.
        filename: Nombre con el que se guardará en Drive.
        mime_type: Tipo MIME del archivo.
        folder_id: ID de la carpeta destino en Drive (opcional).

    Returns:
        ID del archivo en Drive, o None si falló la subida.
    """
    try:
        service = get_drive_service()
        metadata: dict = {"name": filename}
        if folder_id:
            metadata["parents"] = [folder_id]

        media = MediaIoBaseUpload(
            io.BytesIO(file_bytes), mimetype=mime_type, resumable=True
        )
        file = (
            service.files()
            .create(
                body=metadata,
                media_body=media,
                fields="id",
                supportsAllDrives=True,
            )
            .execute()
        )
        return file.get("id")
    except HttpError as exc:
        msg = str(exc)
        detalle = _formatear_http_error("Error al subir archivo a Drive", exc)
        if "storageQuotaExceeded" in msg or "Service Accounts do not have storage quota" in msg:
            st.error(
                "Drive rechazo la subida porque la Service Account no tiene cuota en My Drive. "
                "Usa una carpeta dentro de Shared Drive y comparte esa carpeta con la Service Account "
                "con rol Content manager o Contributor."
            )
        else:
            st.error(detalle)
        return None
    except Exception as exc:
        st.error(f"Error al subir archivo a Drive: {exc}")
        return None


def get_file_url(file_id: str) -> str:
    """
    Construye la URL pública de vista previa para un archivo en Drive.

    Args:
        file_id: ID del archivo en Google Drive.

    Returns:
        URL de visualización del archivo.
    """
    return f"https://drive.google.com/file/d/{file_id}/view"


def get_thumbnail_url(file_id: str) -> str:
    """
    Construye la URL de miniatura para imágenes en Drive.

    Args:
        file_id: ID del archivo en Google Drive.

    Returns:
        URL de miniatura (sz=w400).
    """
    return f"https://drive.google.com/thumbnail?id={file_id}&sz=w400"


def make_file_public(file_id: str) -> bool:
    """
    Hace que un archivo en Drive sea visible para cualquiera con el enlace.

    Args:
        file_id: ID del archivo en Google Drive.

    Returns:
        True si se aplicó el permiso correctamente, False en caso contrario.
    """
    try:
        service = get_drive_service()
        service.permissions().create(
            fileId=file_id,
            body={"type": "anyone", "role": "reader"},
            supportsAllDrives=True,
        ).execute()
        return True
    except Exception as exc:
        st.warning(f"No se pudo cambiar permisos a publico en Drive: {exc}")
        return False


def subir_fotos_drive(
    fotos,
    id_persona: str,
    id_ruta: str,
    fecha: str,
    fotos_existentes: int = 0,
    nombre_persona: str = "",
    id_entrevistador: str = "",
    nombre_entrevistador: str = "",
    nombre_ruta: str = "",
) -> list[str]:
    """
    Sube multiples fotos a Drive y devuelve enlaces publicos.

    Args:
        fotos: Lista de UploadedFile de Streamlit.
        id_persona: ID de persona para nombrado.
        id_ruta: ID de ruta para nombrado.
        fecha: Fecha de captura (YYYY-MM-DD).
        fotos_existentes: Cantidad previa para continuar numeracion.

    Returns:
        Lista de URLs de visualizacion en Drive para las fotos subidas.
    """
    enlaces: list[str] = []
    folder_id = st.secrets.get("drive", {}).get("photos_folder_id")

    if not folder_id:
        st.error(
            "No hay carpeta destino configurada en secrets: [drive].photos_folder_id"
        )
        return enlaces

    id_entrevistador = id_entrevistador or st.session_state.get("entrevistador_id", "SIN_ID")
    nombre_entrevistador = nombre_entrevistador or st.session_state.get(
        "entrevistador_nombre", "Entrevistador"
    )
    nombre_ruta = nombre_ruta or st.session_state.get("ruta_nombre", "Ruta")

    carpeta_entrevistador = f"{_safe_name(nombre_entrevistador, 'Entrevistador')}_{_safe_name(id_entrevistador, 'SIN_ID')}"
    carpeta_ruta = f"{_safe_name(nombre_ruta, 'Ruta')}_{_safe_name(id_ruta, 'SIN_RUTA')}"

    try:
        service = get_drive_service()
        folder_entrevistador_id = _get_or_create_folder(service, carpeta_entrevistador, folder_id)
        if not folder_entrevistador_id:
            st.error("No se pudo crear/encontrar carpeta de entrevistador en Drive.")
            return enlaces

        folder_ruta_id = _get_or_create_folder(service, carpeta_ruta, folder_entrevistador_id)
        if not folder_ruta_id:
            st.error("No se pudo crear/encontrar carpeta de ruta en Drive.")
            return enlaces
    except Exception as exc:
        st.error(f"Error preparando carpetas en Drive: {exc}")
        return enlaces

    for idx, foto in enumerate(fotos, start=1):
        mime_type = getattr(foto, "type", None) or "image/jpeg"
        ext = "jpg"
        if "png" in mime_type.lower():
            ext = "png"
        elif "jpeg" in mime_type.lower() or "jpg" in mime_type.lower():
            ext = "jpg"

        secuencia = fotos_existentes + idx
        nombre_persona_archivo = _safe_name(nombre_persona, "SIN_NOMBRE")
        fecha_archivo = _safe_name(fecha, "SIN_FECHA")
        nombre_archivo = f"{fecha_archivo}_{id_persona}_{nombre_persona_archivo}_{secuencia}.{ext}"
        contenido = foto.read()
        file_id = upload_file(
            file_bytes=contenido,
            filename=nombre_archivo,
            mime_type=mime_type,
            folder_id=folder_ruta_id,
        )
        if file_id:
            make_file_public(file_id)
            enlaces.append(get_file_url(file_id))

    return enlaces
