import streamlit as st
import pdfplumber
from reportlab.pdfgen import canvas
from reportlab.lib.colors import red
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
# CARPETA HISTORIAL
# =========================================================
if not os.path.exists("historial"):
    os.makedirs("historial")

# =========================================================
# CARGAR HISTORIAL DESDE DISCO
# =========================================================
if "historial" not in st.session_state:
    st.session_state.historial = []

    archivos_guardados = os.listdir("historial")

    for archivo in archivos_guardados:
        ruta = f"historial/{archivo}"
        st.session_state.historial.append({
            "nombre": archivo,
            "ruta": ruta
        })

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
# IMÁGENES
# =========================================================
def get_base64_image(path):
    if not os.path.exists(path):
        return ""
    with open(path, "rb") as img:
        return base64.b64encode(img.read()).decode()

# =========================================================
# 🎨 ESTILOS NUEVOS (SaaS)
# =========================================================
st.markdown("""
<style>
.card {
    background: linear-gradient(145deg, #0b1220, #0f172a);
    border-radius: 20px;
    padding: 30px 10px 18px 10px;
    text-align: center;
    color: white;
    border: 1px solid rgba(255,255,255,0.05);
    transition: all 0.3s ease;
    position: relative;
}

.card:hover {
    transform: translateY(-4px);
    box-shadow: 0 10px 25px rgba(0,0,0,0.4);
}

.card.selected {
    border: 2px solid #22c55e;
    box-shadow: 0 0 25px rgba(34,197,94,0.6);
}

.logo {
    position: absolute;
    top: -28px;
    left: 50%;
    transform: translateX(-50%);
    background: white;
    border-radius: 12px;
    padding: 6px 10px;
}

.card h2 {
    font-size: 14px;
    margin-top: 20px;
}

.check {
    position: absolute;
    right: 12px;
    top: 12px;
    background: #22c55e;
    color: white;
    border-radius: 50%;
    width: 22px;
    height: 22px;
    font-size: 13px;
    display: flex;
    align-items: center;
    justify-content: center;
}
</style>
""", unsafe_allow_html=True)

# =========================================================
# BANCOS
# =========================================================
st.markdown("## 🏦 Bancos")

opciones = {
    "BBVA Débito": "tdd",
    "BBVA Crédito": "tdc",
    "Banamex": "banamex"
}

seleccion = st.radio(
    "Selecciona un banco",
    options=list(opciones.keys()),
    index=None if st.session_state.banco is None else list(opciones.values()).index(st.session_state.banco),
    horizontal=True
)

if seleccion:
    st.session_state.banco = opciones[seleccion]

# =========================================================
# TARJETAS VISUALES
# =========================================================
col1, col2, col3 = st.columns(3)

def tarjeta(nombre, key, ruta):
    img = get_base64_image(ruta)
    selected = st.session_state.banco == key
    check = '<div class="check">✓</div>' if selected else ""

    st.markdown(f"""
    <div class="card {'selected' if selected else ''}">
        {check}
        <div class="logo">
            <img src="data:image/png;base64,{img}" width="95">
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
# PROCESAR PDF (ROJO EN TODAS LAS HOJAS)
# =========================================================
def procesar_pdf(file_bytes, nombre_archivo):
    packet = BytesIO()
    can = canvas.Canvas(packet)

    contador_cargos = 1
    contador_abonos = 1

    with pdfplumber.open(BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:

            can.setFillColor(red)

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

                linea = " ".join([
                    ww["text"] for ww in words
                    if abs(float(ww["top"]) - top) < 3
                ]).upper()

                if re.search(r'\b[A-Z]\d{2}\b', linea):

                    if patron_monto.match(t):

                        if X_CARGO_MIN <= x0 <= X_CARGO_MAX:
                            can.setFont("Helvetica-Bold", 8)
                            can.drawRightString(x1+15, y, str(contador_cargos))
                            contador_cargos += 1
                            usados.add(key)

                        elif X_ABONO_MIN <= x0 <= X_ABONO_MAX:
                            can.setFont("Helvetica-Bold", 8)
                            can.drawRightString(x1+15, y, str(contador_abonos))
                            contador_abonos += 1
                            usados.add(key)

                elif patron_monto.match(t) and X_CARGO_MIN <= x0 <= X_CARGO_MAX:
                    can.drawRightString(x1+15, y, str(contador_cargos))
                    contador_cargos += 1
                    usados.add(key)

                elif patron_monto.match(t) and X_ABONO_MIN <= x0 <= X_ABONO_MAX:
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

                ruta = f"historial/{nombre_archivo}"
                with open(ruta, "wb") as f:
                    f.write(resultado.getbuffer())

                st.session_state.historial.append({
                    "nombre": nombre_archivo,
                    "ruta": ruta
                })

                st.success(f"{archivo.name} listo")
                st.download_button("Descargar", resultado, file_name=nombre_archivo)

# =========================================================
# HISTORIAL
# =========================================================
st.divider()
st.markdown("### 📁 Historial")

if st.session_state.historial:

    for i, item in enumerate(reversed(st.session_state.historial)):

        nombre = item["nombre"]
        ruta = item["ruta"]

        col1, col2, col3 = st.columns([6,1,1])

        with col1:
            st.write("📄", nombre)

        with col2:
            if os.path.exists(ruta):
                with open(ruta, "rb") as f:
                    st.download_button("⬇️", f, file_name=nombre, key=f"d{i}")

        with col3:
            if st.button("🗑️", key=f"x{i}"):
                if os.path.exists(ruta):
                    os.remove(ruta)
                st.session_state.historial.remove(item)
                st.rerun()

else:
    st.info("Aún no hay archivos procesados")
