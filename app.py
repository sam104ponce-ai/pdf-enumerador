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

st.set_page_config(page_title="FlowLedger", page_icon="💼", layout="centered")
st.markdown("<h1 style='text-align:center;'>FlowLedger</h1>", unsafe_allow_html=True)
st.markdown("<h3 style='text-align:center;color:gray;'>Automatización de Movimientos Bancarios</h3>", unsafe_allow_html=True)

# =========================================================
# CONFIGURACIÓN
# =========================================================

# Importe de los movimientos BBVA
patron_monto = re.compile(r'^\d{1,3}(?:,\d{3})*\.\d{2}$')

# =========================================================
# OPCIONES
# =========================================================

tipo_pdf = st.radio("Selecciona el tipo de Banco:", ("BBVA TDC", "BBVA TDD"))
archivo = st.file_uploader(f"Sube tu PDF ({tipo_pdf})", type=["pdf"])

# =========================================================
# HISTORIAL
# =========================================================

if "historial_pdfs" not in st.session_state:
    st.session_state.historial_pdfs = []

def agregar_a_historial(nombre, bytes_pdf, banco):
    st.session_state.historial_pdfs.append({
        "nombre": nombre,
        "pdf_bytes": bytes_pdf,
        "banco": banco
    })

# =========================================================
# FUNCIONES TDD
# =========================================================

def misma_fila(words, top, tolerancia=3):
    return [
        ww for ww in words
        if abs(float(ww["top"]) - float(top)) < tolerancia
    ]


def es_fila_movimiento(words, top):
    """
    Una fila de movimiento BBVA contiene una fecha DD/MES.
    Esto evita tomar los importes de los cuadros de resumen,
    saldos y totales.
    """
    fila = misma_fila(words, top)
    texto = " ".join(ww["text"] for ww in sorted(fila, key=lambda z: float(z["x0"])))
    return bool(re.search(r'^\d{2}/[A-Z]{3}\s+\d{2}/[A-Z]{3}\b', texto))


def procesar_bbva_tdd(file_bytes):
    """
    Procesa el formato BBVA de movimientos:
    - Enumera CARGOS de forma independiente: 1, 2, 3...
    - Enumera ABONOS de forma independiente: 1, 2, 3...
    - Ignora los saldos de OPERACIÓN y LIQUIDACIÓN.
    - Ignora los cuadros de resumen de las páginas posteriores.

    Este formato tiene las columnas:
        CARGOS -> x1 aproximado 397.8
        ABONOS -> x1 aproximado 455.7

    La posición x1 se usa porque BBVA alinea los importes a la derecha.
    """

    packet = BytesIO()
    can = canvas.Canvas(packet)

    contador_cargos = 1
    contador_abonos = 1

    # Posiciones reales del formato BBVA TDC/TDD de referencia.
    # CARGOS: los importes terminan aproximadamente en x=397.8
    # ABONOS: los importes terminan aproximadamente en x=455.7
    X1_CARGO = 397.8
    X1_ABONO = 455.7
    TOLERANCIA_X = 2.5

    with pdfplumber.open(BytesIO(file_bytes)) as pdf:

        for page in pdf.pages:

            words = page.extract_words(use_text_flow=False)

            if not words:
                can.showPage()
                continue

            montos_usados = set()

            for w in words:

                texto = w["text"].strip()

                if not patron_monto.match(texto):
                    continue

                x0 = float(w["x0"])
                x1 = float(w["x1"])
                top = float(w["top"])

                # ---------------------------------------------
                # IDENTIFICAR LA FILA
                # ---------------------------------------------
                fila = [
                    ww for ww in words
                    if abs(float(ww["top"]) - top) < 3
                ]

                fila.sort(key=lambda z: float(z["x0"]))

                texto_fila = " ".join(
                    ww["text"].strip()
                    for ww in fila
                )

                texto_fila_mayus = texto_fila.upper()

                # ---------------------------------------------
                # SOLO MOVIMIENTOS REALES
                # ---------------------------------------------
                #
                # En este formato cada movimiento empieza con:
                # DD/MES DD/MES
                #
                # Esto evita tomar:
                # - saldos iniciales
                # - cuadros de resumen
                # - porcentajes
                # - totales
                # - importes de otras secciones
                # ---------------------------------------------

                if not re.search(
                    r'^\d{2}/[A-Z]{3}\s+\d{2}/[A-Z]{3}\b',
                    texto_fila
                ):
                    continue

                # ---------------------------------------------
                # EXCLUSIONES
                # ---------------------------------------------

                if "MOVIMIENTOS DE PERIODOS ANTERIORES" in texto_fila_mayus:
                    continue

                if any(
                    p in texto_fila_mayus
                    for p in [
                        "TOTAL DE MOVIMIENTOS",
                        "TOTAL MOVIMIENTOS",
                        "TOTAL IMPORTE",
                        "SALDO INICIAL",
                        "SALDO FINAL"
                    ]
                ):
                    continue

                # ---------------------------------------------
                # SOLO COLUMNAS CARGOS / ABONOS
                # ---------------------------------------------
                #
                # Los saldos de operación y liquidación tienen
                # x1 aproximadamente 526.3 y 594.0, por lo
                # que automáticamente quedan fuera.
                # ---------------------------------------------

                distancia_cargo = abs(x1 - X1_CARGO)
                distancia_abono = abs(x1 - X1_ABONO)

                if min(distancia_cargo, distancia_abono) > TOLERANCIA_X:
                    continue

                key = (
                    texto,
                    round(x0, 2),
                    round(x1, 2),
                    round(top, 2)
                )

                if key in montos_usados:
                    continue

                y = page.height - top - 6

                can.setFillColorRGB(1, 0, 0)
                can.setFont("Helvetica-Bold", 8)

                # ---------------------------------------------
                # ENUMERACIÓN INDEPENDIENTE
                # ---------------------------------------------

                if distancia_cargo < distancia_abono:

                    can.drawRightString(
                        x1 + 16,
                        y,
                        str(contador_cargos)
                    )

                    contador_cargos += 1

                else:

                    can.drawRightString(
                        x1 + 16,
                        y,
                        str(contador_abonos)
                    )

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

    output = BytesIO()
    writer.write(output)
    output.seek(0)

    return (
        output,
        contador_cargos - 1,
        contador_abonos - 1
    )


# =========================================================
# PROCESAMIENTO
# =========================================================

if archivo:

    if st.button("Procesar PDF"):

        with st.spinner("Procesando…"):

            file_bytes = archivo.read()

            # =================================================
            # BBVA TDC
            # =================================================

            if tipo_pdf == "BBVA TDC":

                packet = BytesIO()
                can = canvas.Canvas(packet)

                contador = 1
                en_movimientos = False

                with pdfplumber.open(BytesIO(file_bytes)) as pdf:

                    for page in pdf.pages:

                        words = page.extract_words(use_text_flow=True)

                        if not words:
                            can.showPage()
                            continue

                        montos_usados = set()

                        for w in words:

                            texto = w["text"].strip()
                            texto_mayus = texto.upper()

                            if not en_movimientos:
                                if "MOVIMIENTOS" in texto_mayus:
                                    en_movimientos = True
                                else:
                                    continue

                            if "TARJETA" in texto_mayus and "EMPRESARIAL" in texto_mayus:
                                continue

                            linea_texto = " ".join(
                                ww["text"] + " "
                                for ww in words
                                if abs(float(ww["top"]) - float(w["top"])) < 3
                            )

                            linea_mayus = linea_texto.upper()

                            if "CAPITAL DE PROMOCIÓN" in linea_mayus:
                                continue

                            if any(
                                p in linea_mayus
                                for p in ["TOTAL IMPORTES", "TOTAL", "IMPORTE TOTAL"]
                            ):
                                continue

                            if not patron_monto.match(texto):
                                continue

                            x0 = float(w["x0"])
                            x1 = float(w["x1"])
                            top = float(w["top"])
                            y = page.height - top - 2

                            if not (x0 > 0 and x1 > x0):
                                continue

                            key = (texto, round(x0, 1), round(top, 1))

                            if key in montos_usados:
                                continue

                            can.setFillColorRGB(1, 0, 0)
                            can.setFont("Helvetica-Bold", 8)
                            can.drawRightString(x1 + 15, y, str(contador))

                            contador += 1
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

                output_pdf = BytesIO()
                writer.write(output_pdf)
                output_pdf.seek(0)

                nombre, ext = os.path.splitext(archivo.name)
                pdf_final = f"{nombre}_ENUMERADO{ext}"

                st.success(f"✅ Total enumerados: {contador - 1}")

                st.download_button(
                    label="📥 Descargar PDF Enumerado",
                    data=output_pdf,
                    file_name=pdf_final,
                    mime="application/pdf"
                )

                agregar_a_historial(
                    pdf_final,
                    output_pdf.getvalue(),
                    tipo_pdf
                )

            # =================================================
            # BBVA TDD
            # =================================================

            else:

                output_pdf, total_cargos, total_abonos = procesar_bbva_tdd(
                    file_bytes
                )

                nombre, ext = os.path.splitext(archivo.name)
                pdf_final = f"{nombre}_ENUMERADO{ext}"

                st.success("✅ PDF procesado correctamente")

                st.write(f"**Cargos enumerados:** {total_cargos}")
                st.write(f"**Abonos enumerados:** {total_abonos}")

                st.download_button(
                    label="📥 Descargar PDF Enumerado",
                    data=output_pdf,
                    file_name=pdf_final,
                    mime="application/pdf"
                )

                agregar_a_historial(
                    pdf_final,
                    output_pdf.getvalue(),
                    tipo_pdf
                )


# =========================================================
# HISTORIAL VISUAL
# =========================================================

if st.session_state.historial_pdfs:

    st.markdown("### 🗂 Historial de PDFs procesados")

    indices_a_eliminar = []

    for i, item in enumerate(st.session_state.historial_pdfs):

        col1, col2, col3 = st.columns([4, 1, 1])

        with col1:
            st.write(f"{item['nombre']} ({item['banco']})")

        with col2:
            st.download_button(
                "⬇️",
                item["pdf_bytes"],
                file_name=item["nombre"],
                mime="application/pdf",
                key=f"download_historial_{i}"
            )

        with col3:
            if st.button("🗑️", key=f"eliminar_{i}"):
                indices_a_eliminar.append(i)

    for i in sorted(indices_a_eliminar, reverse=True):
        st.session_state.historial_pdfs.pop(i)
