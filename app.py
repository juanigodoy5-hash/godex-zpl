import streamlit as st
import requests
import io
import re
import time
from pypdf import PdfWriter, PdfReader

st.set_page_config(page_title="GodEx Converter V3", page_icon="📦")

st.title("📦 GodEx: Centro de Logística")
st.markdown("Conversor ZPL Inteligente. Detecta copias y gestiona múltiples medidas.")

# --- BARRA LATERAL (CONFIGURACIÓN) ---
with st.sidebar:
    st.header("📏 Configuración de Medidas")
    
    # Selector Rápido (Lo nuevo)
    modo = st.radio(
        "¿Qué vas a imprimir?",
        ["Envíos (100x150mm)", "Productos (2x1 pulg)", "Personalizado"],
        index=0
    )
    
    # Lógica de medidas según la selección
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

    dpmm = "8dpmm" # Estándar para Zebra/Honeywell (203 dpi)

# --- FIN BARRA LATERAL ---

uploaded_file = st.file_uploader("Arrastrá tu archivo .txt con ZPL aquí", type=["txt"])

if uploaded_file is not None:
    raw_data = uploaded_file.getvalue().decode("utf-8", errors='ignore')
    
    # Separamos por etiquetas (^XZ) y limpiamos
    raw_labels = raw_data.split('^XZ')
    labels = [l.strip() + '^XZ' for l in raw_labels if "^XA" in l]
    
    total_designs = len(labels)
    
    if total_designs == 0:
        st.error("No se encontró código ZPL válido.")
    else:
        # Cálculo previo de cantidad total
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
            # La API usa pulgadas siempre, por eso pasamos las variables ancho/alto
            url = f"http://api.labelary.com/v1/printers/{dpmm}/labels/{ancho}x{alto}/0/"
            
            errores = 0

            for i, zpl_code in enumerate(labels):
                status_text.text(f"Procesando diseño {i+1} de {total_designs}...")
                
                # 1. Detectar copias (^PQ)
                match_qty = re.search(r'\^PQ(\d+)', zpl_code)
                cantidad_copias = int(match_qty.group(1)) if match_qty else 1
                
                # 2. Forzar 1 copia para la API (ahorro de recursos)
                zpl_para_api = re.sub(r'\^PQ\d+', '^PQ1', zpl_code)
                if "^PQ" not in zpl_para_api: 
                     zpl_para_api = zpl_para_api.replace("^XZ", "^PQ1^XZ")

                # 3. Llamada a API con Retry
                pdf_content = None
                for intento in range(3):
                    try:
                        r = requests.post(url, data=zpl_para_api, headers={'Accept': 'application/pdf'})
                        if r.status_code == 200:
                            pdf_content = r.content
                            break
                        elif r.status_code == 429: # Too many requests
                            time.sleep(2)
                    except:
                        time.sleep(1)
                
                if pdf_content:
                    # 4. Multiplicación interna (Fotocopiadora)
                    reader = PdfReader(io.BytesIO(pdf_content))
                    pagina_maestra = reader.pages[0]
                    
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
            st.success("¡Proceso completado!")
            
            nombre_archivo = "etiquetas_envios.pdf" if "Envíos" in modo else "etiquetas_productos.pdf"
            
            st.download_button(
                label=f"⬇️ Descargar PDF Listo",
                data=output_pdf,
                file_name=nombre_archivo,
                mime="application/pdf"
            )
