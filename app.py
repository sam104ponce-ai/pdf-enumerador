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
# PROCESAR PDF (CON C48 CORRECTO)
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

                x0 = float(w["x0"])
                x1 = float(w["x1"])
                top = float(w["top"])
                y = page.height - top

                if top < 120:
                    continue

                key = (t, round(top,1), round(x0,1))
                if key in usados:
                    continue

                # =========================================================
                # AGRUPAR FILA (PARA DETECTAR C48)
                # =========================================================
                linea_texto = ""
                linea_palabras = []

                for ww in words:
                    if abs(float(ww["top"]) - top) < 3:
                        linea_texto += ww["text"] + " "
                        linea_palabras.append(ww)

                linea_mayus = linea_texto.upper()

                # =========================================================
                # 🔥 C48 COMO CARGO (ALINEADO AL MONTO)
                # =========================================================
                if "C48" in linea_mayus:
                    for ww in linea_palabras:
                        texto = ww["text"].strip()

                        if patron_monto.match(texto):
                            x0_m = float(ww["x0"])
                            x1_m = float(ww["x1"])

                            key_c48 = (texto, round(top,1), round(x0_m,1))
                            if key_c48 in usados:
                                continue

                            can.setFillColorRGB(1,0,0)
                            can.setFont("Helvetica-Bold",8)
                            can.drawRightString(x1_m + 15, y, str(contador_cargos))

                            contador_cargos += 1
                            usados.add(key_c48)
                            break

                # =========================================================
                # CARGOS NORMALES
                # =========================================================
                elif patron_monto.match(t) and X_CARGO_MIN <= x0 <= X_CARGO_MAX:
                    can.setFillColorRGB(1,0,0)
                    can.setFont("Helvetica-Bold",8)
                    can.drawRightString(x1+15,y,str(contador_cargos))
                    contador_cargos+=1
                    usados.add(key)

                # =========================================================
                # ABONOS
                # =========================================================
                elif patron_monto.match(t) and X_ABONO_MIN <= x0 <= X_ABONO_MAX:
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
# CSS TARJETAS
# =========================================================
st.markdown("""
<style>
div.stButton > button {
    width: 100%;
    height: 160px;
    border-radius: 16px;
    background-color: #111827;
    color: white;
    font-size: 16px;
    font-weight: 600;
    border: 1px solid #374151;
    transition: 0.3s;
}
div.stButton > button:hover {
    background-color: #1d4ed8;
    box-shadow: 0 0 15px rgba(37,99,235,0.6);
    transform: scale(1.03);
}
</style>
""", unsafe_allow_html=True)

# =========================================================
# TARJETAS CLICKABLES
# =========================================================
st.markdown("## 🏦 Bancos")

col1, col2, col3 = st.columns(3)

def tarjeta(nombre, key, ruta):
    img = get_base64_image(ruta)

    if st.button(nombre, key=f"bank_{key}"):
        st.session_state.banco = key
        st.rerun()

    if img:
        st.markdown(f"""
        <div style='margin-top:-120px;text-align:center;pointer-events:none;'>
            <img src="data:image/png;base64,{img}" width="70">
        </div>
        """, unsafe_allow_html=True)

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
