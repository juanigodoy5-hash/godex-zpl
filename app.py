import streamlit as st
import requests
import io
from pypdf import PdfWriter

# Configuración de la página
st.set_page_config(page_title="GodEx ZPL Converter", page_icon="🖨️")

st.title("🖨️ GodEx: Conversor Masivo")
st.markdown("Subí tu archivo. El sistema procesará por lotes para evitar errores.")

# Configuración 2x1 pulgadas
ancho = 2
alto = 1
dpmm = "8dpmm"

uploaded_file = st.file_uploader("Arrastrá tu archivo .txt aquí", type=["txt"])

if uploaded_file is not None:
    raw_data = uploaded_file.getvalue().decode("utf-8")
    st.text(f"Archivo cargado. Tamaño: {len(raw_data)} caracteres.")

    if st.button('Generar PDF Masivo'):
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # 1. Limpieza y división de etiquetas (Split por ^XZ)
        # Separamos el texto gigante en etiquetas individuales
        raw_labels = raw_data.split('^XZ')
        labels = [l.strip() + '^XZ' for l in raw_labels if l.strip()]
        
        total_labels = len(labels)
        
        if total_labels == 0:
            st.error("No se detectaron etiquetas ZPL válidas (deben terminar con ^XZ).")
        else:
            status_text.text(f"Detectadas {total_labels} etiquetas. Procesando...")
            
            # 2. Procesamiento por lotes (Batching)
            # Labelary acepta máx 50. Usamos 20 para estar seguros.
            BATCH_SIZE = 20
            pdf_writer = PdfWriter()
            error_flag = False

            for i in range(0, total_labels, BATCH_SIZE):
                batch = labels[i:i + BATCH_SIZE]
                zpl_batch = '\n'.join(batch)
                
                # Actualizar barra de progreso
                progress = min((i + BATCH_SIZE) / total_labels, 1.0)
                progress_bar.progress(progress)
                
                try:
                    url = f"http://api.labelary.com/v1/printers/{dpmm}/labels/{ancho}x{alto}/0/"
                    files = {'file': zpl_batch}
                    headers = {'Accept': 'application/pdf'}
                    
                    response = requests.post(url, files=files, headers=headers)
                    
                    if response.status_code == 200:
                        # Convertir bytes a PDF y añadir al final
                        batch_pdf = io.BytesIO(response.content)
                        pdf_writer.append(batch_pdf)
                    else:
                        st.error(f"Error en el lote {i}: Código {response.status_code}")
                        error_flag = True
                        break
                        
                except Exception as e:
                    st.error(f"Error de conexión: {e}")
                    error_flag = True
                    break

            # 3. Descarga final
            if not error_flag:
                status_text.text("¡Procesamiento terminado! Uniendo PDF...")
                output_pdf = io.BytesIO()
                pdf_writer.write(output_pdf)
                output_pdf.seek(0)
                
                st.success(f"¡Listo! {total_labels} etiquetas procesadas.")
                st.download_button(
                    label="⬇️ Descargar PDF Listo para Imprimir",
                    data=output_pdf,
                    file_name="etiquetas_godex_full.pdf",
                    mime="application/pdf"
                )
