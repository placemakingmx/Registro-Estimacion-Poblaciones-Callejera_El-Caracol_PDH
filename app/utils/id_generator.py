import random
import string
from datetime import datetime
import unicodedata


GENERO_MAP = {
    "Mujer": "M",
    "Hombre": "H",
    "No binario": "N",
    "Desconocido": "D",
    "Prefiere no decirlo": "D",
}

MESES_VALIDOS = {
    "ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC", "XXX"
}


def normalizar_texto(texto: str | None) -> str:
    if not texto:
        return ""
    limpio = texto.upper().strip()
    limpio = "".join(
        c for c in unicodedata.normalize("NFD", limpio)
        if unicodedata.category(c) != "Mn"
    )
    return "".join(limpio.split())


def generar_id_persona(
    genero: str,
    nombre: str | None,
    apellido: str | None,
    alias: str | None,
    mes_nac: str,
    anio_nac: int,
) -> str:
    """Genera ID_Persona con formato [G][NN][A][MMMAA]."""
    cod_genero = GENERO_MAP.get(genero, "D")

    nombre_n = normalizar_texto(nombre)
    apellido_n = normalizar_texto(apellido)
    alias_n = normalizar_texto(alias)
    mes_n = normalizar_texto(mes_nac)[:3]

    if mes_n not in MESES_VALIDOS:
        raise ValueError("Mes de nacimiento invalido para generar ID_Persona")
    if not anio_nac:
        raise ValueError("Anio de nacimiento obligatorio para generar ID_Persona")

    if not nombre_n and not apellido_n and not alias_n:
        cod_nombre = "NAX"
    elif not nombre_n and not alias_n and apellido_n:
        cod_nombre = f"NA{apellido_n[0]}"
    elif not nombre_n and alias_n and apellido_n:
        cod_nombre = f"{alias_n[:2]}{apellido_n[0]}"
    elif not nombre_n and alias_n and not apellido_n:
        cod_nombre = f"{alias_n[:2]}X"
    elif nombre_n and not apellido_n:
        cod_nombre = f"{nombre_n[:2]}X"
    else:
        cod_nombre = f"{nombre_n[:2]}{apellido_n[0]}"

    cod_nombre = cod_nombre.ljust(3, "X")[:3]
    anio_str = str(int(anio_nac))[-2:]
    return f"{cod_genero}{cod_nombre}{mes_n}{anio_str}"


def generar_id_entrevistador(
    genero: str,
    nombre: str,
    apellido: str,
    mes_nac: str,
    anio_nac: int,
) -> str:
    """Genera ID_Entrevistador con prefijo EC-."""
    base = generar_id_persona(
        genero=genero,
        nombre=nombre,
        apellido=apellido,
        alias=None,
        mes_nac=mes_nac,
        anio_nac=anio_nac,
    )
    return f"EC-{base}"


def generar_id_evento(
    fecha_entrevista: str,
    id_ruta: str,
    entrevistas_existentes: list[dict] | None = None,
) -> str:
    """Genera ID_Evento con formato DDMMAAAA-ID_Ruta."""
    if not fecha_entrevista:
        raise ValueError("La fecha de entrevista es obligatoria")
    if not str(id_ruta).strip():
        raise ValueError("El ID de ruta es obligatorio")

    dia, mes, anio = fecha_entrevista.split("/")
    fecha_str = f"{dia}{mes}{anio}"
    return f"{fecha_str}-{str(id_ruta).strip()}"


def generar_id_alfanumerico(prefijo: str = "", longitud: int = 7) -> str:
    """
    Genera ID unico alfanumerico de 7 caracteres.
    Formato: XXXXXXX (letras mayusculas + numeros)
    Ejemplo: A3K9M2L, B7X4P1Q
    """
    caracteres = string.ascii_uppercase + string.digits
    # Excluir caracteres ambiguos: 0/O, 1/I
    caracteres = caracteres.replace("O", "").replace("I", "")

    id_generado = "".join(random.choices(caracteres, k=longitud))

    # Agregar prefijo opcional (ej: P=Persona, E=Entrevistador, R=Ruta)
    if prefijo:
        id_generado = prefijo + id_generado[1:]

    return id_generado


def generar_id_entrevistador_legacy() -> str:
    return generar_id_alfanumerico(prefijo="E")


def generar_id_ruta() -> str:
    return generar_id_alfanumerico(prefijo="R")


def validar_id_unico(id_propuesto: str, lista_existentes: list[str]) -> bool:
    """Valida que ID no exista en lista (usar al sincronizar)."""
    return id_propuesto not in lista_existentes


def regenerar_si_duplicado(
    id_propuesto: str,
    lista_existentes: list[str],
    tipo: str = "persona",
) -> str:
    """Regenera ID hasta encontrar uno unico."""
    while id_propuesto in lista_existentes:
        if tipo == "persona":
            id_propuesto = generar_id_alfanumerico(prefijo="P")
        elif tipo == "entrevistador":
            id_propuesto = generar_id_entrevistador_legacy()
        elif tipo == "ruta":
            id_propuesto = generar_id_ruta()
        else:
            id_propuesto = generar_id_alfanumerico()
    return id_propuesto


def inicializar_session_ids(st) -> None:
    if "ids_generados_sesion" not in st.session_state:
        st.session_state.ids_generados_sesion = []
    if "contador_ids" not in st.session_state:
        st.session_state.contador_ids = 0


def registrar_id_generado(st, id_nuevo: str) -> None:
    st.session_state.ids_generados_sesion.append(id_nuevo)
    st.session_state.contador_ids += 1


# Compatibilidad hacia atras con el codigo ya existente en la app.
def generate_id(prefix: str = "") -> str:
    """Alias compatible para llamadas previas a generate_id()."""
    if prefix:
        return generar_id_alfanumerico(prefijo=prefix[:1].upper())
    return generar_id_alfanumerico()


def parse_id(record_id: str) -> dict:
    """Parser minimo para conservar compatibilidad con importaciones existentes."""
    return {
        "raw": record_id,
        "prefix": record_id[0] if record_id else "",
        "timestamp": datetime.now().isoformat(),
    }
