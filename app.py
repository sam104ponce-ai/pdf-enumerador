 import streamlit as st
import pdfplumber
from reportlab.pdfgen import canvas
from PyPDF2 import PdfReader, PdfWriter
from io import BytesIO
import re
import os
import base64
import json

# =========================================================
# CONFIG
# =========================================================
st.set_page_config(page_title="FlowLedger", layout="wide")

# =========================================================
# ARCHIVOS PERMANENTES
# =========================================================
HISTORIAL_FILE = "historial.json"
CARPETA_PDFS = "historial"

os.makedirs(CARPETA_PDFS, exist_ok=True)

def cargar_historial():
    if os.path.exists(HISTORIAL_FILE):
        with open(HISTORIAL_FILE, "r") as f:
            return json.load(f)
    return []

def guardar_historial(data):
    with open(HISTORIAL_FILE, "w") as f:
        json.dump(data, f)

# =========================================================
# ESTADO
# =========================================================
if "banco" not in st.session_state:
    st.session_state.banco = "tdd"

if "historial" not in st.session_state:
    st.session_state.historial = cargar_historial()

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

# Detecta cualquier código tipo C48, K65, etc.
patron_codigo = re.compile(r'\b[A-Z]\d{2}\b')

# =========================================================
# PROCESAR PDF
# =========================================================
def procesar_pdf(file_bytes):
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
                bottom = float(w["bottom"])

                y = page.height - ((top + bottom) / 2) - 1

                if top < 120:
                    continue

                key = (t, round(top,1), round(x0,1))
                if key in usados:
                    continue

                # Agrupar línea
                linea_texto = ""
                linea_palabras = []

                for ww in words:
                    if abs(float(ww["top"]) - top) < 3:
                        linea_texto += ww["text"] + " "
                        linea_palabras.append(ww)

                linea_mayus = linea_texto.upper()

                # Detectar códigos automáticos
                if patron_codigo.search(linea_mayus):
                    for ww in linea_palabras:
                        texto = ww["text"].strip()

                        if patron_monto.match(texto):
                            x1_m = float(ww["x1"])

                            can.setFillColorRGB(1,0,0)
                            can.setFont("Helvetica-Bold",8)
                            can.drawRightString(x1_m + 15, y, str(contador_cargos))

                            contador_cargos += 1
                            usados.add((texto, round(top,1), round(x1_m,1)))
                            break

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

    return output

# =========================================================
# IMÁGENES
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
    height: 180px;
    background-color: transparent;
    border: none;
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
    seleccionado = st.session_state.banco == key

    estilo = "background-color:#1f2937;border:2px solid #374151;"
    if seleccionado:
        estilo = "background-color:#111827;border:2px solid #22c55e;box-shadow:0 0 10px #22c55e;"

    click = st.button(" ", key=f"bank_{key}")

    st.markdown(f"""
    <div style="{estilo} border-radius:16px;padding:20px;text-align:center;margin-top:-140px;">
        <img src="data:image/png;base64,{img}" width="80"><br><br>
        <strong style="color:white;">{nombre}</strong>
    </div>
    """, unsafe_allow_html=True)

    if click:
        st.session_state.banco = key
        st.rerun()

with col1:
    tarjeta("BBVA Débito", "tdd", "assets/bbva.png")

with col2:
    tarjeta("BBVA Crédito", "tdc", "assets/bbva.png")

with col3:
    tarjeta("Banamex", "banamex", "assets/banamex.png")

st.divider()

# =========================================================
# INTERFAZ MULTI PDF
# =========================================================
def interfaz(nombre, key):
    st.subheader(nombre)

    archivos = st.file_uploader(
        "Sube hasta 3 PDFs",
        type=["pdf"],
        accept_multiple_files=True,
        key=f"upload_{key}"
    )

    if archivos:
        if len(archivos) > 3:
            st.warning("Máximo 3 archivos")
        else:
            if st.button("Procesar PDFs", key=f"proc_{key}"):

                for archivo in archivos:
                    resultado = procesar_pdf(archivo.read())

                    nombre_final = archivo.name.replace(".pdf", "_ENUMERADO.pdf")
                    ruta = os.path.join(CARPETA_PDFS, nombre_final)

                    with open(ruta, "wb") as f:
                        f.write(resultado.getvalue())

                    st.session_state.historial.append({
                        "nombre": nombre_final,
                        "ruta": ruta
                    })

                guardar_historial(st.session_state.historial)

                st.success("PDFs procesados correctamente")

# Mostrar interfaz
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

if not st.session_state.historial:
    st.info("Sin archivos aún")
else:
    for i, item in enumerate(st.session_state.historial[::-1]):

        col1, col2, col3 = st.columns([5,2,2])

        with col1:
            st.write("📄", item["nombre"])

        with col2:
            with open(item["ruta"], "rb") as f:
                st.download_button(
                    "⬇️ Descargar",
                    f,
                    file_name=item["nombre"],
                    key=f"d_{i}"
                )

        with col3:
            if st.button("🗑️", key=f"del_{i}"):
                if os.path.exists(item["ruta"]):
                    os.remove(item["ruta"])

                index_real = len(st.session_state.historial) - 1 - i
                st.session_state.historial.pop(index_real)

                guardar_historial(st.session_state.historial)
                st.rerun()v
