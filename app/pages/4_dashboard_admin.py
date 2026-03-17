"""
Página 4 – Dashboard Administrativo
Visualización de estadísticas y exportación de datos (sólo rol admin).
"""
import streamlit as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.sheets_handler import get_all_records
from utils.connectivity import is_online

st.set_page_config(
    page_title="Dashboard Admin – El Caracol",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Guardias ──────────────────────────────────────────────────────────────────
if not st.session_state.get("authenticated"):
    st.warning("Debes iniciar sesión primero.")
    st.stop()

if st.session_state.get("user_role") != "admin":
    st.error("⛔ Acceso restringido. Solo administradores pueden ver esta página.")
    st.stop()

st.markdown(
    """
    <style>
    #MainMenu, footer {visibility: hidden;}
    .block-container {max-width: 900px; margin: 0 auto; padding-top: 1rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown("## 📊 Dashboard Administrativo")

# ── Carga de datos ────────────────────────────────────────────────────────────
if not is_online():
    st.warning("🔴 Sin conexión. El dashboard requiere acceso a Google Sheets.")
    if st.button("← Volver al inicio"):
        st.switch_page("main.py")
    st.stop()

with st.spinner("Cargando datos…"):
    df = get_all_records()

if df.empty:
    st.info("No hay registros disponibles o hubo un error al conectar con Google Sheets.")
    if st.button("← Volver al inicio"):
        st.switch_page("main.py")
    st.stop()

# ── Métricas generales ────────────────────────────────────────────────────────
st.markdown("### Resumen general")
total = len(df)
sincronizados = int((df.get("sincronizado", "No") == "Sí").sum()) if "sincronizado" in df.columns else total
con_foto = int((df.get("tiene_foto", "No") == "Sí").sum()) if "tiene_foto" in df.columns else 0

col1, col2, col3 = st.columns(3)
col1.metric("Total de registros", total)
col2.metric("Sincronizados", sincronizados)
col3.metric("Con fotografía", con_foto)

st.divider()

# ── Distribución por sexo ─────────────────────────────────────────────────────
if "sexo" in df.columns:
    st.markdown("### Distribución por sexo")
    sexo_counts = df["sexo"].value_counts()
    st.bar_chart(sexo_counts)

# ── Tiempo en situación de calle ──────────────────────────────────────────────
if "tiempo_calle" in df.columns:
    st.markdown("### Tiempo en situación de calle")
    tiempo_counts = df["tiempo_calle"].value_counts()
    st.bar_chart(tiempo_counts)

# ── Registros por fecha ───────────────────────────────────────────────────────
if "fecha" in df.columns:
    st.markdown("### Registros por fecha")
    fecha_counts = df["fecha"].value_counts().sort_index()
    st.line_chart(fecha_counts)

# ── Tabla completa ────────────────────────────────────────────────────────────
st.divider()
st.markdown("### Tabla de registros")
st.dataframe(df, use_container_width=True)

# ── Exportar ──────────────────────────────────────────────────────────────────
st.divider()
st.markdown("### Exportar datos")

col_a, col_b = st.columns(2)

with col_a:
    csv_data = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Descargar CSV",
        data=csv_data,
        file_name="registros_el_caracol.csv",
        mime="text/csv",
        use_container_width=True,
    )

with col_b:
    try:
        import io
        import openpyxl  # noqa: F401 – verify availability
        excel_buf = io.BytesIO()
        df.to_excel(excel_buf, index=False, engine="openpyxl")
        excel_buf.seek(0)
        st.download_button(
            label="⬇️ Descargar Excel",
            data=excel_buf.getvalue(),
            file_name="registros_el_caracol.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    except ImportError:
        st.info("Instala openpyxl para habilitar la exportación a Excel.")

st.divider()
if st.button("← Volver al inicio"):
    st.switch_page("main.py")
