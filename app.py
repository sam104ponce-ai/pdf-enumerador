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

# BBVA TDD
# Rangos calibrados para el PDF enviado:
# CARGOS: x1 aproximadamente 417
# ABONOS: x1 aproximadamente 458

X_CARGO_MIN, X_CARGO_MAX = 408, 425
X_ABONO_MIN, X_ABONO_MAX = 448, 468

patron_monto = re.compile(
    r'^\d{1,3}(?:,\d{3})*\.\d{2}$'
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

        with st.spinner("Procesando…"):

            file_bytes = archivo.read()

            # =========================================================
            # BBVA TDC
            # =========================================================

            if tipo_pdf == "BBVA TDC":

                X_CARGO_MIN_TDC, X_CARGO_MAX_TDC = None, None

                with pdfplumber.open(BytesIO(file_bytes)) as pdf:

                    page0 = pdf.pages[0]
                    words0 = page0.extract_words()

                    for w in words0:

                        texto = w["text"].upper()

                        if "IMPORTE" in texto:

                            x_base = float(w["x0"])

                            posibles = []

                            for ww in words0:

                                t = ww["text"].strip()

                                if patron_monto.match(t):

                                    if abs(float(ww["x0"]) - x_base) < 120:

                                        posibles.append(
                                            float(ww["x0"])
                                        )

                            if posibles:

                                X_CARGO_MIN_TDC = min(posibles) - 10
                                X_CARGO_MAX_TDC = max(posibles) + 10

                            break

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

                            # -----------------------------------------
                            # Detectar inicio de movimientos
                            # -----------------------------------------

                            if not en_movimientos:

                                if "MOVIMIENTOS" in texto_mayus:

                                    en_movimientos = True

                                else:

                                    continue

                            # -----------------------------------------
                            # Ignorar tarjeta empresarial
                            # -----------------------------------------

                            if (
                                "TARJETA" in texto_mayus
                                and "EMPRESARIAL" in texto_mayus
                            ):
                                continue

                            # -----------------------------------------
                            # Texto completo de la fila
                            # -----------------------------------------

                            linea_texto = ""

                            for ww in words:

                                if abs(
                                    float(ww["top"])
                                    - float(w["top"])
                                ) < 3:

                                    linea_texto += (
                                        ww["text"] + " "
                                    )

                            linea_mayus = linea_texto.upper()

                            # -----------------------------------------
                            # Ignorar capital de promoción
                            # -----------------------------------------

                            if "CAPITAL DE PROMOCIÓN" in linea_mayus:
                                continue

                            # -----------------------------------------
                            # Excluir totales
                            # -----------------------------------------

                            if any(
                                p in linea_mayus
                                for p in [
                                    "TOTAL IMPORTES",
                                    "TOTAL",
                                    "IMPORTE TOTAL"
                                ]
                            ):
                                continue

                            # -----------------------------------------
                            # Solo importes
                            # -----------------------------------------

                            if not patron_monto.match(texto):
                                continue

                            x0 = float(w["x0"])
                            x1 = float(w["x1"])
                            top = float(w["top"])

                            y = page.height - top - 2

                            # -----------------------------------------
                            # FILTRO TDC
                            #
                            # Si no se pudieron detectar los rangos,
                            # no hacemos una comparación contra None.
                            # -----------------------------------------

                            if (
                                X_CARGO_MIN_TDC is not None
                                and X_CARGO_MAX_TDC is not None
                                and not (
                                    X_CARGO_MIN_TDC
                                    <= x0
                                    <= X_CARGO_MAX_TDC
                                )
                            ):
                                continue

                            # -----------------------------------------
                            # Evitar duplicados
                            # -----------------------------------------

                            key = (
                                texto,
                                round(x0, 1),
                                round(top, 1)
                            )

                            if key in montos_usados:
                                continue

                            # -----------------------------------------
                            # Enumerar
                            # -----------------------------------------

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
                base_pdf = PdfReader(
                    BytesIO(file_bytes)
                )

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

                st.success(
                    f"✅ Total enumerados: {contador - 1}"
                )

                # -----------------------------------------
                # Nombre del PDF
                # -----------------------------------------

                nombre, ext = os.path.splitext(
                    archivo.name
                )

                pdf_final = (
                    f"{nombre}_ENUMERADO{ext}"
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
            # BBVA TDD
            # =========================================================

            else:

                nombre, ext = os.path.splitext(
                    archivo.name
                )

                pdf_final = (
                    f"{nombre}_ENUMERADO{ext}"
                )

                packet = BytesIO()

                can = canvas.Canvas(packet)

                contador_cargos = 1
                contador_abonos = 1

                with pdfplumber.open(
                    BytesIO(file_bytes)
                ) as pdf:

                    for page in pdf.pages:

                        words = page.extract_words(
                            use_text_flow=True
                        )

                        if not words:

                            can.showPage()
                            continue

                        montos_usados = set()

                        for w in words:

                            t = w["text"].strip()

                            # -----------------------------------------
                            # Solo importes
                            # -----------------------------------------

                            if not patron_monto.match(t):
                                continue

                            x0 = float(w["x0"])
                            x1 = float(w["x1"])
                            top = float(w["top"])

                            y = page.height - top - 6

                            # -----------------------------------------
                            # Ignorar encabezados
                            # -----------------------------------------

                            if top < 120:
                                continue

                            # -----------------------------------------
                            # Montos de la misma fila
                            # -----------------------------------------

                            linea_montos = []

                            for ww in words:

                                if abs(
                                    float(ww["top"]) - top
                                ) < 3:

                                    texto = ww["text"].strip()

                                    if patron_monto.match(
                                        texto
                                    ):

                                        linea_montos.append({
                                            "text": texto,
                                            "x0": float(
                                                ww["x0"]
                                            ),
                                            "x1": float(
                                                ww["x1"]
                                            )
                                        })

                            linea_montos = sorted(
                                linea_montos,
                                key=lambda x: x["x0"]
                            )

                            # -----------------------------------------
                            # Ignorar segundo monto cuando
                            # existen 3 o más
                            # -----------------------------------------

                            ignorar = False

                            if len(linea_montos) >= 3:

                                for i, m in enumerate(
                                    linea_montos
                                ):

                                    if (
                                        m["text"] == t
                                        and abs(
                                            m["x0"] - x0
                                        ) < 1
                                    ):

                                        if i == 1:

                                            ignorar = True

                            if ignorar:
                                continue

                            # -----------------------------------------
                            # Texto completo de la fila
                            # -----------------------------------------

                            linea_texto = ""

                            for ww in words:

                                if abs(
                                    float(ww["top"]) - top
                                ) < 3:

                                    linea_texto += (
                                        ww["text"] + " "
                                    )

                            linea_mayus = (
                                linea_texto.upper()
                            )

                            # -----------------------------------------
                            # Ignorar movimientos de períodos
                            # anteriores
                            # -----------------------------------------

                            if (
                                "MOVIMIENTOS DE PERIODOS ANTERIORES"
                                in linea_mayus
                            ):
                                continue

                            # -----------------------------------------
                            # Excluir saldos, operaciones,
                            # liquidaciones y totales
                            # -----------------------------------------

                            if (
                                "P14 TOTAL PLAY"
                                not in linea_mayus
                            ):

                                if any(
                                    p in linea_mayus
                                    for p in [
                                        "SALDO",
                                        "OPERACION",
                                        "OPERACIÓN",
                                        "LIQUIDACION",
                                        "LIQUIDACIÓN",
                                        "TOTAL"
                                    ]
                                ):
                                    continue

                            # -----------------------------------------
                            # Evitar duplicados
                            # -----------------------------------------

                            key = (
                                t,
                                round(top, 1),
                                round(x0, 1)
                            )

                            if key in montos_usados:
                                continue

                            # =================================================
                            # CARGOS
                            # =================================================

                            if (
                                X_CARGO_MIN
                                <= x1
                                <= X_CARGO_MAX
                            ):

                                can.setFillColorRGB(
                                    1, 0, 0
                                )

                                can.setFont(
                                    "Helvetica-Bold",
                                    8
                                )

                                can.drawRightString(
                                    x1 + 16,
                                    y,
                                    str(
                                        contador_cargos
                                    )
                                )

                                contador_cargos += 1

                                montos_usados.add(
                                    key
                                )

                                continue

                            # =================================================
                            # ABONOS
                            # =================================================

                            if (
                                X_ABONO_MIN
                                <= x1
                                <= X_ABONO_MAX
                            ):

                                can.setFillColorRGB(
                                    1, 0, 0
                                )

                                can.setFont(
                                    "Helvetica-Bold",
                                    8
                                )

                                can.drawRightString(
                                    x1 + 16,
                                    y,
                                    str(
                                        contador_abonos
                                    )
                                )

                                contador_abonos += 1

                                montos_usados.add(
                                    key
                                )

                        can.showPage()

                can.save()
                packet.seek(0)

                # =========================================================
                # UNIR PDF ORIGINAL + ENUMERACIÓN
                # =========================================================

                overlay_pdf = PdfReader(packet)

                base_pdf = PdfReader(
                    BytesIO(file_bytes)
                )

                writer = PdfWriter()

                for i in range(
                    len(base_pdf.pages)
                ):

                    page = base_pdf.pages[i]

                    if i < len(
                        overlay_pdf.pages
                    ):

                        page.merge_page(
                            overlay_pdf.pages[i]
                        )

                    writer.add_page(page)

                output = BytesIO()

                writer.write(output)

                output.seek(0)

                # =========================================================
                # RESULTADOS
                # =========================================================

                st.success(
                    f"✅ Listo: {pdf_final}"
                )

                st.write(
                    f"Cargos: {contador_cargos - 1}"
                )

                st.write(
                    f"Abonos: {contador_abonos - 1}"
                )

                st.download_button(
                    "⬇️ Descargar PDF",
                    output,
                    file_name=pdf_final,
                    mime="application/pdf"
                )

                agregar_a_historial(
                    pdf_final,
                    output.getvalue(),
                    tipo_pdf
                )


# =========================================================
# HISTORIAL VISUAL
# =========================================================

if st.session_state.historial_pdfs:

    st.markdown(
        "### 🗂 Historial de PDFs procesados"
    )

    indices_a_eliminar = []

    for i, item in enumerate(
        st.session_state.historial_pdfs
    ):

        col1, col2, col3 = st.columns(
            [4, 1, 1]
        )

        with col1:

            st.write(
                f"{item['nombre']} "
                f"({item['banco']})"
            )

        with col2:

            st.download_button(
                "⬇️",
                item["pdf_bytes"],
                file_name=item["nombre"],
                mime="application/pdf",
                key=f"descargar_{i}"
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
