import streamlit as st
import requests
import io
import re
import time
from pypdf import PdfWriter, PdfReader
from pypdf.generic import RectangleObject

st.set_page_config(page_title="GodEx Converter V3", page_icon="📦")
st.title("📦 GodEx: Centro de Logística")
st.markdown("Conversor ZPL Inteligente. Detecta copias, centra contenido y gestiona múltiples medidas.")

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("📏 Configuración de Medidas")
    modo = st.radio(
        "¿Qué vas a imprimir?",
        ["Envíos (100x150mm)", "Productos (2x1 pulg)", "Personalizado"],
        index=0
    )
    if "Envíos" in modo:
        ancho = 4.0
        alto = 6.0
        st.info("✅ Configurado para Mercado Envíos / Andreani (4x6 pulgadas).")
    elif "Productos" in modo:
        ancho = 2.0
        alto = 1.0
        st.info("✅ Configurado para etiquetas internas GodEx.")
    else:
        ancho = st.number_input("Ancho (pulgadas)", value=4.0)
        alto = st.number_input("Alto (pulgadas)", value=6.0)
        st.warning("Modo manual activado.")
    centrar = st.checkbox("Centrar contenido automáticamente", value=True)
    dpmm = "8dpmm"  # 8 dots/mm = 203 dpi
# --- FIN BARRA LATERAL ---


def calcular_bbox_zpl(zpl: str):
    """Devuelve (max_x, max_y) en dots del contenido ZPL."""
    xs, ys = [0], [0]
    # ^FO y ^FT: posiciones absolutas
    for m in re.finditer(r'\^F[OT](\d+),(\d+)', zpl):
        xs.append(int(m.group(1)))
        ys.append(int(m.group(2)))
    max_x_base = max(xs)
    max_y_base = max(ys)
    # Ancho extra por ^FB (field block ancho)
    fb_widths = [int(m.group(1)) for m in re.finditer(r'\^FB(\d+)', zpl)]
    extra_w = max(fb_widths) if fb_widths else 120
    # Alto extra por la última línea (barcode / texto)
    extra_h = 70
    return max_x_base + extra_w, max_y_base + extra_h


def centrar_zpl(zpl: str, ancho_pulg: float, alto_pulg: float) -> str:
    """Inyecta ^LH con el offset necesario para centrar el contenido."""
    dots_por_pulg = 203  # 8dpmm
    target_w = int(ancho_pulg * dots_por_pulg)
    target_h = int(alto_pulg * dots_por_pulg)
    bw, bh = calcular_bbox_zpl(zpl)
    off_x = max(0, (target_w - bw) // 2)
    off_y = max(0, (target_h - bh) // 2)
    nuevo_lh = f'^LH{off_x},{off_y}'
    if re.search(r'\^LH\d+,\d+', zpl):
        zpl = re.sub(r'\^LH\d+,\d+', nuevo_lh, zpl)
    else:
        zpl = zpl.replace('^XA', '^XA\n' + nuevo_lh, 1)
    return zpl


uploaded_file = st.file_uploader("Arrastrá tu archivo .txt con ZPL aquí", type=["txt"])

if uploaded_file is not None:
    raw_data = uploaded_file.getvalue().decode("utf-8", errors='ignore')
    raw_labels = raw_data.split('^XZ')
    labels = [l.strip() + '^XZ' for l in raw_labels if "^XA" in l]
    total_designs = len(labels)

    if total_designs == 0:
        st.error("No se encontró código ZPL válido.")
    else:
        total_etiquetas_finales = 0
        for l in labels:
            m = re.search(r'\^PQ(\d+)', l)
            total_etiquetas_finales += int(m.group(1)) if m else 1

        st.success(f"📂 Archivo cargado. Modo: {modo}")
        st.write(f"Diseños detectados: **{total_designs}** | Etiquetas totales a generar: **{total_etiquetas_finales}**")

        if st.button(f'🚀 Generar PDF ({total_etiquetas_finales} etiquetas)'):
            progress_bar = st.progress(0)
            status_text = st.empty()
            final_pdf_writer = PdfWriter()
            url = f"http://api.labelary.com/v1/printers/{dpmm}/labels/{ancho}x{alto}/0/"
            errores = 0

            for i, zpl_code in enumerate(labels):
                status_text.text(f"Procesando diseño {i+1} de {total_designs}...")

                # 1. Detectar copias
                match_qty = re.search(r'\^PQ(\d+)', zpl_code)
                cantidad_copias = int(match_qty.group(1)) if match_qty else 1

                # 2. Forzar 1 copia para la API
                zpl_para_api = re.sub(r'\^PQ\d+(,\d+){0,3}', '^PQ1', zpl_code)
                if "^PQ" not in zpl_para_api:
                    zpl_para_api = zpl_para_api.replace("^XZ", "^PQ1^XZ")

                # 3. Centrar contenido según el tamaño objetivo
                if centrar:
                    zpl_para_api = centrar_zpl(zpl_para_api, ancho, alto)

                # 4. Llamada a Labelary con retry
                pdf_content = None
                for intento in range(3):
                    try:
                        r = requests.post(url, data=zpl_para_api, headers={'Accept': 'application/pdf'})
                        if r.status_code == 200:
                            pdf_content = r.content
                            break
                        elif r.status_code == 429:
                            time.sleep(2)
                    except:
                        time.sleep(1)

                if pdf_content:
                    reader = PdfReader(io.BytesIO(pdf_content))
                    pagina_maestra = reader.pages[0]

                    # 5. Recortar la página al tamaño real de la etiqueta
                    # (Labelary a veces devuelve A4/Letter con la etiqueta arriba-izquierda)
                    w_pt = ancho * 72
                    h_pt = alto * 72
                    page_h = float(pagina_maestra.mediabox.height)
                    lly = max(0, page_h - h_pt)
                    rect = RectangleObject((0, lly, w_pt, page_h))
                    pagina_maestra.mediabox = rect
                    pagina_maestra.cropbox = rect
                    pagina_maestra.trimbox = rect
                    pagina_maestra.artbox = rect
                    pagina_maestra.bleedbox = rect

                    for _ in range(cantidad_copias):
                        final_pdf_writer.add_page(pagina_maestra)
                else:
                    st.error(f"Error procesando diseño {i+1}")
                    errores += 1

                progress_bar.progress((i + 1) / total_designs)
                time.sleep(0.2)

            status_text.text("Compilando PDF final...")
            output_pdf = io.BytesIO()
            final_pdf_writer.write(output_pdf)
            output_pdf.seek(0)

            st.balloons()
            st.success(f"¡Proceso completado! Errores: {errores}")

            nombre_archivo = "etiquetas_envios.pdf" if "Envíos" in modo else "etiquetas_productos.pdf"
            st.download_button(
                label="⬇️ Descargar PDF Listo",
                data=output_pdf,
                file_name=nombre_archivo,
                mime="application/pdf"
            )
