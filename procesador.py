"""COSILANDIA: recorte y ajuste automático dentro del recuadro seguro."""
from io import BytesIO
from PIL import Image, ImageDraw, ImageFilter, ImageOps

# Recuadro rosa marcado en la imagen de referencia, normalizado.
# Los límites NO se dibujan en las imágenes finales.
# Referencia original: 1145 x 1374 px (esquina superior izquierda como origen).
ZONA_RELATIVA = (57 / 1145, 39 / 1374, 1078 / 1145, 1014 / 1374)


def abrir_foto(datos):
    with Image.open(BytesIO(datos)) as foto:
        return ImageOps.exif_transpose(foto).convert('RGBA')


def recortar_objeto(imagen, sesion=None):
    """Extrae objeto y recorta espacio transparente adicional."""
    imagen = imagen.convert('RGBA')
    alfa = imagen.getchannel('A')
    proporcion_transparente = sum(alfa.histogram()[:250]) / max(1, imagen.width * imagen.height)
    if proporcion_transparente <= 0.015:
        if sesion is None:
            raise ValueError('No se cargó el recortador de fondo.')
        from rembg import remove
        imagen = remove(imagen.convert('RGB'), session=sesion).convert('RGBA')
    mascara = imagen.getchannel('A').point(lambda a: 255 if a > 12 else 0)
    limites = mascara.getbbox()
    if limites is None:
        raise ValueError('No se reconoció ningún producto. Usa una foto con más contraste.')
    return imagen.crop(limites)


def area_segura(fondo, margen=2):
    """Rectángulo interior útil, con margen opcional porcentual del recuadro."""
    ancho, alto = fondo.size
    x0, y0, x1, y1 = ZONA_RELATIVA
    izquierda = round(ancho * x0)
    arriba = round(alto * y0)
    derecha = round(ancho * x1)
    abajo = round(alto * y1)
    borde_x = round((derecha - izquierda) * margen / 100)
    borde_y = round((abajo - arriba) * margen / 100)
    area = (izquierda + borde_x, arriba + borde_y, derecha - borde_x, abajo - borde_y)
    if area[2] <= area[0] or area[3] <= area[1]:
        raise ValueError('El margen configurado es demasiado grande.')
    return area


def preparar_producto(producto):
    producto = producto.convert('RGBA')
    mascara = producto.getchannel('A').point(lambda a: 255 if a > 12 else 0)
    limites = mascara.getbbox()
    if limites is None:
        raise ValueError('El archivo no contiene un producto visible.')
    return producto.crop(limites)


def calcular_ubicacion(fondo, producto, tamano=100, mover_x=0, mover_y=0, margen=2):
    """Maximiza el tamaño sin exceder área; movimientos nunca la sobrepasan."""
    producto = preparar_producto(producto)
    x0, y0, x1, y1 = area_segura(fondo, margen)
    permitido_w = x1 - x0
    permitido_h = y1 - y0
    # Respeta relación de aspecto original incluso si es muy alto o muy ancho.
    escala = min(permitido_w / producto.width, permitido_h / producto.height)
    escala *= max(0.05, min(100, tamano)) / 100
    w = min(permitido_w, max(1, round(producto.width * escala)))
    h = min(permitido_h, max(1, round(producto.height * escala)))
    # Movimiento de -100 a +100 consume SOLO el espacio que queda libre.
    frac_x = (max(-100, min(100, mover_x)) + 100) / 200
    frac_y = (max(-100, min(100, mover_y)) + 100) / 200
    x = x0 + round((permitido_w - w) * frac_x)
    y = y0 + round((permitido_h - h) * frac_y)
    return (x, y, w, h), (x0, y0, x1, y1)


def componer(fondo, producto, tamano=100, mover_x=0, mover_y=0,
             sombra=True, margen=2):
    """Conserva el fondo original y agrega solo el producto dentro del área segura."""
    base = fondo.convert('RGBA').copy()
    recorte = preparar_producto(producto)
    (x, y, w, h), (x0, y0, x1, y1) = calcular_ubicacion(
        base, recorte, tamano, mover_x, mover_y, margen)
    recorte = recorte.resize((w, h), Image.Resampling.LANCZOS)
    if sombra:
        # Sombra suave y sutil, siempre recortada dentro del área permitida.
        alpha = recorte.getchannel('A')
        radio = max(5, round(min(w, h) * 0.025))
        sombra_alpha = alpha.filter(ImageFilter.GaussianBlur(radio))
        sombra_alpha = sombra_alpha.point(lambda a: int(a * 0.20))
        capa = Image.new('RGBA', (w, h), (85, 56, 71, 0))
        capa.putalpha(sombra_alpha)
        sx, sy = (max(2, round(w * 0.01)), max(3, round(h * 0.012)))
        zona = Image.new('RGBA', (x1 - x0, y1 - y0), (0, 0, 0, 0))
        zona.alpha_composite(capa, (x - x0 + sx, y - y0 + sy))
        base.alpha_composite(zona, (x0, y0))
    base.alpha_composite(recorte, (x, y))
    return base.convert('RGB')


def mostrar_area(fondo, margen=2):
    """Guía visual únicamente para la vista previa; no se añade a la exportación."""
    vista = fondo.convert('RGB').copy()
    x0, y0, x1, y1 = area_segura(fondo, margen)
    dib = ImageDraw.Draw(vista)
    dib.rectangle((x0, y0, x1 - 1, y1 - 1), outline=(226, 70, 139), width=5)
    return vista


def adaptar_formato(imagen, formato):
    """Crea formatos para redes sin estirar ni recortar el producto/logo."""
    imagen = imagen.convert('RGB')
    if formato == 'Instagram · 1080 × 1350':
        # Se recorta ligeramente el borde lateral sin tocar el área segura.
        return ImageOps.fit(imagen, (1080, 1350), method=Image.Resampling.LANCZOS)
    if formato == 'Estado WhatsApp · 1080 × 1920':
        # Fondo de extensión difuminado; en el centro, diseño original íntegro.
        fondo = ImageOps.fit(imagen, (1080, 1920), method=Image.Resampling.LANCZOS)
        fondo = fondo.filter(ImageFilter.GaussianBlur(48))
        # Atenuar el fondo extendido para mantener una estética ligera.
        velo = Image.new('RGB', fondo.size, (246, 238, 231))
        fondo = Image.blend(fondo, velo, 0.55)
        centro = imagen.copy()
        h = round(centro.height * 1080 / centro.width)
        centro = centro.resize((1080, h), Image.Resampling.LANCZOS)
        pos_y = round((1920 - h) * 0.68)
        fondo.paste(centro, (0, pos_y))
        return fondo
    return imagen


def guardar_png(imagen):
    archivo = BytesIO()
    imagen.save(archivo, format='PNG', optimize=True)
    return archivo.getvalue()
