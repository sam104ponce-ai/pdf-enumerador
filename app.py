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
    st.session_state.banco = None

# =========================================================
# HEADER
# =========================================================
st.markdown("<h1 style='text-align:center;'>FlowLedger</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align:center;color:gray;'>Automatización de Movimientos Bancarios</p>", unsafe_allow_html=True)

st.divider()

# =========================================================
# FUNCION IMAGEN
# =========================================================
def get_base64_image(path):
    if not os.path.exists(path):
        return ""
    with open(path, "rb") as img:
        return base64.b64encode(img.read()).decode()

# =========================================================
# ESTILOS
# =========================================================
st.markdown("""
<style>
.card {
    background-color: #111827;
    border-radius: 18px;
    padding: 30px 10px 15px 10px;
    text-align: center;
    color: white;
    cursor: pointer;
    border: 2px solid transparent;
    transition: 0.3s;
    position: relative;
}

.card:hover {
    border: 2px solid #2563eb;
    transform: scale(1.03);
}

.card.selected {
    border: 2px solid #22c55e;
    box-shadow: 0 0 10px #22c55e;
}

.logo {
    position: absolute;
    top: -30px;
    left: 50%;
    transform: translateX(-50%);
    background: white;
    border-radius: 12px;
    padding: 5px;
}
</style>
""", unsafe_allow_html=True)

# =========================================================
# TARJETAS
# =========================================================
st.markdown("## 🏦 Bancos")

col1, col2, col3 = st.columns(3)

def tarjeta(nombre, key, ruta):
    img = get_base64_image(ruta)
    selected = "selected" if st.session_state.banco == key else ""

    if st.button("", key=f"btn_{key}"):
        st.session_state.banco = key

    st.markdown(f"""
    <div class="card {selected}">
        <div class="logo">
            <img src="data:image/png;base64,{img}" width="60">
        </div>
        <h3 style="margin-top:20px;">{nombre}</h3>
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
# CONFIG PDF
# =========================================================
X_CARGO_MIN, X_CARGO_MAX = 290, 380
X_ABONO_MIN, X_ABONO_MAX = 390, 480

patron_monto = re.compile(r'^\d{1,3}(?:,\d{3})*\.\d{2}$')

# =========================================================
# PROCESAR PDF (AUTOMÁTICO PARA CUALQUIER CÓDIGO)
# =========================================================
def procesar_pdf(file_bytes, nombre_archivo):
    packet = BytesIO()
    can = canvas.Canvas(packet)

    contador_cargos = 1
    contador_abonos = 1

    with pdfplumber.open(BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            words = page.extract_words()

            usados = set()

            for w in words:
                t = w["text"].strip()
                x0 = float(w["x0"])
                x1 = float(w["x1"])
                top = float(w["top"])
                bottom = float(w["bottom"])

                y = page.height - ((top + bottom) / 2)

                if top < 120:
                    continue

                key = (t, round(top,1), round(x0,1))
                if key in usados:
                    continue

                # Detecta cualquier código tipo C48, K65, etc
                linea = " ".join([ww["text"] for ww in words if abs(float(ww["top"]) - top) < 3]).upper()

                if re.search(r'\b[A-Z]\d{2}\b', linea):
                    if patron_monto.match(t):
                        can.setFillColorRGB(1,0,0)
                        can.setFont("Helvetica-Bold",8)
                        can.drawRightString(x1+15,y,str(contador_cargos))
                        contador_cargos+=1
                        usados.add(key)

                elif patron_monto.match(t) and X_CARGO_MIN <= x0 <= X_CARGO_MAX:
                    can.setFillColorRGB(1,0,0)
                    can.setFont("Helvetica-Bold",8)
                    can.drawRightString(x1+15,y,str(contador_cargos))
                    contador_cargos+=1
                    usados.add(key)

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
# INTERFAZ
# =========================================================
if st.session_state.banco:

    st.subheader(f"Banco seleccionado: {st.session_state.banco.upper()}")

    archivos = st.file_uploader("Sube hasta 3 PDFs", type=["pdf"], accept_multiple_files=True)

    if archivos and len(archivos) <= 3:
        for archivo in archivos:
            if st.button(f"Procesar {archivo.name}"):
                resultado, nombre_archivo = procesar_pdf(archivo.read(), archivo.name)

                st.success(f"{archivo.name} listo")
                st.download_button("Descargar", resultado, file_name=nombre_archivo)

elif st.session_state.banco is None:
    st.info("Selecciona un banco para comenzar")
