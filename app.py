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

if "historial" not in st.session_state:
    st.session_state.historial = []

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
# ESTILOS PREMIUM
# =========================================================
st.markdown("""
<style>
.card {
    background-color: #0f172a;
    border-radius: 18px;
    padding: 25px 10px 12px 10px;
    text-align: center;
    color: white;
    border: 2px solid transparent;
    transition: 0.3s;
    position: relative;
}

.card.selected {
    border: 2px solid #22c55e;
    box-shadow: 0 0 12px #22c55e;
}

.logo {
    position: absolute;
    top: -26px;
    left: 50%;
    transform: translateX(-50%);
    background: white;
    border-radius: 10px;
    padding: 4px;
}

.card h2 {
    font-size: 16px;
    margin-top: 18px;
}

.radio-container {
    display: flex;
    justify-content: center;
    margin-bottom: 10px;
}
</style>
""", unsafe_allow_html=True)

# =========================================================
# TÍTULO ARRIBA 🔥
# =========================================================
st.markdown("## 🏦 Bancos")

# =========================================================
# SELECCIÓN ÚNICA
# =========================================================
opciones = {
    "BBVA Débito": "tdd",
    "BBVA Crédito": "tdc",
    "Banamex": "banamex"
}

st.markdown('<div class="radio-container">', unsafe_allow_html=True)

seleccion = st.radio(
    "Selecciona un banco",
    options=list(opciones.keys()),
    index=None if st.session_state.banco is None else list(opciones.values()).index(st.session_state.banco),
    horizontal=True
)

st.markdown('</div>', unsafe_allow_html=True)

if seleccion:
    st.session_state.banco = opciones[seleccion]

# =========================================================
# TARJETAS
# =========================================================
col1, col2, col3 = st.columns(3)

def tarjeta(nombre, key, ruta):
    img = get_base64_image(ruta)
    selected = "selected" if st.session_state.banco == key else ""

    st.markdown(f"""
    <div class="card {selected}">
        <div class="logo">
            <img src="data:image/png;base64,{img}" width="60">
        </div>
        <h2>{nombre}</h2>
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

                linea = " ".join([ww["text"] for ww in words if abs(float(ww["top"]) - top) < 3]).upper()

                if re.search(r'\b[A-Z]\d{2}\b', linea):
                    if patron_monto.match(t):
                        can.setFont("Helvetica-Bold", 8)
                        can.drawRightString(x1+15, y, str(contador_cargos))
                        contador_cargos += 1
                        usados.add(key)

                elif patron_monto.match(t) and X_CARGO_MIN <= x0 <= X_CARGO_MAX:
                    can.setFont("Helvetica-Bold", 8)
                    can.drawRightString(x1+15, y, str(contador_cargos))
                    contador_cargos += 1
                    usados.add(key)

                elif patron_monto.match(t) and X_ABONO_MIN <= x0 <= X_ABONO_MAX:
                    can.setFont("Helvetica-Bold", 8)
                    can.drawRightString(x1+15, y, str(contador_abonos))
                    contador_abonos += 1
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

    archivos = st.file_uploader(
        "Sube hasta 3 PDFs",
        type=["pdf"],
        accept_multiple_files=True
    )

    if archivos:
        archivos = archivos[:3]

        for archivo in archivos:
            if st.button(f"Procesar {archivo.name}"):
                resultado, nombre_archivo = procesar_pdf(archivo.read(), archivo.name)

                st.session_state.historial.append(nombre_archivo)

                st.success(f"{archivo.name} listo")
                st.download_button("Descargar", resultado, file_name=nombre_archivo)

# =========================================================
# HISTORIAL
# =========================================================
st.divider()
st.markdown("### 📁 Historial")

if st.session_state.historial:
    for item in reversed(st.session_state.historial):
        st.write("📄", item)
else:
    st.info("Aún no hay archivos procesados")
