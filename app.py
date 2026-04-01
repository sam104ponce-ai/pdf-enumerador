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
# HEADER
# =========================================================
st.markdown("""
<div style='text-align: center; padding-top: 20px;'>
    <h1>FlowLedger</h1>
    <p style='color:#9ca3af;'>Automatización de Movimientos Bancarios</p>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div style='width:120px;height:4px;background:linear-gradient(90deg,#2563eb,#1d4ed8);margin:auto;border-radius:10px;'></div>
""", unsafe_allow_html=True)

st.divider()

# =========================================================
# DASHBOARD
# =========================================================
st.markdown("### 📊 Panel de Control")

col1, col2, col3 = st.columns(3)

col1.markdown("<div style='background:#111827;padding:20px;border-radius:12px;text-align:center;'><h3>📄 PDFs</h3><h2>0</h2></div>", unsafe_allow_html=True)
col2.markdown("<div style='background:#111827;padding:20px;border-radius:12px;text-align:center;'><h3>🏦 Bancos</h3><h2>3</h2></div>", unsafe_allow_html=True)
col3.markdown("<div style='background:#111827;padding:20px;border-radius:12px;text-align:center;'><h3>⚡ Estado</h3><h2 style='color:#16a34a;'>Activo</h2></div>", unsafe_allow_html=True)

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
    
    archivo = st.file_uploader(
        "Sube tu PDF",
        type=["pdf"],
        key=f"upload_{key}"
    )

    if archivo:
        st.success("Archivo cargado")

        if st.button("Procesar", key=f"btn_{key}"):
            with st.spinner("Procesando..."):
                resultado, nombre = procesar_pdf(archivo.read(), archivo.name)

            st.success("Listo")
            st.download_button(
                "Descargar PDF",
                resultado,
                file_name=nombre,
                key=f"download_{key}"
            )

# =========================================================
# SELECTOR DE BANCO
# =========================================================
st.markdown("### 🏦 Selecciona el banco")

if "banco" not in st.session_state:
    st.session_state.banco = "tdd"

col1, col2, col3 = st.columns(3)

def boton_banco(nombre, key, img):
    seleccionado = st.session_state.banco == key

    color = "#1d4ed8" if seleccionado else "#111827"
    borde = "2px solid #2563eb" if seleccionado else "1px solid #374151"

    st.markdown(f"""
    <div style='background:{color};padding:15px;border-radius:12px;text-align:center;border:{borde};'>
        <img src="{img}" width="80"><br>
        <span style='color:white;font-weight:600;'>{nombre}</span>
    </div>
    """, unsafe_allow_html=True)

    if st.button(f"Seleccionar {nombre}", key=f"select_{key}"):
        st.session_state.banco = key

with col1:
    if os.path.exists("assets/bbva.png"):
        boton_banco("BBVA Débito", "tdd", "assets/bbva.png")

with col2:
    if os.path.exists("assets/bbva.png"):
        boton_banco("BBVA Crédito", "tdc", "assets/bbva.png")

with col3:
    if os.path.exists("assets/banamex.png"):
        boton_banco("Banamex", "banamex", "assets/banamex.png")

st.divider()

# =========================================================
# CONTENIDO DINÁMICO
# =========================================================
if st.session_state.banco == "tdd":
    interfaz_tab("BBVA Débito", "tdd")

elif st.session_state.banco == "tdc":
    interfaz_tab("BBVA Crédito", "tdc")

elif st.session_state.banco == "banamex":
    interfaz_tab("Banamex", "banamex")
