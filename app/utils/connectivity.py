"""
Verificación de conectividad a Internet y a Google APIs.

Uso:
    from utils.connectivity import is_online, check_google_api
"""
import socket
import urllib.request


def is_online(timeout: int = 3) -> bool:
    """
    Comprueba si hay conexión a Internet haciendo una petición DNS.

    Args:
        timeout: Segundos máximos de espera.

    Returns:
        True si hay conexión, False en caso contrario.
    """
    try:
        socket.setdefaulttimeout(timeout)
        socket.getaddrinfo("dns.google", 443)
        return True
    except OSError:
        return False


def check_google_api(timeout: int = 5) -> bool:
    """
    Verifica el acceso a la API de Google Sheets/Drive.

    Args:
        timeout: Segundos máximos de espera.

    Returns:
        True si se puede alcanzar el endpoint, False en caso contrario.
    """
    url = "https://www.googleapis.com/discovery/v1/apis"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ElCaracol/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status == 200
    except Exception:
        return False


def connectivity_badge() -> str:
    """
    Retorna un emoji indicador del estado de conectividad.

    Returns:
        '🟢 En línea' o '🔴 Sin conexión'.
    """
    return "🟢 En línea" if is_online() else "🔴 Sin conexión"


def verificar_conexion(timeout: int = 3) -> bool:
    """Alias en espanol para mantener compatibilidad con pantallas de login."""
    return is_online(timeout=timeout)


def banner_sin_conexion() -> None:
    """Muestra un banner consistente para modo offline."""
    try:
        import streamlit as st

        st.warning("Sin conexion a internet - Modo offline activado")
    except Exception:
        # Fallback silencioso para mantener esta utilidad libre de dependencias duras.
        pass
