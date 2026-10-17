from io import BytesIO
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

import streamlit as st
from PIL import Image
from rembg import new_session

from procesador import abrir_foto, recortar_objeto, componer, guardar_png

RUTA = Path(__file__).resolve().parent
ARCHIVO_FONDO = RUTA / 'fondo_cosilandia.png'

st.set_page_config(page_title='COSILANDIA | Generador de catálogo', page_icon='🎀', layout='wide')

st.markdown('''
<style>
.block-container {padding-top: 1.7rem; max-width: 1150px;}
h1, h2, h3 {color: #A52572;}
</style>
''', unsafe_allow_html=True)

st.title('🎀 COSILANDIA')
st.write('Generador de fotografías para el catálogo. El fondo y el logo originales se mantienen intactos.')

if not ARCHIVO_FONDO.is_file():
    st.error('No se encontró fondo_cosilandia.png en la misma carpeta que app.py.')
    st.stop()

@st.cache_resource(show_spinner='Cargando el recortador de fondo (la primera vez puede demorar)...')
def modelo():
    return new_session('isnet-general-use')

@st.cache_data(show_spinner=False)
def separar_fondo(datos):
    original = abrir_foto(datos)
    # Solo se carga IA si la foto aún no tiene fondo transparente.
    alfa = original.getchannel('A')
    hist = alfa.histogram()
    porcentaje = sum(hist[:250]) / max(1, original.width * original.height)
    sesion = modelo() if porcentaje <= 0.015 else None
    recorte = recortar_objeto(original, sesion)
    return guardar_png(recorte)

with Image.open(ARCHIVO_FONDO) as archivo:
    fondo = archivo.convert('RGBA').copy()

with st.sidebar:
    st.header('Ajustes de la fotografía')
    tamano = st.slider('Tamaño del producto (%)', 40, 160, 100, step=5)
    mover_x = st.slider('Mover a derecha (+) / izquierda (-)', -30, 30, 0)
    mover_y = st.slider('Mover abajo (+) / arriba (-)', -20, 20, 0)
    sombra = st.checkbox('Sombra suave sobre la plataforma', value=True)
    st.caption('Estos ajustes se aplican tanto a fotos individuales como a los lotes. ' 
               'La plataforma y el logo no se modifican.')

tab_uno, tab_lote = st.tabs(['📷 Una fotografía', '📦 Varias fotografías'])

with tab_uno:
    foto = st.file_uploader('Sube la foto de un producto', type=['png', 'jpg', 'jpeg', 'webp'], key='foto_unica')
    if foto is None:
        st.info('Carga una fotografía para comenzar. Preferiblemente con fondo sencillo y buena iluminación.')
        st.image(fondo, caption='Fondo original COSILANDIA, sin editar', width=310)
    else:
        try:
            with st.spinner('Quitando fondo y creando catálogo...'):
                recorte = Image.open(BytesIO(separar_fondo(foto.getvalue()))).convert('RGBA')
                terminado = componer(fondo, recorte, tamano, mover_x, mover_y, sombra)
            primera, segunda = st.columns(2)
            with primera:
                st.image(abrir_foto(foto.getvalue()), caption='Fotografía original', use_container_width=True)
                st.image(recorte, caption='Producto recortado', use_container_width=True)
            with segunda:
                st.image(terminado, caption='Vista previa sobre la plataforma', use_container_width=True)
                st.download_button('⬇️ Descargar PNG', data=guardar_png(terminado),
                                   file_name=f'{Path(foto.name).stem}_COSILANDIA.png',
                                   mime='image/png', type='primary', use_container_width=True)
        except Exception as e:
            st.error(f'No se pudo procesar la imagen: {e}')
            st.caption('Prueba otra foto, preferiblemente con un fondo de un solo color.')

with tab_lote:
    fotos = st.file_uploader('Selecciona varias fotografías',
                             type=['png', 'jpg', 'jpeg', 'webp'],
                             accept_multiple_files=True, key='fotos_lote')
    st.caption('Se aplicarán automáticamente a todas el tamaño, posición y sombra elegidos en la barra lateral.')
    if st.button('✨ Crear catálogo en lote', type='primary', disabled=not fotos):
        buffer_zip = BytesIO()
        procesadas = 0
        fallidas = []
        progreso = st.progress(0)
        with ZipFile(buffer_zip, 'w', ZIP_DEFLATED) as zipf:
            for i, foto_lote in enumerate(fotos, start=1):
                try:
                    con_fondo_quitado = Image.open(BytesIO(separar_fondo(foto_lote.getvalue()))).convert('RGBA')
                    foto_final = componer(fondo, con_fondo_quitado, tamano, mover_x, mover_y, sombra)
                    nombre = Path(foto_lote.name).stem
                    zipf.writestr(f'{i:03d}_{nombre}_COSILANDIA.png', guardar_png(foto_final))
                    procesadas += 1
                except Exception as e:
                    fallidas.append(f'{foto_lote.name}: {e}')
                progreso.progress(i / len(fotos))
        if procesadas:
            st.session_state['ultimo_zip'] = buffer_zip.getvalue()
            st.success(f'¡Listo! {procesadas} fotografías de catálogo generadas.')
        else:
            st.session_state.pop('ultimo_zip', None)
            st.error('No se pudo procesar ninguna fotografía.')
        if fallidas:
            st.warning('Fotos con problemas:\n\n' + '\n\n'.join(fallidas))

    if 'ultimo_zip' in st.session_state:
        st.download_button('⬇️ Descargar catálogo completo (ZIP)',
                           data=st.session_state['ultimo_zip'],
                           file_name='COSILANDIA_catalogo.zip',
                           mime='application/zip', use_container_width=True)

st.divider()
st.caption(f'Tamaño original del diseño: {fondo.width} × {fondo.height} px · ' 
           'Las imágenes generadas conservan este tamaño y el mismo fondo.')
