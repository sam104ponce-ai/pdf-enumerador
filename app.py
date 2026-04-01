import streamlit as st
import pdfplumber
from reportlab.pdfgen import canvas
from PyPDF2 import PdfReader, PdfWriter
from io import BytesIO
import re
import os

# =========================================================
# CONFIGURACIÓN
# =========================================================
st.set_page_config(
    page_title="FlowLedger",
    page_icon="📊",
    layout="wide"
)

# =========================================================
# CSS PREMIUM
# =========================================================
st.markdown("""
<style>
.main {
    background-color: #0b1220;
}
h1 {
    font-size: 42px !important;
    font-weight: 700 !important;
}
.stButton>button {
    background: linear-gradient(90deg, #2563eb, #1d4ed8);
    color: white;
    border-radius: 12px;
    height: 3em;
    font-weight: 600;
}
.stDownloadButton>button {
    background: linear-gradient(90deg, #16a34a, #15803d);
    color: white;
    border-radius: 12px;
    height: 3em;
}
</style>
""", unsafe_allow_html=True)

# =========================================================
# SIDEBAR
# =========================================================
with st.sidebar:
    st.title("FlowLedger")
    st.caption("Sistema de automatización financiera")

    st.divider()

    st.markdown("### 🏦 Bancos")
    st.markdown("BBVA Débito")
    st.markdown("BBVA Crédito")
    st.markdown("Banamex")

    st.divider()

    st.success("Sistema activo")

# =========================================================
# HEADER PREMIUM
# =========================================================
st.markdown("""
<div style='text-align: center; padding-top: 20px; padding-bottom: 10px;'>
    <h1>FlowLedger</h1>
    <p style='font-size: 18px; color: #9ca3af;'>
        Automatización de Movimientos Bancarios
    </p>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div style='width: 120px; height: 4px; background: linear-gradient(90deg, #2563eb, #1d4ed8); margin: auto; border-radius: 10px;'></div>
""", unsafe_allow_html=True)

st.divider()

# =========================================================
# DASHBOARD
# =========================================================
st.markdown("### 📊 Panel de Control")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("""
    <div style='background-color:#111827;padding:20px;border-radius:12px;text-align:center;'>
        <h3>📄 PDFs procesados</h3>
        <h2>0</h2>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
    <div style='background-color:#111827;padding:20px;border-radius:12px;text-align:center;'>
        <h3>🏦 Bancos activos</h3>
        <h2>3</h2>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown("""
    <div style='background-color:#111827;padding:20px;border-radius:12px;text-align:center;'>
        <h3>⚡ Estado</h3>
        <h2 style='color:#16a34a;'>Activo</h2>
    </div>
    """, unsafe_allow_html=True)

st.divider()

# =========================================================
# CONFIG PDF
# =========================================================
X_CARGO_MIN, X_CARGO_MAX = 290, 380
X_ABONO_MIN, X_ABONO_MAX = 390, 480

patron_monto = re.compile(r'^\d{1,3}(?:,\d{3})*\.\d{2}$')

# =========================================================
# FUNCIÓN PDF
# =========================================================
def procesar_pdf(file_bytes, nombre_archivo):
    packet = BytesIO()
    can = canvas.Canvas(packet)

    contador_cargos = 1
    contador_abonos = 1

    with pdfplumber.open(BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            words = page.extract_words(use_text_flow=True)
            if not words:
                can.showPage()
                continue

            montos_usados = set()

            for w in words:
                t = w["text"].strip()
                if not patron_monto.match(t):
                    continue

                x0 = float(w["x0"])
                x1 = float(w["x1"])
                top = float(w["top"])
                y = page.height - top - 2

                if top < 120:
                    continue

                linea_texto = ""
                for ww in words:
                    if abs(float(ww["top"]) - top) < 3:
                        linea_texto += ww["text"] + " "

                linea_mayus = linea_texto.upper()

                if "MOVIMIENTOS DE PERIODOS ANTERIORES" in linea_mayus:
                    continue

                key = (t, round(top, 1), round(x0, 1))
                if key in montos_usados:
                    continue

                contiene_codigo = any(c in linea_mayus for c in [
                    "P14","T93","V41","K65","V40","T92","K64"
                ]) or "P14 TOTAL PLAY" in linea_mayus

                # CARGOS
                if X_CARGO_MIN <= x0 <= X_CARGO_MAX or contiene_codigo:
                    can.setFillColorRGB(1, 0, 0)
                    can.setFont("Helvetica-Bold", 8)
                    can.drawRightString(x1 + 14, y, str(contador_cargos))
                    contador_cargos += 1
                    montos_usados.add(key)
                    continue

                # ABONOS
                if X_ABONO_MIN <= x0 <= X_ABONO_MAX:
                    can.setFillColorRGB(1, 0, 0)
                    can.setFont("Helvetica-Bold", 8)
                    can.drawRightString(x1 + 14, y, str(contador_abonos))
                    contador_abonos += 1
                    montos_usados.add(key)

            can.showPage()

    can.save()
    packet.seek(0)

    overlay_pdf = PdfReader(packet)
    base_pdf = PdfReader(BytesIO(file_bytes))
    writer = PdfWriter()

    for i in range(len(base_pdf.pages)):
        page = base_pdf.pages[i]
        if i < len(overlay_pdf.pages):
            page.merge_page(overlay_pdf.pages[i])
        writer.add_page(page)

    nombre, ext = os.path.splitext(nombre_archivo)
    output_name = f"{nombre}_ENUMERADO{ext}"

    output_bytes = BytesIO()
    writer.write(output_bytes)
    output_bytes.seek(0)

    return output_bytes, output_name

# =========================================================
# INTERFAZ
# =========================================================
def interfaz_tab(nombre_tab, key):
    st.markdown(f"### {nombre_tab}")
    archivo = st.file_uploader("Sube tu PDF", type=["pdf"], key=key)

    if archivo:
        st.success("Archivo cargado")

        if st.button("Procesar", key=f"btn_{key}"):
            with st.spinner("Procesando..."):
                resultado, nombre = procesar_pdf(archivo.read(), archivo.name)

            st.success("Listo")
            st.download_button("Descargar PDF", resultado, file_name=nombre)

# =========================================================
# TABS CON LOGOS
# =========================================================
tab1, tab2, tab3 = st.tabs(["", "", ""])

with tab1:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        if os.path.exists("assets/bbva.png"):
            st.image("assets/bbva.png", width=120)
    interfaz_tab("BBVA Débito", "tdd")

with tab2:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        if os.path.exists("assets/bbva.png"):
            st.image("assets/bbva.png", width=120)
    interfaz_tab("BBVA Crédito", "tdc")

with tab3:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        if os.path.exists("assets/banamex.png"):
            st.image("assets/banamex.png", width=120)
    interfaz_tab("Banamex", "banamex")
