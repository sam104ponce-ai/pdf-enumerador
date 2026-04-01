import streamlit as st
import pdfplumber
from reportlab.pdfgen import canvas
from PyPDF2 import PdfReader, PdfWriter
from io import BytesIO
import re
import os

# ===============================
# CONFIGURACIÓN GENERAL
# ===============================
st.set_page_config(
    page_title="ContaFlow",
    page_icon="📊",
    layout="centered"
)

st.title("🏢 ContaFlow")
st.caption("Automatización de enumeración de movimientos")

# ===============================
# FUNCIÓN PROCESADORA
# ===============================
def procesar_pdf(uploaded_file):

    X_CARGO_MIN, X_CARGO_MAX = 290, 380
    X_ABONO_MIN, X_ABONO_MAX = 390, 480

    patron_monto = re.compile(r'^\d{1,3}(?:,\d{3})*\.\d{2}$')

    nombre, ext = os.path.splitext(uploaded_file.name)
    pdf_final = f"{nombre}_ENUMERADO{ext}"

    packet = BytesIO()
    can = canvas.Canvas(packet)

    contador_cargos = 1
    contador_abonos = 1

    with pdfplumber.open(uploaded_file) as pdf:
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

                # ===============================
                # MONTOS EN MISMA FILA
                # ===============================
                linea_montos = []
                for ww in words:
                    if abs(float(ww["top"]) - top) < 3:
                        texto = ww["text"].strip()
                        if patron_monto.match(texto):
                            linea_montos.append({
                                "text": texto,
                                "x0": float(ww["x0"]),
                                "x1": float(ww["x1"])
                            })

                linea_montos = sorted(linea_montos, key=lambda x: x["x0"])

                # ===============================
                # IGNORAR MONTO INTERMEDIO
                # ===============================
                ignorar = False
                if len(linea_montos) >= 3:
                    for i, m in enumerate(linea_montos):
                        if m["text"] == t and abs(m["x0"] - x0) < 1:
                            if i == 1:
                                ignorar = True

                if ignorar:
                    continue

                # ===============================
                # TEXTO COMPLETO DE LA LÍNEA
                # ===============================
                linea_texto = ""
                for ww in words:
                    if abs(float(ww["top"]) - top) < 3:
                        linea_texto += ww["text"] + " "

                linea_mayus = linea_texto.upper()

                # ===============================
                # FILTROS
                # ===============================
                if "MOVIMIENTOS DE PERIODOS ANTERIORES" in linea_mayus:
                    continue

                if "P14 TOTAL PLAY" not in linea_mayus:
                    if any(p in linea_mayus for p in [
                        "SALDO","OPERACION","OPERACIÓN",
                        "LIQUIDACION","LIQUIDACIÓN","TOTAL"
                    ]):
                        continue

                key = (t, round(top, 1), round(x0, 1))
                if key in montos_usados:
                    continue

                # ===============================
                # DETECCIÓN DE CÓDIGOS
                # ===============================
                contiene_codigo = (
                    any(c in linea_mayus for c in [
                        "P14","V44","V47","V43","T93",
                        "V41","K65","V40","T92","K64","C48"
                    ])
                    or "P14 TOTAL PLAY" in linea_mayus
                )

                es_primer_monto = any(
                    abs(m["x0"] - x0) < 2 for m in linea_montos[:1]
                )

                # ===============================
                # CARGOS
                # ===============================
                if (
                    (X_CARGO_MIN <= x0 <= X_CARGO_MAX)
                    or (contiene_codigo and es_primer_monto)
                    or ("P14 TOTAL PLAY" in linea_mayus)
                ):
                    can.setFillColorRGB(1, 0, 0)
                    can.setFont("Helvetica-Bold", 8)
                    can.drawRightString(x1 + 14, y, str(contador_cargos))
                    contador_cargos += 1
                    montos_usados.add(key)
                    continue

                # ===============================
                # ABONOS
                # ===============================
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
    base_pdf = PdfReader(uploaded_file)

    writer = PdfWriter()

    for i in range(len(base_pdf.pages)):
        page = base_pdf.pages[i]
        if i < len(overlay_pdf.pages):
            page.merge_page(overlay_pdf.pages[i])
        writer.add_page(page)

    output = BytesIO()
    writer.write(output)
    output.seek(0)

    return output, pdf_final


# ===============================
# PESTAÑAS
# ===============================
tab1, tab2, tab3 = st.tabs([
    "🏦 BBVA TDD",
    "💳 BBVA TDC",
    "🏦 BANAMEX"
])

# ===============================
# BBVA TDD
# ===============================
with tab1:
    st.subheader("BBVA - Débito")
    file = st.file_uploader("Subir PDF", type="pdf", key="tdd")

    if file:
        st.info("Procesando...")
        output, nombre = procesar_pdf(file)
        st.success("Listo")
        st.download_button("Descargar PDF ENUMERADO", output, nombre)

# ===============================
# BBVA TDC
# ===============================
with tab2:
    st.subheader("BBVA - Crédito")
    file = st.file_uploader("Subir PDF", type="pdf", key="tdc")

    if file:
        st.info("Procesando...")
        output, nombre = procesar_pdf(file)
        st.success("Listo")
        st.download_button("Descargar PDF ENUMERADO", output, nombre)

# ===============================
# BANAMEX
# ===============================
with tab3:
    st.subheader("Banamex")
    file = st.file_uploader("Subir PDF", type="pdf", key="banamex")

    if file:
        st.info("Procesando...")
        output, nombre = procesar_pdf(file)
        st.success("Listo")
        st.download_button("Descargar PDF ENUMERADO", output, nombre)
