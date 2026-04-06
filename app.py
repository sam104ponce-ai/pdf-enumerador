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

st.markdown("<h1 style='text-align:center;'>FlowLedger</h1>", unsafe_allow_html=True)
st.markdown("<h3 style='text-align:center;color:gray;'>Automatización de Movimientos Bancarios</h3>", unsafe_allow_html=True)

# =========================================================
# CONFIGURACIÓN (COLUMNAS Y PATRÓN)
# =========================================================
X_CARGO_MIN, X_CARGO_MAX = 290, 380
X_ABONO_MIN, X_ABONO_MAX = 390, 480
patron_monto = re.compile(r'^\d{1,3}(?:,\d{3})*\.\d{2}$')

# =========================================================
# OPCIONES DE SUBIDA
# =========================================================
tipo_pdf = st.radio(
    "Selecciona el tipo de Banco:",
    ("BBVA TDC", "BBVA TDD")
)

archivo = st.file_uploader(f"Sube tu PDF ({tipo_pdf})", type=["pdf"])

# =========================================================
# HISTORIAL DE PDF
# =========================================================
if "historial_pdfs" not in st.session_state:
    st.session_state.historial_pdfs = []

def agregar_a_historial(nombre, bytes_pdf, tipo_banco):
    st.session_state.historial_pdfs.append({
        "nombre": nombre,
        "pdf_bytes": bytes_pdf,
        "banco": tipo_banco
    })

# =========================================================
# PROCESAR PDF
# =========================================================
if archivo:
    if st.button("Procesar PDF"):

        with st.spinner("Procesando…"):
            file_bytes = archivo.read()

            # =========================================================
            # BBVA TDC
            # =========================================================
            if tipo_pdf == "BBVA TDC":

                X_CARGO_MIN, X_CARGO_MAX = None, None
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
                                        posibles.append(float(ww["x0"]))
                            if posibles:
                                X_CARGO_MIN = min(posibles) - 10
                                X_CARGO_MAX = max(posibles) + 10
                                break

                # ❌ Se quita la línea de mostrar columna detectada
                # st.write(f"📍 Columna detectada: {X_CARGO_MIN:.2f} - {X_CARGO_MAX:.2f}")

                # Procesar PDF TDC
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

                            linea_texto = ""
                            for ww in words:
                                if abs(float(ww["top"]) - float(w["top"])) < 3:
                                    linea_texto += ww["text"] + " "
                            linea_mayus = linea_texto.upper()

                            if any(p in linea_mayus for p in ["TOTAL IMPORTES", "TOTAL", "IMPORTE TOTAL"]):
                                continue

                            if not patron_monto.match(texto):
                                continue

                            x0 = float(w["x0"])
                            x1 = float(w["x1"])
                            top = float(w["top"])
                            y = page.height - top - 2

                            if not (X_CARGO_MIN <= x0 <= X_CARGO_MAX):
                                continue

                            key = (texto, round(x0,1), round(top,1))
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

                st.success(f"✅ Total enumerados: {contador - 1}")
                st.download_button(
                    label="📥 Descargar PDF Enumerado",
                    data=output_pdf,
                    file_name="PDF_ENUMERADO.pdf",
                    mime="application/pdf"
                )

                # Guardar en historial
                agregar_a_historial("PDF_ENUMERADO.pdf", output_pdf.getvalue(), tipo_pdf)

            # =========================================================
            # BBVA TDD
            # =========================================================
            else:

                nombre, ext = os.path.splitext(archivo.name)
                pdf_final = f"{nombre}_ENUMERADO{ext}"

                packet = BytesIO()
                can = canvas.Canvas(packet)

                contador_cargos = 1
                contador_abonos = 1

                with pdfplumber.open(BytesIO(file_bytes)) as pdf:
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
                            y = page.height - top - 6

                            if top < 120:
                                continue

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

                            ignorar = False
                            if len(linea_montos) >= 3:
                                for i, m in enumerate(linea_montos):
                                    if m["text"] == t and abs(m["x0"] - x0) < 1:
                                        if i == 1:
                                            ignorar = True
                            if ignorar:
                                continue

                            linea_texto = ""
                            for ww in words:
                                if abs(float(ww["top"]) - top) < 3:
                                    linea_texto += ww["text"] + " "
                            linea_mayus = linea_texto.upper()

                            if "MOVIMIENTOS DE PERIODOS ANTERIORES" in linea_mayus:
                                continue
                            if "P14 TOTAL PLAY" not in linea_mayus:
                                if any(p in linea_mayus for p in [
                                    "SALDO", "OPERACION", "OPERACIÓN",
                                    "LIQUIDACION", "LIQUIDACIÓN", "TOTAL"
                                ]):
                                    continue

                            key = (t, round(top, 1), round(x0, 1))
                            if key in montos_usados:
                                continue

                            contiene_codigo = (
                                any(
                                    re.search(c[0] + r'\s*' + c[1:], linea_mayus)
                                    for c in ["P14","V44","V47","V43","T93","V41",
                                              "K65","V40","T92","K64","V46","I74","C48"]
                                ) or "P14 TOTAL PLAY" in linea_mayus
                            )

                            es_primer_monto = any(abs(m["x0"]-x0)<2 for m in linea_montos[:1])

                            # Cargos
                            if (X_CARGO_MIN <= x0 <= X_CARGO_MAX) or (contiene_codigo and es_primer_monto) or ("P14 TOTAL PLAY" in linea_mayus):
                                can.setFillColorRGB(1,0,0)
                                can.setFont("Helvetica-Bold",8)
                                can.drawRightString(x1+16,y,str(contador_cargos))
                                contador_cargos += 1
                                montos_usados.add(key)
                                continue

                            # Abonos
                            if X_ABONO_MIN <= x0 <= X_ABONO_MAX:
                                can.setFillColorRGB(1,0,0)
                                can.setFont("Helvetica-Bold",8)
                                can.drawRightString(x1+16,y,str(contador_abonos))
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

                st.success(f"✅ Listo: {pdf_final}")
                st.write(f"Cargos: {contador_cargos - 1}")
                st.write(f"Abonos: {contador_abonos - 1}")

                st.download_button(
                    "⬇️ Descargar PDF",
                    output,
                    file_name=pdf_final,
                    mime="application/pdf"
                )

                # Guardar en historial
                agregar_a_historial(pdf_final, output.getvalue(), tipo_pdf)

# =========================================================
# MOSTRAR HISTORIAL
# =========================================================
if st.session_state.historial_pdfs:
    st.markdown("### 🗂 Historial de PDFs procesados")
    for i, item in enumerate(st.session_state.historial_pdfs):
        col1, col2, col3 = st.columns([4,1,1])
        with col1:
            st.write(f"{item['nombre']} ({item['banco']})")
        with col2:
            st.download_button(
                label="⬇️",
                data=item["pdf_bytes"],
                file_name=item["nombre"],
                mime="application/pdf"
            )
        with col3:
            if st.button("🗑️", key=f"eliminar_{i}"):
                st.session_state.historial_pdfs.pop(i)
                st.experimental_rerun()
