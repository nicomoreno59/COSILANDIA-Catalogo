"""COSILANDIA — generador de catálogo (autoajuste con recuadro seguro)."""
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import streamlit as st
from PIL import Image
from rembg import new_session

from procesador import (abrir_foto, recortar_objeto, componer, guardar_png,
                        adaptar_formato, mostrar_area)

CARPETA = Path(__file__).resolve().parent
FONDO = CARPETA / 'fondo_cosilandia.png'
st.set_page_config(page_title='COSILANDIA | Catálogo', page_icon='🎀', layout='wide')
st.title('🎀 COSILANDIA — Generador de catálogo')
st.caption('Productos al máximo tamaño permitido, sin tapar el logo ni salir del recuadro.')

if not FONDO.is_file():
    st.error('Falta fondo_cosilandia.png junto a app.py.')
    st.stop()

@st.cache_resource(show_spinner='Preparando la inteligencia artificial para recortar imágenes…')
def modelo():
    return new_session('isnet-general-use')

@st.cache_data(show_spinner=False)
def quitar_fondo(datos):
    imagen = abrir_foto(datos)
    alfa = imagen.getchannel('A')
    proporcion = sum(alfa.histogram()[:250]) / max(1, imagen.width * imagen.height)
    sesion = modelo() if proporcion <= 0.015 else None
    return guardar_png(recortar_objeto(imagen, sesion))

with Image.open(FONDO) as archivo:
    fondo = archivo.convert('RGBA').copy()

FORMATOS = ['Original · sin cambios', 'Instagram · 1080 × 1350', 'Estado WhatsApp · 1080 × 1920']
with st.sidebar:
    st.header('Configuración del catálogo')
    st.success('✅ Tamaño máximo automático y protegido')
    tamano = st.slider('Tamaño respecto al máximo (%)', min_value=40, max_value=100,
                       value=100, step=5,
                       help='100 % ocupa todo lo posible dentro del recuadro, sin deformarse.')
    mover_x = st.slider('Mover izquierda ↔ derecha', -100, 100, 0, 5,
                        help='El movimiento nunca supera el límite permitido.')
    mover_y = st.slider('Mover arriba ↕ abajo', -100, 100, 0, 5,
                        help='El movimiento nunca supera el límite permitido.')
    margen = st.slider('Separación respecto al recuadro (%)', 0, 8, 2, 1)
    sombra = st.checkbox('Sombra suave', value=True)
    formato = st.selectbox('Formato de descarga', FORMATOS, index=0)
    guia = st.checkbox('Mostrar recuadro de ajuste en la vista previa', value=False)
    st.caption('El recuadro de referencia es INVISIBLE en el archivo descargado. '
               'El logo y el tejido del fondo no se redibujan.')

ajustes = (tamano, mover_x, mover_y, margen, sombra, formato)

def crear_imagen(datos):
    transparente = Image.open(BytesIO(quitar_fondo(datos))).convert('RGBA')
    composicion = componer(fondo, transparente, tamano, mover_x, mover_y, sombra, margen)
    exportable = adaptar_formato(composicion, formato)
    return transparente, composicion, exportable

tab_una, tab_lote = st.tabs(['📸 Una fotografía', '📦 Varias fotografías'])
with tab_una:
    archivo = st.file_uploader('Subir foto del producto',
                                type=['png', 'jpg', 'jpeg', 'webp'], key='unica')
    if archivo is None:
        st.info('Sube una fotografía para recortarla y ubicarla automáticamente.')
        muestra = mostrar_area(fondo, margen) if guia else fondo
        st.image(muestra, caption='Área disponible para el producto' if guia else 'Fondo original',
                 width=340)
    else:
        try:
            with st.spinner('Recortando y acomodando el producto…'):
                recorte, composicion, exportable = crear_imagen(archivo.getvalue())
            izquierda, derecha = st.columns([1, 1])
            with izquierda:
                st.image(recorte, caption='Producto recortado', use_container_width=True)
            with derecha:
                vista = componer(mostrar_area(fondo, margen), recorte, tamano,
                                 mover_x, mover_y, sombra, margen) if guia else composicion
                if formato != FORMATOS[0]:
                    vista = adaptar_formato(vista, formato)
                st.image(vista, caption='Vista previa del catálogo', use_container_width=True)
                st.download_button('⬇️ Descargar fotografía (PNG)',
                                   data=guardar_png(exportable),
                                   file_name=f'{Path(archivo.name).stem}_COSILANDIA.png',
                                   mime='image/png', use_container_width=True, type='primary')
        except Exception as error:
            st.error(f'No se pudo crear la fotografía: {error}')
            st.info('Intenta otra foto con buena iluminación y un fondo de color diferente al producto.')

with tab_lote:
    archivos = st.file_uploader('Subir varias fotografías',
                                 type=['png', 'jpg', 'jpeg', 'webp'],
                                 accept_multiple_files=True, key='lote')
    st.caption('Cada producto se agranda independientemente hasta su máximo tamaño permitido.')
    if st.button('✨ Procesar lote', type='primary', disabled=not archivos):
        paquete = BytesIO()
        errores = []
        progreso = st.progress(0)
        completadas = 0
        with ZipFile(paquete, 'w', compression=ZIP_DEFLATED) as zipfile:
            for i, foto in enumerate(archivos, 1):
                try:
                    _, _, listo = crear_imagen(foto.getvalue())
                    zipfile.writestr(f'{i:03d}_{Path(foto.name).stem}_COSILANDIA.png',
                                     guardar_png(listo))
                    completadas += 1
                except Exception as error:
                    errores.append(f'{foto.name}: {error}')
                progreso.progress(i / len(archivos))
        if completadas:
            st.session_state['catalogo_zip'] = (ajustes, paquete.getvalue())
            st.success(f'¡Hecho! {completadas} imágenes creadas.')
        else:
            st.session_state.pop('catalogo_zip', None)
            st.error('No fue posible procesar ninguna imagen.')
        if errores:
            st.warning('Archivos con problemas: ' + '; '.join(errores))
    almacenado = st.session_state.get('catalogo_zip')
    if almacenado:
        if almacenado[0] == ajustes:
            st.download_button('⬇️ Descargar todas las fotos (ZIP)', data=almacenado[1],
                               file_name='COSILANDIA_catalogo.zip',
                               mime='application/zip', use_container_width=True)
        else:
            st.info('Cambiaste los ajustes. Pulsa Procesar lote para regenerar el ZIP.')

st.divider()
st.caption(f'Fondo original: {fondo.width} × {fondo.height} px · '
           'El producto no sale del recuadro y el logo permanece visible.')
