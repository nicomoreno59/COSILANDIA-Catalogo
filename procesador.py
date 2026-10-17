"""Recorte, posicionamiento y composición sobre el fondo ORIGINAL de COSILANDIA."""
from io import BytesIO
from PIL import Image, ImageOps, ImageDraw, ImageFilter


def abrir_foto(datos):
    with Image.open(BytesIO(datos)) as im:
        return ImageOps.exif_transpose(im).convert('RGBA')


def recortar_objeto(imagen, sesion):
    """Conserva PNG con transparencia; para otros usa rembg."""
    imagen = imagen.convert('RGBA')
    alfa = imagen.getchannel('A')
    hist = alfa.histogram()
    porcentaje_transparente = sum(hist[:250]) / max(1, imagen.width * imagen.height)
    if porcentaje_transparente <= 0.015:
        from rembg import remove
        imagen = remove(imagen.convert('RGB'), session=sesion).convert('RGBA')

    # Recorta al borde útil, ignorando unos pocos píxeles muy transparentes.
    mascara = imagen.getchannel('A').point(lambda v: 255 if v > 12 else 0)
    limites = mascara.getbbox()
    if limites is None:
        raise ValueError('No se detectó ningún producto. Prueba una foto más clara.')
    return imagen.crop(limites)


def componer(fondo, producto, tamano=100, mover_x=0, mover_y=0, sombra=True):
    """Añade SOLO el producto y su sombra; no modifica el archivo de fondo."""
    base = fondo.convert('RGBA').copy()
    objeto = producto.convert('RGBA')
    ancho, alto = base.size

    # Plataforma del fondo compartido: aprox. centro x=50%, superficie y=75.5%.
    ajuste = min(0.57 * ancho / objeto.width, 0.36 * alto / objeto.height)
    ajuste *= tamano / 100
    w_obj = max(1, round(objeto.width * ajuste))
    h_obj = max(1, round(objeto.height * ajuste))
    objeto = objeto.resize((w_obj, h_obj), Image.Resampling.LANCZOS)

    centro_x = round(ancho * (0.5 + mover_x / 100))
    superficie_y = round(alto * (0.755 + mover_y / 100))
    izquierda = round(centro_x - w_obj / 2)
    superior = superficie_y - h_obj

    if sombra:
        capa_sombra = Image.new('RGBA', base.size, (0, 0, 0, 0))
        dibujar = ImageDraw.Draw(capa_sombra)
        ancho_sombra = max(18, round(w_obj * 0.65))
        alto_sombra = max(9, round(alto * 0.015))
        dibujar.ellipse((centro_x - ancho_sombra // 2,
                         superficie_y - alto_sombra // 2,
                         centro_x + ancho_sombra // 2,
                         superficie_y + alto_sombra // 2),
                        fill=(112, 68, 91, 80))
        capa_sombra = capa_sombra.filter(ImageFilter.GaussianBlur(max(7, round(ancho * 0.012))))
        base = Image.alpha_composite(base, capa_sombra)

    capa_producto = Image.new('RGBA', base.size, (0, 0, 0, 0))
    capa_producto.alpha_composite(objeto, (izquierda, superior))
    return Image.alpha_composite(base, capa_producto).convert('RGB')


def guardar_png(imagen):
    buffer = BytesIO()
    imagen.save(buffer, format='PNG', optimize=True)
    return buffer.getvalue()
