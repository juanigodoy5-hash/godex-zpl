import streamlit as st
import requests
import io
import re
from pypdf import PdfWriter
import time

st.set_page_config(page_title="GodEx ZPL Converter", page_icon="🖨️")

st.title("🖨️ GodEx: Conversor Blindado")
st.markdown("Modo Hormiga: Procesa 1 a 1 para evitar caídas del servidor.")

# Opciones laterales
with st.sidebar:
    st.header("Configuración")
    ancho = st.number_input("Ancho (pulgadas)", value=2.0)
    alto = st.number_input("Alto (pulgadas)", value=1.0)
    # Checkbox clave para evitar error 413 por exceso de copias
    forzar_una = st.checkbox("Forzar 1 copia (Ignorar ^PQ)", value=True, help="Si tu ZPL pide 50 copias, esto lo baja a 1 para que el PDF no explote.")

uploaded_file = st.file_uploader("Arrastrá tu archivo .txt aquí", type=["txt"])

if uploaded_file is not None:
    raw_data = uploaded_file.getvalue().decode("utf-8", errors='ignore')
    
    # Limpieza: Separar por ^XZ (fin de etiqueta)
    # A veces los archivos traen basura antes del ^XA, limpiamos eso.
    raw_labels = raw_data.split('^XZ')
    labels = []
    for l in raw_labels:
        clean_l = l.strip()
        if "^XA" in clean_l: # Solo procesamos si tiene inicio de etiqueta
            # Aseguramos que termine con ^XZ
            labels.append(clean_l + '^XZ')
            
    total_labels = len(labels)
    st.info(f"Detectadas {total_labels} etiquetas individuales.")

    if st.button(f'Generar PDF ({total_labels} etiq.)'):
        progress_bar = st.progress(0)
        status_text = st.empty()
        pdf_writer = PdfWriter()
        errores = 0
        
        # URL base
        url = f"http://api.labelary.com/v1/printers/8dpmm/labels/{ancho}x{alto}/0/"
        
        for i, zpl_code in enumerate(labels):
            status_text.text(f"Procesando etiqueta {i+1} de {total_labels}...")
            
            # TRUCO: Modificar el ZPL al vuelo si está activado el "Forzar 1 copia"
            if forzar_una:
                # Reemplazamos cualquier ^PQ... por ^PQ1
                zpl_code = re.sub(r'\^PQ\d+', '^PQ1', zpl_code)
            
            try:
                # Enviamos como data raw en lugar de files para ser más ligeros
                headers = {'Accept': 'application/pdf'}
                response = requests.post(url, data=zpl_code, headers=headers)

                if response.status_code == 200:
                    batch_pdf = io.BytesIO(response.content)
                    pdf_writer.append(batch_pdf)
                else:
                    st.warning(f"Etiqueta {i+1} falló (Error {response.status_code}). Se omitió.")
                    errores += 1
            
            except Exception as e:
                st.error(f"Error de conexión en etiqueta {i+1}: {e}")
                errores += 1
            
            # Actualizar barra
            progress_bar.progress((i + 1) / total_labels)
            # Pequeña pausa para no saturar la API gratuita
            time.sleep(0.1)

        # Resultado final
        status_text.text("Finalizado.")
        
        if errores < total_labels:
            output_pdf = io.BytesIO()
            pdf_writer.write(output_pdf)
            output_pdf.seek(0)
            
            msg = "¡Listo!"
            if errores > 0:
                msg += f" (Ojo: {errores} etiquetas fallaron y no están en el PDF)"
            
            st.success(msg)
            st.download_button(
                label="⬇️ Descargar PDF Final",
                data=output_pdf,
                file_name="etiquetas_godex_blindado.pdf",
                mime="application/pdf"
            )
        else:
            st.error("Todas las etiquetas fallaron. Revisá que el formato ZPL sea correcto (debe tener ^XA y ^XZ).")
