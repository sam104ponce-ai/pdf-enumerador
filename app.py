import streamlit as st
import pdfplumber
from reportlab.pdfgen import canvas
from PyPDF2 import PdfReader, PdfWriter
from io import BytesIO
import re
import os

# =========================================================
# CONFIG
# =========================================================
st.set_page_config(page_title="FlowLedger", layout="wide")

# =========================================================
# CSS PREMIUM
# =========================================================
st.markdown("""
<style>
.main {background-color: #0b1220;}
h1 {font-size: 42px !important; text-align:center;}
.sub {text-align:center; color:gray;}

.stButton>button {
    width:100%;
    background: linear-gradient(90deg, #2563eb, #1d4ed8);
    color: white;
    border-radius: 12px;
    height: 50px;
    font-size:16px;
}
</style>
""", unsafe_allow_html=True)

# =========================================================
# HEADER
# =========================================================
st.markdown("<h1>FlowLedger</h1>", unsafe_allow_html=True)
st.markdown("<p class='sub'>Automatización de Movimientos Bancarios</p>", unsafe_allow_html=True)

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
            words = page.extract_words(use_text_flow=True)
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

                # CARGOS
                if X_CARGO_MIN <= x0 <= X_CARGO_MAX:
                    can.setFillColorRGB(1,0,0)
                    can.setFont("Helvetica-Bold",8)
                    can.drawRightString(x1+15,y,str(contador_cargos))
                    contador_cargos+=1
                    usados.add(key)

                # ABONOS
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
# INTERFAZ
# =========================================================
def interfaz(nombre, key):
    st.subheader(nombre)

    archivo = st.file_uploader(
        "Sube tu PDF",
        type=["pdf"],
        key=f"upload_{key}"
    )

    if archivo:
        if st.button("Procesar PDF", key=f"btn_{key}"):
            resultado, nombre_archivo = procesar_pdf(archivo.read(), archivo.name)
            st.download_button("Descargar PDF", resultado, file_name=nombre_archivo)

# =========================================================
# ESTADO
# =========================================================
if "banco" not in st.session_state:
    st.session_state.banco = "tdd"

# =========================================================
# SELECTOR DE BANCOS (CLICK DIRECTO)
# =========================================================
st.markdown("## 🏦 Bancos")

col1, col2, col3 = st.columns(3)

def boton_banco(nombre, key, ruta):
    seleccionado = st.session_state.banco == key

    with st.container():

        # Imagen
        if os.path.exists(ruta):
            st.image(ruta, width=90)
        else:
            st.warning(f"No se encontró: {ruta}")

        # 🔥 BOTÓN PRINCIPAL
        if st.button(nombre, key=f"bank_{key}"):
            st.session_state.banco = key

        # 🔥 INDICADOR VERDE AUTOMÁTICO
        if seleccionado:
            st.success(f"{nombre} seleccionado")

with col1:
    boton_banco("BBVA Débito", "tdd", "assets/bbva.png")

with col2:
    boton_banco("BBVA Crédito", "tdc", "assets/bbva.png")

with col3:
    boton_banco("Banamex", "banamex", "assets/banamex.png")

st.divider()

# =========================================================
# CONTENIDO DINÁMICO
# =========================================================
if st.session_state.banco == "tdd":
    interfaz("BBVA Débito", "tdd")

elif st.session_state.banco == "tdc":
    interfaz("BBVA Crédito", "tdc")

elif st.session_state.banco == "banamex":
    interfaz("Banamex", "banamex")
