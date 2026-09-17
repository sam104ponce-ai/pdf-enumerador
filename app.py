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

st.set_page_config(
    page_title="FlowLedger",
    page_icon="💼",
    layout="centered"
)

st.markdown(
    "<h1 style='text-align:center;'>FlowLedger</h1>",
    unsafe_allow_html=True
)
st.markdown(
    "<h3 style='text-align:center;color:gray;'>Automatización de Movimientos Bancarios</h3>",
    unsafe_allow_html=True
)

# =========================================================
# CONFIGURACIÓN
# =========================================================

# IMPORTANTE:
# El punto decimal debe estar escapado como \.
# Esta expresión detecta, por ejemplo:
# 893.55
# 1,098.09
# 5,708.29

PATRON_MONTO = re.compile(r"^\d{1,3}(?:,\d{3})*\.\d{2}$")

# =========================================================
# FUNCIONES AUXILIARES
# =========================================================

def es_monto(texto):
    return bool(PATRON_MONTO.match(texto.strip()))


def obtener_linea(words, top, tolerancia=3):
    """Obtiene todos los textos que pertenecen a la misma fila."""
    fila = [
        w for w in words
        if abs(float(w["top"]) - float(top)) < tolerancia
    ]
    fila.sort(key=lambda w: float(w["x0"]))
    return fila


def texto_linea(words, top, tolerancia=3):
    fila = obtener_linea(words, top, tolerancia)
    return " ".join(w["text"].strip() for w in fila)


def detectar_columnas_tdd(words):
    """
    Busca EXCLUSIVAMENTE el encabezado de movimientos que contiene:
    FECHA, DESCRIPCION/DESCRIPCIÓN, REFERENCIA, CARGOS y ABONOS.

    Regresa el x1 de CARGOS y ABONOS.
    """
    tops = sorted(set(round(float(w["top"]), 1) for w in words))

    for top in tops:
        fila = obtener_linea(words, top, 3)
        textos = [w["text"].upper().strip() for w in fila]

        tiene_fecha = "FECHA" in textos
        tiene_descripcion = (
            "DESCRIPCION" in textos or
            "DESCRIPCIÓN" in textos
        )
        tiene_referencia = "REFERENCIA" in textos
        tiene_cargos = "CARGOS" in textos
        tiene_abonos = "ABONOS" in textos

        if (
            tiene_fecha
            and tiene_descripcion
            and tiene_referencia
            and tiene_cargos
            and tiene_abonos
        ):
            cargo = next(
                w for w in fila
                if w["text"].upper().strip() == "CARGOS"
            )
            abono = next(
                w for w in fila
                if w["text"].upper().strip() == "ABONOS"
            )

            return float(cargo["x1"]), float(abono["x1"])

    return None, None


def procesar_tdd(file_bytes):
    """
    Enumera por separado:
    Cargos: 1, 2, 3...
    Abonos: 1, 2, 3...

    La clasificación se hace con la posición horizontal del importe.
    """
    packet = BytesIO()
    can = canvas.Canvas(packet)

    contador_cargos = 1
    contador_abonos = 1
    encontrados_cargos = 0
    encontrados_abonos = 0

    with pdfplumber.open(BytesIO(file_bytes)) as pdf:

        # -------------------------------------------------
        # PRIMERO: detectar las columnas reales del PDF
        # -------------------------------------------------
        columnas_por_pagina = []

        for page in pdf.pages:
            words = page.extract_words(use_text_flow=False)

            cargo_x1, abono_x1 = detectar_columnas_tdd(words)

            columnas_por_pagina.append((cargo_x1, abono_x1))

        # -------------------------------------------------
        # SEGUNDO: procesar cada página
        # -------------------------------------------------
        for page_num, page in enumerate(pdf.pages):

            words = page.extract_words(use_text_flow=False)

            if not words:
                can.showPage()
                continue

            cargo_x1, abono_x1 = columnas_por_pagina[page_num]

            # Si no se encontró encabezado en esta página,
            # intentamos reutilizar el de otra página.
            if cargo_x1 is None or abono_x1 is None:
                for cx, ax in columnas_por_pagina:
                    if cx is not None and ax is not None:
                        cargo_x1, abono_x1 = cx, ax
                        break

            montos_usados = set()

            for w in words:

                texto = w["text"].strip()

                # -----------------------------------------
                # Solo importes
                # -----------------------------------------
                if not es_monto(texto):
                    continue

                x0 = float(w["x0"])
                x1 = float(w["x1"])
                top = float(w["top"])

                # Evitar encabezados superiores
                if top < 100:
                    continue

                linea = texto_linea(words, top)
                linea_mayus = linea.upper()

                # -----------------------------------------
                # Excluir filas que NO son movimientos
                # -----------------------------------------
                if "MOVIMIENTOS DE PERIODOS ANTERIORES" in linea_mayus:
                    continue

                if any(
                    palabra in linea_mayus
                    for palabra in [
                        "TOTAL DE MOVIMIENTOS",
                        "TOTAL MOVIMIENTOS",
                        "TOTAL CARGOS",
                        "TOTAL ABONOS",
                        "SALDO INICIAL",
                        "SALDO FINAL"
                    ]
                ):
                    continue

                # Evitar encabezados de columnas
                if any(
                    palabra in linea_mayus
                    for palabra in [
                        "FECHA SALDO",
                        "DESCRIPCION REFERENCIA",
                        "DESCRIPCIÓN REFERENCIA"
                    ]
                ):
                    continue

                # -----------------------------------------
                # Evitar duplicados
                # -----------------------------------------
                key = (
                    texto,
                    round(x0, 1),
                    round(x1, 1),
                    round(top, 1)
                )

                if key in montos_usados:
                    continue

                # -----------------------------------------
                # CLASIFICACIÓN
                #
                # Comparamos el borde derecho x1 del
                # importe contra el borde derecho x1
                # de los encabezados CARGOS y ABONOS.
                #
                # En el PDF real:
                # CARGOS  ≈ 416.63
                # ABONOS  ≈ 460.27
                #
                # Los importes aparecen aproximadamente:
                # CARGOS  ≈ 417.37
                # ABONOS  ≈ 457.84
                # -----------------------------------------

                if cargo_x1 is not None and abono_x1 is not None:

                    distancia_cargo = abs(x1 - cargo_x1)
                    distancia_abono = abs(x1 - abono_x1)

                    # Tolerancia suficientemente amplia para
                    # pequeñas variaciones del PDF.
                    if min(distancia_cargo, distancia_abono) <= 15:

                        y = page.height - top - 6

                        can.setFillColorRGB(1, 0, 0)
                        can.setFont("Helvetica-Bold", 8)

                        if distancia_cargo < distancia_abono:
                            can.drawRightString(
                                x1 + 16,
                                y,
                                str(contador_cargos)
                            )
                            contador_cargos += 1
                            encontrados_cargos += 1

                        else:
                            can.drawRightString(
                                x1 + 16,
                                y,
                                str(contador_abonos)
                            )
                            contador_abonos += 1
                            encontrados_abonos += 1

                        montos_usados.add(key)

            can.showPage()

    can.save()
    packet.seek(0)

    overlay_pdf = PdfReader(packet)
    base_pdf = PdfReader(BytesIO(file_bytes))
    writer = PdfWriter()

    for i, page in enumerate(base_pdf.pages):
        if i < len(overlay_pdf.pages):
            page.merge_page(overlay_pdf.pages[i])
        writer.add_page(page)

    output = BytesIO()
    writer.write(output)
    output.seek(0)

    return (
        output,
        encontrados_cargos,
        encontrados_abonos
    )


# =========================================================
# OPCIONES
# =========================================================

tipo_pdf = st.radio(
    "Selecciona el tipo de Banco:",
    ("BBVA TDC", "BBVA TDD")
)

archivo = st.file_uploader(
    f"Sube tu PDF ({tipo_pdf})",
    type=["pdf"]
)

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
# PROCESAMIENTO
# =========================================================

if archivo:

    if st.button("Procesar PDF"):

        with st.spinner("Procesando PDF..."):

            file_bytes = archivo.read()

            # =================================================
            # BBVA TDD
            # =================================================
            if tipo_pdf == "BBVA TDD":

                output_pdf, total_cargos, total_abonos = procesar_tdd(
                    file_bytes
                )

                nombre, ext = os.path.splitext(archivo.name)
                pdf_final = f"{nombre}_ENUMERADO{ext}"

                st.success("✅ PDF procesado correctamente")

                col1, col2 = st.columns(2)

                with col1:
                    st.metric(
                        "Cargos enumerados",
                        total_cargos
                    )

                with col2:
                    st.metric(
                        "Abonos enumerados",
                        total_abonos
                    )

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
            # BBVA TDC
            # =================================================
            else:

                packet = BytesIO()
                can = canvas.Canvas(packet)

                contador = 1
                en_movimientos = False

                with pdfplumber.open(BytesIO(file_bytes)) as pdf:

                    for page in pdf.pages:

                        words = page.extract_words(
                            use_text_flow=True
                        )

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

                            if (
                                "TARJETA" in texto_mayus
                                and "EMPRESARIAL" in texto_mayus
                            ):
                                continue

                            linea_texto = texto_linea(
                                words,
                                float(w["top"])
                            )

                            linea_mayus = linea_texto.upper()

                            if "CAPITAL DE PROMOCIÓN" in linea_mayus:
                                continue

                            if any(
                                p in linea_mayus
                                for p in [
                                    "TOTAL IMPORTES",
                                    "TOTAL",
                                    "IMPORTE TOTAL"
                                ]
                            ):
                                continue

                            if not es_monto(texto):
                                continue

                            x0 = float(w["x0"])
                            x1 = float(w["x1"])
                            top = float(w["top"])
                            y = page.height - top - 2

                            # Para TDC usamos una zona amplia alrededor
                            # de los importes encontrados.
                            if not (x0 > 0 and x1 > x0):
                                continue

                            key = (
                                texto,
                                round(x0, 1),
                                round(top, 1)
                            )

                            if key in montos_usados:
                                continue

                            can.setFillColorRGB(1, 0, 0)
                            can.setFont(
                                "Helvetica-Bold",
                                8
                            )

                            can.drawRightString(
                                x1 + 15,
                                y,
                                str(contador)
                            )

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
                        page.merge_page(
                            overlay_pdf.pages[i]
                        )

                    writer.add_page(page)

                output_pdf = BytesIO()
                writer.write(output_pdf)
                output_pdf.seek(0)

                nombre, ext = os.path.splitext(
                    archivo.name
                )

                pdf_final = f"{nombre}_ENUMERADO{ext}"

                st.success(
                    f"✅ Total enumerados: {contador - 1}"
                )

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

    for i, item in enumerate(
        st.session_state.historial_pdfs
    ):

        col1, col2, col3 = st.columns([4, 1, 1])

        with col1:
            st.write(
                f"{item['nombre']} ({item['banco']})"
            )

        with col2:
            st.download_button(
                "⬇️",
                item["pdf_bytes"],
                file_name=item["nombre"],
                mime="application/pdf",
                key=f"download_historial_{i}"
            )

        with col3:
            if st.button(
                "🗑️",
                key=f"eliminar_{i}"
            ):
                indices_a_eliminar.append(i)

    for i in sorted(
        indices_a_eliminar,
        reverse=True
    ):
        st.session_state.historial_pdfs.pop(i)
