```python
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
    "<h3 style='text-align:center;color:gray;'>"
    "Automatización de Movimientos Bancarios"
    "</h3>",
    unsafe_allow_html=True
)


# =========================================================
# PATRÓN DE MONTOS
# =========================================================

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
# FUNCIONES AUXILIARES TDD
# =========================================================

def obtener_columnas_tdd(words):
    """
    Busca el encabezado real de movimientos:

    FECHA ... CARGOS ABONOS ...

    y obtiene la posición horizontal de las columnas.

    NO usa coordenadas fijas.
    """

    # Agrupamos palabras por altura (misma línea)
    lineas = {}

    for w in words:

        top = round(float(w["top"]), 1)

        if top not in lineas:
            lineas[top] = []

        lineas[top].append(w)


    for top, linea in lineas.items():

        linea_ordenada = sorted(
            linea,
            key=lambda x: float(x["x0"])
        )

        textos = [
            w["text"].strip().upper()
            for w in linea_ordenada
        ]

        # Buscamos una línea que tenga CARGOS y ABONOS
        if "CARGOS" in textos and "ABONOS" in textos:

            cargo_word = None
            abono_word = None

            for w in linea_ordenada:

                texto = w["text"].strip().upper()

                if texto == "CARGOS":
                    cargo_word = w

                elif texto == "ABONOS":
                    abono_word = w


            if cargo_word is not None and abono_word is not None:

                centro_cargo = (
                    float(cargo_word["x0"]) +
                    float(cargo_word["x1"])
                ) / 2

                centro_abono = (
                    float(abono_word["x0"]) +
                    float(abono_word["x1"])
                ) / 2

                return {
                    "cargo": centro_cargo,
                    "abono": centro_abono
                }

    return None


def detectar_columnas_tdd(pdf):

    """
    Recorre las páginas hasta encontrar
    el encabezado real de CARGOS / ABONOS.
    """

    for page in pdf.pages:

        words = page.extract_words(
            use_text_flow=False
        )

        columnas = obtener_columnas_tdd(words)

        if columnas is not None:
            return columnas

    return None


def distancia_columna(x_centro, columna):

    return abs(x_centro - columna)


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

                X_CARGO_MIN_TDC = None
                X_CARGO_MAX_TDC = None

                # ---------------------------------------------
                # Detectar columna TDC
                # ---------------------------------------------

                with pdfplumber.open(
                    BytesIO(file_bytes)
                ) as pdf:

                    page0 = pdf.pages[0]

                    words0 = page0.extract_words(
                        use_text_flow=False
                    )

                    for w in words0:

                        texto = w["text"].upper()

                        if "IMPORTE" in texto:

                            x_base = float(w["x0"])

                            posibles = []

                            for ww in words0:

                                t = ww["text"].strip()

                                if patron_monto.match(t):

                                    if (
                                        abs(
                                            float(ww["x0"])
                                            - x_base
                                        ) < 120
                                    ):

                                        posibles.append(
                                            float(ww["x0"])
                                        )

                            if posibles:

                                X_CARGO_MIN_TDC = (
                                    min(posibles) - 10
                                )

                                X_CARGO_MAX_TDC = (
                                    max(posibles) + 10
                                )

                            break


                # ---------------------------------------------
                # Crear overlay
                # ---------------------------------------------

                packet = BytesIO()

                can = canvas.Canvas(packet)

                contador = 1

                en_movimientos = False


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

                            texto = w["text"].strip()

                            texto_mayus = texto.upper()


                            # ---------------------------------
                            # Esperar sección MOVIMIENTOS
                            # ---------------------------------

                            if not en_movimientos:

                                if "MOVIMIENTOS" in texto_mayus:

                                    en_movimientos = True

                                else:

                                    continue


                            # ---------------------------------
                            # Excepciones
                            # ---------------------------------

                            if (
                                "TARJETA" in texto_mayus
                                and
                                "EMPRESARIAL" in texto_mayus
                            ):
                                continue


                            linea_texto = ""

                            for ww in words:

                                if (
                                    abs(
                                        float(ww["top"])
                                        - float(w["top"])
                                    ) < 3
                                ):

                                    linea_texto += (
                                        ww["text"] + " "
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


                            if not patron_monto.match(texto):
                                continue


                            x0 = float(w["x0"])
                            x1 = float(w["x1"])
                            top = float(w["top"])


                            # ---------------------------------
                            # Protección contra None
                            # ---------------------------------

                            if (
                                X_CARGO_MIN_TDC is None
                                or
                                X_CARGO_MAX_TDC is None
                            ):
                                continue


                            if not (
                                X_CARGO_MIN_TDC
                                <= x0
                                <= X_CARGO_MAX_TDC
                            ):
                                continue


                            y = (
                                page.height
                                - top
                                - 2
                            )


                            key = (
                                texto,
                                round(x0, 1),
                                round(top, 1)
                            )


                            if key in montos_usados:
                                continue


                            can.setFillColorRGB(
                                1, 0, 0
                            )

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


                # ---------------------------------------------
                # Unir overlay con PDF original
                # ---------------------------------------------

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


                output_pdf = BytesIO()

                writer.write(output_pdf)

                output_pdf.seek(0)


                # ---------------------------------------------
                # Resultado
                # ---------------------------------------------

                st.success(
                    f"✅ Total enumerados: "
                    f"{contador - 1}"
                )


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


            # =================================================
            # BBVA TDD
            # =================================================

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


                # =================================================
                # PASO 1
                # Detectar automáticamente CARGOS / ABONOS
                # =================================================

                with pdfplumber.open(
                    BytesIO(file_bytes)
                ) as pdf:

                    columnas = detectar_columnas_tdd(
                        pdf
                    )


                # ---------------------------------------------
                # Si no encuentra encabezado
                # ---------------------------------------------

                if columnas is None:

                    st.error(
                        "❌ No pude detectar automáticamente "
                        "las columnas CARGOS y ABONOS "
                        "en este PDF."
                    )

                    st.stop()


                centro_cargo = columnas["cargo"]
                centro_abono = columnas["abono"]


                # =================================================
                # PASO 2
                # Procesar movimientos
                # =================================================

                with pdfplumber.open(
                    BytesIO(file_bytes)
                ) as pdf:

                    for page in pdf.pages:

                        words = page.extract_words(
                            use_text_flow=False
                        )


                        if not words:

                            can.showPage()

                            continue


                        montos_usados = set()


                        # -----------------------------------------
                        # Ordenar palabras
                        # -----------------------------------------

                        words = sorted(
                            words,
                            key=lambda w: (
                                float(w["top"]),
                                float(w["x0"])
                            )
                        )


                        for w in words:

                            t = w["text"].strip()


                            # -------------------------------------
                            # Solo importes
                            # -------------------------------------

                            if not patron_monto.match(t):
                                continue


                            x0 = float(w["x0"])
                            x1 = float(w["x1"])
                            top = float(w["top"])


                            # -------------------------------------
                            # Ignorar encabezados superiores
                            # -------------------------------------

                            if top < 120:
                                continue


                            # -------------------------------------
                            # Texto completo de la fila
                            # -------------------------------------

                            fila = []

                            for ww in words:

                                if (
                                    abs(
                                        float(ww["top"])
                                        - top
                                    ) < 3
                                ):

                                    fila.append(ww)


                            fila = sorted(
                                fila,
                                key=lambda x:
                                float(x["x0"])
                            )


                            linea_texto = " ".join(
                                ww["text"].strip()
                                for ww in fila
                            )


                            linea_mayus = (
                                linea_texto.upper()
                            )


                            # -------------------------------------
                            # Excluir filas que NO son movimientos
                            # -------------------------------------

                            if (
                                "MOVIMIENTOS DE PERIODOS "
                                "ANTERIORES"
                                in linea_mayus
                            ):
                                continue


                            if any(
                                p in linea_mayus
                                for p in [
                                    "TOTAL IMPORTES",
                                    "IMPORTE TOTAL",
                                    "SALDO INICIAL",
                                    "SALDO ANTERIOR"
                                ]
                            ):
                                continue


                            # -------------------------------------
                            # Resumen de movimientos
                            # -------------------------------------

                            if any(
                                p in linea_mayus
                                for p in [
                                    "TOTAL MOVIMIENTOS",
                                    "TOTAL CARGOS",
                                    "TOTAL ABONOS"
                                ]
                            ):
                                continue


                            # -------------------------------------
                            # No contar encabezados
                            # -------------------------------------

                            if (
                                "CARGOS" in linea_mayus
                                and
                                "ABONOS" in linea_mayus
                            ):
                                continue


                            # -------------------------------------
                            # Casos de saldo / liquidación
                            # -------------------------------------

                            if any(
                                p in linea_mayus
                                for p in [
                                    "LIQUIDACION",
                                    "LIQUIDACIÓN"
                                ]
                            ):

                                # Si la fila contiene una
                                # descripción de movimiento
                                # además de liquidación,
                                # no la descartamos automáticamente.
                                pass


                            # -------------------------------------
                            # Centro del importe
                            # -------------------------------------

                            centro_importe = (
                                x0 + x1
                            ) / 2


                            distancia_cargo = (
                                abs(
                                    centro_importe
                                    - centro_cargo
                                )
                            )


                            distancia_abono = (
                                abs(
                                    centro_importe
                                    - centro_abono
                                )
                            )


                            # -------------------------------------
                            # Solo aceptar importes cercanos
                            # a las columnas detectadas
                            # -------------------------------------

                            TOLERANCIA = 18


                            es_cargo = (
                                distancia_cargo
                                <= TOLERANCIA
                            )


                            es_abono = (
                                distancia_abono
                                <= TOLERANCIA
                            )


                            if not es_cargo and not es_abono:
                                continue


                            # -------------------------------------
                            # Si por alguna razón cae cerca
                            # de ambas, elegir la más cercana
                            # -------------------------------------

                            if (
                                es_cargo
                                and
                                es_abono
                            ):

                                if (
                                    distancia_cargo
                                    < distancia_abono
                                ):

                                    es_abono = False

                                else:

                                    es_cargo = False


                            # -------------------------------------
                            # Evitar duplicados
                            # -------------------------------------

                            key = (
                                t,
                                round(top, 1),
                                round(x0, 1)
                            )


                            if key in montos_usados:
                                continue


                            # -------------------------------------
                            # Posición vertical del número
                            # -------------------------------------

                            y = (
                                page.height
                                - top
                                - 6
                            )


                            # =====================================
                            # CARGO
                            # =====================================

                            if es_cargo:

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


                            # =====================================
                            # ABONO
                            # =====================================

                            if es_abono:

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


                # =================================================
                # UNIR PDF
                # =================================================

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


                # =================================================
                # RESULTADO
                # =================================================

                total_cargos = (
                    contador_cargos - 1
                )

                total_abonos = (
                    contador_abonos - 1
                )


                st.success(
                    f"✅ Listo: {pdf_final}"
                )


                st.write(
                    f"**Cargos:** {total_cargos}"
                )

                st.write(
                    f"**Abonos:** {total_abonos}"
                )


                # ---------------------------------------------
                # Validación contra el estado de cuenta
                # ---------------------------------------------

                if (
                    total_cargos == 5
                    and
                    total_abonos == 5
                ):

                    st.success(
                        "✅ La cantidad de movimientos "
                        "coincide con el resumen del estado "
                        "de cuenta."
                    )

                else:

                    st.warning(
                        "⚠️ La cantidad enumerada no coincide "
                        "con el resumen esperado. Revisa "
                        "el formato de este PDF."
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
                key=f"descargar_historial_{i}"
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
```
