import streamlit as st
import requests
import io
import re
import time
from pypdf import PdfWriter, PdfReader

st.set_page_config(page_title="GodEx ZPL Converter", page_icon="🖨️")

st.title("🖨️ GodEx: Fotocopiadora Inteligente")
st.markdown("Detecta cantidades (^PQ), descarga 1 matriz y multiplica en el PDF.")

# Configuración 2x1
ancho = 2
alto = 1
dpmm = "8dpmm"

uploaded_file = st.file_uploader("Arrastrá tu archivo .txt aquí", type=["txt"])

if uploaded_file is not None:
    raw_data = uploaded_file.getvalue().decode("utf-8", errors='ignore')
    
    # Separamos por etiquetas (^XZ) y limpiamos vacíos
    raw_labels = raw_data.split('^XZ')
    labels = [l.strip() + '^XZ' for l in raw_labels if "^XA" in l]
    
    total_designs = len(labels)
    
    if total_designs == 0:
        st.error("No se encontró código ZPL válido.")
    else:
        # Calcular total teórico para informar al usuario
        total_etiquetas_finales = 0
        for l in labels:
            m = re.search(r'\^PQ(\d+)', l)
            total_etiquetas_finales += int(m.group(1)) if m else 1
            
        st.info(f"Detectados {total_designs} diseños únicos. Se generarán un total de {total_etiquetas_finales} etiquetas.")

        if st.button(f'Generar PDF Masivo ({total_etiquetas_finales} etiq.)'):
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            final_pdf_writer = PdfWriter()
            url = f"http://api.labelary.com/v1/printers/{dpmm}/labels/{ancho}x{alto}/0/"
            
            errores = 0

            for i, zpl_code in enumerate(labels):
                status_text.text(f"Procesando diseño {i+1} de {total_designs}...")
                
                # --- INTELIGENCIA GODEX ---
                # 1. Detectar cuántas copias pide el ZPL original
                match_qty = re.search(r'\^PQ(\d+)', zpl_code)
                cantidad_copias = int(match_qty.group(1)) if match_qty else 1
                
                # 2. "Trucar" el ZPL para pedirle SOLO UNA a la API (Velocidad pura)
                # Reemplaza ^PQ59 por ^PQ1
                zpl_para_api = re.sub(r'\^PQ\d+', '^PQ1', zpl_code)
                if "^PQ" not in zpl_para_api: 
                     zpl_para_api = zpl_para_api.replace("^XZ", "^PQ1^XZ")

                # 3. Llamada a la API (Intentos automáticos por si falla)
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
                    # 4. FOTOCOPIADORA
                    # Leemos la etiqueta maestra
                    reader = PdfReader(io.BytesIO(pdf_content))
                    pagina_maestra = reader.pages[0]
                    
                    # La clonamos "cantidad_copias" veces
                    for _ in range(cantidad_copias):
                        final_pdf_writer.add_page(pagina_maestra)
                else:
                    st.error(f"Error procesando diseño {i+1}")
                    errores += 1
                
                progress_bar.progress((i + 1) / total_designs)
                time.sleep(0.2) # Respeto a la API

            # Finalización
            status_text.text("Compilando PDF final...")
            output_pdf = io.BytesIO()
            final_pdf_writer.write(output_pdf)
            output_pdf.seek(0)
            
            st.success("¡Listo! PDF Generado.")
            st.download_button(
                label=f"⬇️ Descargar PDF ({total_etiquetas_finales} etiquetas)",
                data=output_pdf,
                file_name="etiquetas_godex_full.pdf",
                mime="application/pdf"
            )
