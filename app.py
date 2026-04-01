import streamlit as st
import pdfplumber
from reportlab.pdfgen import canvas
from PyPDF2 import PdfReader, PdfWriter
from io import BytesIO
import re
import os
import base64

# =========================================================
# CONFIG
# =========================================================
st.set_page_config(page_title="FlowLedger", layout="wide")

# =========================================================
# ESTADO
# =========================================================
if "banco" not in st.session_state:
    st.session_state.banco = "tdd"

if "historial" not in st.session_state:
    st.session_state.historial = []

# =========================================================
# HEADER
# =========================================================
st.markdown("<h1 style='text-align:center;'>FlowLedger</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align:center;color:gray;'>Automatización de Movimientos Bancarios</p>", unsafe_allow_html=True)

st.divider()

# =========================================================
# DASHBOARD
# =========================================================
st.markdown("### 📊 Dashboard")

col1, col2 = st.columns(2)
col1.metric("PDFs procesados", len(st.session_state.historial))
col2.metric("Bancos disponibles", 3)

st.divider()

# =========================================================
# CONFIG PDF
# =========================================================
X_CARGO_MIN, X_CARGO_MAX = 290, 380
X_ABONO_MIN, X_ABONO_MAX = 390, 480
patron_monto = re.compile(r'^\d{1,3}(?:,\d{3})*\.\d{2}$')

# =========================================================
# PROCESAR PDF
# =========================================================
def procesar_pdf(file_bytes, nombre_archivo):
    packet = BytesIO()
    can = canvas.Canvas(packet)

    contador_cargos = 1
    contador_abonos = 1

    with pdfplumber.open(BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            words = page.extract_words()

            if not words:
                can.showPage()
                continue

            usados = set()

            for w in words:
                t = w["text"].strip()
                if not patron_monto.match(t):
                    continue

                x0 = float(w["x0"])
                x1 = float(w["x1"])
                top = float(w["top"])
                y = page.height - top

                if top < 120:
                    continue

                key = (t, round(top,1), round(x0,1))
                if key in usados:
                    continue

                if X_CARGO_MIN <= x0 <= X_CARGO_MAX:
                    can.setFillColorRGB(1,0,0)
                    can.setFont("Helvetica-Bold",8)
                    can.drawRightString(x1+15,y,str(contador_cargos))
                    contador_cargos+=1
                    usados.add(key)

                elif X_ABONO_MIN <= x0 <= X_ABONO_MAX:
                    can.setFillColorRGB(1,0,0)
                    can.setFont("Helvetica-Bold",8)
                    can.drawRightString(x1+15,y,str(contador_abonos))
                    contador_abonos+=1
                    usados.add(key)

            can.showPage()

    can.save()
    packet.seek(0)

    overlay = PdfReader(packet)
    base = PdfReader(BytesIO(file_bytes))
    writer = PdfWriter()

    for i in range(len(base.pages)):
        page = base.pages[i]
        if i < len(overlay.pages):
            page.merge_page(overlay.pages[i])
        writer.add_page(page)

    output = BytesIO()
    writer.write(output)
    output.seek(0)

    return output, f"{nombre_archivo}_ENUMERADO.pdf"

# =========================================================
# BASE64 IMG
# =========================================================
def get_base64_image(path):
    if not os.path.exists(path):
        return ""
    with open(path, "rb") as img:
        return base64.b64encode(img.read()).decode()

# =========================================================
# CSS TARJETAS CLICKABLE
# =========================================================
st.markdown("""
<style>
.card-btn button {
    width: 100%;
    height: 180px;
    border-radius: 16px;
    border: none;
    background-color: #111827;
    color: white;
    font-weight: 600;
    font-size: 16px;
    transition: 0.3s;
}
.card-btn button:hover {
    background-color: #1d4ed8;
    box-shadow: 0 0 15px rgba(37,99,235,0.6);
    transform: scale(1.03);
}
.selected button {
    background-color: #1d4ed8 !important;
    box-shadow: 0 0 15px rgba(37,99,235,0.6);
}
</style>
""", unsafe_allow_html=True)

# =========================================================
# TARJETAS
# =========================================================
st.markdown("## 🏦 Bancos")

col1, col2, col3 = st.columns(3)

def tarjeta(nombre, key, ruta):
    seleccionado = st.session_state.banco == key
    img = get_base64_image(ruta)

    clase = "card-btn selected" if seleccionado else "card-btn"

    st.markdown(f"<div class='{clase}'>", unsafe_allow_html=True)

    if st.button(f"{nombre}", key=f"btn_{key}"):
        st.session_state.banco = key
        st.rerun()

    if img:
        st.markdown(f"""
        <div style='margin-top:-140px;text-align:center;pointer-events:none;'>
            <img src="data:image/png;base64,{img}" width="70"><br>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

with col1:
    tarjeta("BBVA Débito", "tdd", "assets/bbva.png")

with col2:
    tarjeta("BBVA Crédito", "tdc", "assets/bbva.png")

with col3:
    tarjeta("Banamex", "banamex", "assets/banamex.png")

st.divider()

# =========================================================
# INTERFAZ
# =========================================================
def interfaz(nombre, key):
    st.subheader(nombre)

    archivo = st.file_uploader("Sube tu PDF", type=["pdf"], key=f"upload_{key}")

    if archivo:
        if st.button("Procesar", key=f"proc_{key}"):
            resultado, nombre_archivo = procesar_pdf(archivo.read(), archivo.name)

            st.session_state.historial.append(nombre_archivo)

            st.success("Procesado correctamente")
            st.download_button("Descargar PDF", resultado, file_name=nombre_archivo)

if st.session_state.banco == "tdd":
    interfaz("BBVA Débito", "tdd")
elif st.session_state.banco == "tdc":
    interfaz("BBVA Crédito", "tdc")
elif st.session_state.banco == "banamex":
    interfaz("Banamex", "banamex")

# =========================================================
# HISTORIAL
# =========================================================
st.divider()
st.markdown("### 📁 Historial")

for h in st.session_state.historial[::-1]:
    st.write("✔️", h)
