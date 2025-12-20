import streamlit as st
import requests

# Configuración de la página (Minimalista)
st.set_page_config(page_title="GodEx ZPL Converter", page_icon="🖨️")

st.title("🖨️ GodEx: Conversor ZPL a PDF")
st.markdown("Subí tu TXT con código ZPL. Descargá tu PDF. **Sin vueltas.**")

# Configuración de la etiqueta (2x1 pulgadas)
# 8dpmm es estándar para 203dpi (común en Zebra/Honeywell)
ancho_pulgadas = 2
alto_pulgadas = 1
densidad = "8dpmm" 

uploaded_file = st.file_uploader("Arrastrá tu archivo .txt aquí", type=["txt"])

if uploaded_file is not None:
    # Leer el archivo
    zpl_data = uploaded_file.getvalue().decode("utf-8")
    
    st.text_area("Vista previa del código ZPL:", value=zpl_data, height=150)

    if st.button('Generar PDF'):
        with st.spinner('Procesando etiqueta...'):
            try:
                # Usamos la API pública de Labelary (Motor de renderizado)
                # Ajustamos la URL para el tamaño 2x1 pulgadas
                url = f"http://api.labelary.com/v1/printers/{densidad}/labels/{ancho_pulgadas}x{alto_pulgadas}/0/"
                
                # Enviamos el ZPL
                files = {'file': zpl_data}
                headers = {'Accept': 'application/pdf'}
                
                response = requests.post(url, files=files, headers=headers, stream=True)

                if response.status_code == 200:
                    st.success("¡Etiqueta generada con éxito!")
                    
                    # Botón de descarga
                    st.download_button(
                        label="⬇️ Descargar PDF para Imprimir",
                        data=response.content,
                        file_name="etiqueta_godex.pdf",
                        mime="application/pdf"
                    )
                else:
                    st.error(f"Error en el motor de renderizado: {response.status_code}")
                    st.write(response.text)
            
            except Exception as e:
                st.error(f"Ocurrió un error de conexión: {e}")

st.divider()
st.caption("Sistema interno GodEx - Uso exclusivo operaciones.")