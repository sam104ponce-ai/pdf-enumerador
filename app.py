import streamlit as st
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.colors import red
from reportlab.lib.pagesizes import letter
import io

st.set_page_config(page_title="Enumerador PDF", layout="centered")

# -------------------- ESTILOS --------------------
st.markdown("""
<style>
.banco-titulo {
    font-size: 22px;
    margin-top: 10px;
    margin-bottom: -10px;
}

.subtitulo {
    font-size: 14px;
    margin-bottom: 15px;
}

.bancos-container {
    display: flex;
    justify-content: space-around;
    margin-bottom: 20px;
}

.banco-card {
    text-align: center;
    cursor: pointer;
}

.banco-card img {
    width: 85px; /* LOGO GRANDE */
}

.banco-nombre {
    font-size: 12px; /* TEXTO MÁS PEQUEÑO */
    background-color: #f1f1f1;
    padding: 4px;
    border-radius: 8px;
    margin-top: 5px;
}

.selected {
    border: 2px solid red;
    border-radius: 10px;
    padding: 5px;
}
</style>
""", unsafe_allow_html=True)

# -------------------- ESTADO --------------------
if "banco" not in st.session_state:
    st.session_state.banco = None

if "historial" not in st.session_state:
    st.session_state.historial = []

# -------------------- HEADER --------------------
st.markdown('<div class="banco-titulo">🏦 Bancos</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitulo">Selecciona banco</div>', unsafe_allow_html=True)

# -------------------- FUNCION TARJETA --------------------
def banco_card(nombre, key, base64_img):
    selected_class = "selected" if st.session_state.banco == key else ""

    clicked = st.markdown(f"""
    <div class="banco-card {selected_class}">
        <img src="data:image/png;base64,{base64_img}">
        <div class="banco-nombre">{nombre}</div>
    </div>
    """, unsafe_allow_html=True)

    if st.button(f"Seleccionar {nombre}", key=key):
        st.session_state.banco = key

# -------------------- BASE64 (USA LOS TUYOS) --------------------
bbva = "TU_BASE64_BBVA"
santander = "TU_BASE64_SANTANDER"
banorte = "TU_BASE64_BANORTE"

# -------------------- MOSTRAR BANCOS --------------------
col1, col2, col3 = st.columns(3)

with col1:
    banco_card("BBVA Crédito", "bbva", bbva)

with col2:
    banco_card("Santander Débito", "santander", santander)

with col3:
    banco_card("Banorte Débito", "banorte", banorte)

# -------------------- SUBIR PDFs --------------------
st.markdown("### 📂 Subir PDFs (máx 3)")
pdfs = st.file_uploader("", type="pdf", accept_multiple_files=True)

# -------------------- ENUMERADOR --------------------
def enumerar_pdf(file):
    reader = PdfReader(file)
    writer = PdfWriter()

    for i, page in enumerate(reader.pages):
        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=letter)

        # NUMERO EN ROJO (TODAS LAS HOJAS)
        can.setFillColor(red)
        can.setFont("Helvetica-Bold", 12)
        can.drawString(500, 750, str(i+1))

        can.save()
        packet.seek(0)

        overlay = PdfReader(packet)
        page.merge_page(overlay.pages[0])
        writer.add_page(page)

    output = io.BytesIO()
    writer.write(output)
    output.seek(0)
    return output

# -------------------- PROCESAR --------------------
if pdfs and len(pdfs) <= 3 and st.session_state.banco:

    if st.button("Procesar PDFs"):
        for pdf in pdfs:
            resultado = enumerar_pdf(pdf)

            st.download_button(
                label=f"Descargar {pdf.name}",
                data=resultado,
                file_name=f"ENUM_{pdf.name}",
                mime="application/pdf"
            )

            # HISTORIAL
            st.session_state.historial.append({
                "nombre": pdf.name
            })

# -------------------- HISTORIAL --------------------
st.markdown("### 🕘 Historial")

if st.session_state.historial:
    for item in st.session_state.historial:
        st.write("📄", item["nombre"])
else:
    st.write("Sin archivos aún")
