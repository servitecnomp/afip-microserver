import qrcode
import base64
import json
import requests
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.graphics.shapes import Drawing, Rect, String, Line
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

# Mapeo de compañías (fallback)
COMPANIAS = {
    "30500031132": {
        "razon_social": "MERCANTIL ANDINA SEGUROS S.A.",
        "domicilio": "Av. San Juan 550, CABA",
        "condicion_iva": "IVA Responsable Inscripto"
    },
    "20226717871": {
        "razon_social": "LA SEGUNDA COOPERATIVA LIMITADA",
        "domicilio": "Juan Manuel De Rosas 957 - Rosario Norte, Santa Fe",
        "condicion_iva": "IVA Responsable Inscripto"
    }
}

# Datos de los emisores
EMISOR_DATA = {
    "27239676931": {
        "razon_social": "DEVRIES MARIA PAULA",
        "domicilio": "Rodriguez Peña 1789 - Mar Del Plata Sur, Buenos Aires",
        "ingresos_brutos": "27239676931",
        "inicio_actividades": "01/01/2021",
        "condicion_iva": "Responsable Monotributo"
    },
    "27461124149": {
        "razon_social": "CACCIATO MARIA MERCEDES",
        "domicilio": "General Paz 4662 - Mar Del Plata Sur, Buenos Aires",
        "ingresos_brutos": "27461124149",
        "inicio_actividades": "01/12/2023",
        "condicion_iva": "Responsable Monotributo"
    }
}

# URLs del logo de ARCA para intentar descargar
ARCA_LOGO_URLS = [
    "https://www.afip.gob.ar/images/logo-arca.png",
    "https://www.afip.gob.ar/images/logoARCA.png",
    "https://www.afip.gob.ar/images/arca.png",
]

_arca_logo_cache = None

def get_arca_logo():
    """Intenta obtener el logo de ARCA desde internet, con cache"""
    global _arca_logo_cache
    if _arca_logo_cache is not None:
        return _arca_logo_cache
    for url in ARCA_LOGO_URLS:
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                buf = BytesIO(resp.content)
                _arca_logo_cache = buf
                print(f"✓ Logo ARCA descargado desde {url}")
                return buf
        except Exception:
            continue
    print("⚠ No se pudo descargar logo ARCA, se omitirá")
    _arca_logo_cache = False
    return None

def formatear_vencimiento_cae(vencimiento_str):
    """Convierte AAAAMMDD a DD/MM/AAAA"""
    if len(vencimiento_str) == 8:
        anio = vencimiento_str[0:4]
        mes = vencimiento_str[4:6]
        dia = vencimiento_str[6:8]
        return f"{dia}/{mes}/{anio}"
    return vencimiento_str

def formatear_importe(valor):
    """Formatea número con coma de miles y punto decimal: 22,100.00"""
    return f"{float(valor):,.2f}"

def generar_qr_afip(datos_factura):
    """Genera código QR según especificaciones AFIP RG 5198/2022"""
    cuit_emisor = str(datos_factura["cuit_emisor"]).replace("-", "")
    cuit_receptor = str(datos_factura["cuit_receptor"]).replace("-", "")
    
    qr_data = {
        "ver": 1,
        "fecha": datos_factura["fecha_emision"].strftime("%Y-%m-%d"),
        "cuit": int(cuit_emisor),
        "ptoVta": int(datos_factura["punto_venta"]),
        "tipoCmp": int(datos_factura["tipo_cbte"]),
        "nroCmp": int(datos_factura["cbte_nro"]),
        "importe": float(datos_factura["importe"]),
        "moneda": "PES",
        "ctz": 1,
        "tipoDocRec": 80,
        "nroDocRec": int(cuit_receptor),
        "tipoCodAut": "E",
        "codAut": int(datos_factura["cae"])
    }
    
    qr_json = json.dumps(qr_data, separators=(',', ':'))
    qr_base64 = base64.b64encode(qr_json.encode()).decode()
    qr_url = f"https://www.afip.gob.ar/fe/qr/?p={qr_base64}"
    
    qr = qrcode.QRCode(version=1, box_size=10, border=1)
    qr.add_data(qr_url)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return buffer

def construir_pagina(datos_factura, logo_path, tipo_copia):
    """
    Construye los elementos (story) de una copia de la factura.
    tipo_copia: 'ORIGINAL', 'DUPLICADO', 'TRIPLICADO'
    """
    cuit_emisor = str(datos_factura["cuit_emisor"]).replace("-", "").replace(" ", "")
    cuit_receptor = str(datos_factura["cuit_receptor"]).replace("-", "").replace(" ", "")
    fecha_emision = datos_factura["fecha_emision"]
    vencimiento_cae = formatear_vencimiento_cae(str(datos_factura["vencimiento_cae"]))

    tipo_cbte = int(datos_factura.get("tipo_cbte", 11))
    es_nota_credito = (tipo_cbte == 13)

    emisor = EMISOR_DATA.get(cuit_emisor, EMISOR_DATA["27239676931"])

    if datos_factura.get("compania"):
        receptor = {
            "razon_social": datos_factura.get("compania", "Cliente"),
            "domicilio": datos_factura.get("domicilio", ""),
            "condicion_iva": datos_factura.get("condicion_iva", "IVA Responsable Inscripto")
        }
    else:
        receptor = COMPANIAS.get(cuit_receptor, {
            "razon_social": "Cliente",
            "domicilio": "",
            "condicion_iva": "IVA Responsable Inscripto"
        })

    # Generar QR (buffer nuevo cada vez)
    qr_buffer = generar_qr_afip(datos_factura)

    style_normal = ParagraphStyle('Normal', fontSize=8, leading=10)
    style_small  = ParagraphStyle('Small',  fontSize=7, leading=9)
    style_small_15 = ParagraphStyle('Small15', fontSize=7, leading=10.5)

    story = []

    # ===== ENCABEZADO ORIGINAL/DUPLICADO/TRIPLICADO =====
    encabezado = Table([[tipo_copia]], colWidths=[180*mm])
    encabezado.setStyle(TableStyle([
        ('ALIGN',        (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME',     (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE',     (0, 0), (-1, -1), 11),
        ('BOX',          (0, 0), (-1, -1), 1, colors.black),
        ('TOPPADDING',   (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 3),
    ]))
    story.append(encabezado)
    story.append(Spacer(1, 2*mm))

    # ===== LOGO EMISOR =====
    try:
        logo = RLImage(logo_path, width=20*mm, height=20*mm)
    except:
        logo = Paragraph("<b>LOGO</b>", style_normal)

    codigo_cbte = "013" if es_nota_credito else "011"
    titulo_cbte = "NOTA DE CRÉDITO" if es_nota_credito else "FACTURA"

    emisor_content = Paragraph(
        f"<b>{emisor['razon_social']}</b><br/><br/>"
        f"<b>Razón Social:</b> {emisor['razon_social']}<br/>"
        f"<b>Domicilio Comercial:</b> {emisor['domicilio']}<br/>"
        f"<b>Condición frente al IVA:</b> {emisor['condicion_iva']}",
        style_small_15
    )

    tabla_emisor = Table([[logo], [emisor_content]], colWidths=[86*mm])
    tabla_emisor.setStyle(TableStyle([
        ('ALIGN',        (0, 0), (0, 0), 'LEFT'),
        ('VALIGN',       (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING',   (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 3),
    ]))

    # Columna central con C y divisor
    d = Drawing(8*mm, 48*mm)
    d.add(Line(4*mm, 0, 4*mm, 48*mm, strokeColor=colors.black, strokeWidth=1.2))
    cuadrado_size = 18*mm
    cuadrado_y = 28*mm
    d.add(Rect(-5*mm, cuadrado_y, cuadrado_size, cuadrado_size,
               fillColor=colors.white, strokeColor=colors.black, strokeWidth=2.5))
    letra_y = cuadrado_y + 9*mm
    d.add(String(4*mm, letra_y, 'C',
                 fontSize=26, fontName='Helvetica-Bold', textAnchor='middle', fillColor=colors.black))
    d.add(String(4*mm, cuadrado_y + 2*mm, f'COD. {codigo_cbte}',
                 fontSize=7, fontName='Helvetica', textAnchor='middle', fillColor=colors.black))

    factura_content = Paragraph(
        f"<b><font size=16>{titulo_cbte}</font></b><br/><br/><br/>"
        f"<b>Punto de Venta:</b> {str(datos_factura['punto_venta']).zfill(5)} "
        f"<b>Comp. Nro:</b> {str(datos_factura['cbte_nro']).zfill(8)}<br/>"
        f"<b>Fecha de Emisión:</b> {fecha_emision.strftime('%d/%m/%Y')}<br/>"
        f"<b>CUIT:</b> {cuit_emisor}<br/>"
        f"<b>Ingresos Brutos:</b> {emisor['ingresos_brutos']}<br/>"
        f"<b>Fecha de Inicio de Actividades:</b> {emisor['inicio_actividades']}",
        style_small_15
    )

    bloque_principal = Table([[tabla_emisor, d, factura_content]], colWidths=[86*mm, 8*mm, 86*mm])
    bloque_principal.setStyle(TableStyle([
        ('BOX',          (0, 0), (-1, -1), 1.5, colors.black),
        ('ALIGN',        (0, 0), (0, 0), 'LEFT'),
        ('ALIGN',        (1, 0), (1, 0), 'CENTER'),
        ('ALIGN',        (2, 0), (2, 0), 'LEFT'),
        ('VALIGN',       (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING',   (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 5),
        ('LEFTPADDING',  (0, 0), (0, 0), 5),
        ('RIGHTPADDING', (0, 0), (0, 0), 5),
        ('LEFTPADDING',  (1, 0), (1, 0), 0),
        ('RIGHTPADDING', (1, 0), (1, 0), 0),
        ('LEFTPADDING',  (2, 0), (2, 0), 18),
        ('RIGHTPADDING', (2, 0), (2, 0), 5),
        ('TOPPADDING',   (2, 0), (2, 0), 2),
    ]))

    story.append(bloque_principal)
    story.append(Spacer(1, 2*mm))

    # ===== PERÍODO FACTURADO =====
    periodo_table = Table([[
        Paragraph(
            f"<b>Período Facturado Desde:</b> {fecha_emision.strftime('%d/%m/%Y')}  "
            f"<b>Hasta:</b> {fecha_emision.strftime('%d/%m/%Y')}  "
            f"<b>Fecha de Vto. para el pago:</b> {fecha_emision.strftime('%d/%m/%Y')}",
            style_small)
    ]], colWidths=[180*mm])
    periodo_table.setStyle(TableStyle([
        ('BOX',          (0, 0), (-1, -1), 1, colors.black),
        ('TOPPADDING',   (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 3),
    ]))
    story.append(periodo_table)
    story.append(Spacer(1, 2*mm))

    # ===== DATOS DEL RECEPTOR =====
    receptor_content = (
        f"<b>CUIT:</b> {cuit_receptor}<br/>"
        f"<b>Apellido y Nombre / Razón Social:</b> {receptor['razon_social']}<br/>"
        f"<b>Condición frente al IVA:</b> {receptor['condicion_iva']}<br/>"
        f"<b>Domicilio:</b> {receptor['domicilio']}<br/>"
    )

    if es_nota_credito:
        cbte_asoc_nro = datos_factura.get("cbte_asoc_nro", "")
        cbte_asoc_pto_vta = datos_factura.get("cbte_asoc_pto_vta", datos_factura.get("punto_venta", 2))
        if cbte_asoc_nro:
            receptor_content += f"<b>Fac. C:</b> {str(cbte_asoc_pto_vta).zfill(5)}-{str(cbte_asoc_nro).zfill(8)}<br/>"

    receptor_content += "<b>Condición de venta:</b> Otra"

    receptor_table = Table([[Paragraph(receptor_content, style_small)]], colWidths=[180*mm])
    receptor_table.setStyle(TableStyle([
        ('BOX',          (0, 0), (-1, -1), 1, colors.black),
        ('TOPPADDING',   (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 3),
    ]))
    story.append(receptor_table)
    story.append(Spacer(1, 3*mm))

    # ===== TABLA DE PRODUCTOS =====
    importe = float(datos_factura["importe"])
    descripcion = datos_factura.get("descripcion", "Servicio")
    importe_fmt = formatear_importe(importe)

    productos_data = [
        [Paragraph("<b>Código</b>", style_small),
         Paragraph("<b>Producto / Servicio</b>", style_small),
         Paragraph("<b>Cantidad</b>", style_small),
         Paragraph("<b>U. Medida</b>", style_small),
         Paragraph("<b>Precio Unit.</b>", style_small),
         Paragraph("<b>% Bonif</b>", style_small),
         Paragraph("<b>Imp. Bonif.</b>", style_small),
         Paragraph("<b>Subtotal</b>", style_small)],
        ["", Paragraph(descripcion, style_small), "1,00", "unidades",
         importe_fmt, "0,00", "0,00", importe_fmt]
    ]

    productos_table = Table(productos_data,
                            colWidths=[15*mm, 70*mm, 18*mm, 18*mm, 18*mm, 13*mm, 13*mm, 18*mm])
    productos_table.setStyle(TableStyle([
        ('GRID',         (0, 0), (-1, -1), 0.5, colors.black),
        ('BACKGROUND',   (0, 0), (-1,  0), colors.lightgrey),
        ('ALIGN',        (0, 0), (0, -1), 'CENTER'),
        ('ALIGN',        (1, 0), (1,  0), 'CENTER'),
        ('ALIGN',        (1, 1), (1, -1), 'LEFT'),
        ('ALIGN',        (2, 0), (-1,-1), 'CENTER'),
        ('VALIGN',       (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTSIZE',     (0, 0), (-1, -1), 8),
        ('TOPPADDING',   (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 4),
        ('LEFTPADDING',  (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(productos_table)
    story.append(Spacer(1, 3*mm))

    # ===== TOTALES =====
    totales_table = Table([
        ["", Paragraph("<b>Subtotal: $</b>", style_normal),              importe_fmt],
        ["", Paragraph("<b>Importe Otros Tributos: $</b>", style_normal), "0,00"],
        ["", Paragraph("<b>Importe Total: $</b>", style_normal),          importe_fmt],
    ], colWidths=[100*mm, 60*mm, 20*mm])
    totales_table.setStyle(TableStyle([
        ('ALIGN',        (1, 0), (1, -1), 'RIGHT'),
        ('ALIGN',        (2, 0), (2, -1), 'RIGHT'),
        ('BOX',          (0, 0), (-1, -1), 1, colors.black),
        ('LINEABOVE',    (1, 0), (-1,  0), 1, colors.black),
        ('FONTSIZE',     (0, 0), (-1, -1), 9),
        ('TOPPADDING',   (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 3),
    ]))
    story.append(totales_table)
    story.append(Spacer(1, 5*mm))

    # ===== FOOTER: [QR] | [ARCA] | [Pág + CAE + Comprobante Autorizado] =====
    qr_img = RLImage(qr_buffer, width=30*mm, height=30*mm)

    # Columna central: ARCA + Comprobante Autorizado + texto legal
    arca_logo = get_arca_logo()
    style_centro = ParagraphStyle('centro', fontSize=7, leading=10, alignment=TA_LEFT)
    style_centro6 = ParagraphStyle('centro6', fontSize=6, leading=8, alignment=TA_LEFT)

    if arca_logo:
        arca_logo.seek(0)
        arca_img = RLImage(arca_logo, width=28*mm, height=14*mm)
        col_arca = Table([
            [arca_img],
            [Spacer(1, 2*mm)],
            [Paragraph("<b><i>Comprobante Autorizado</i></b>", style_centro)],
            [Spacer(1, 1*mm)],
            [Paragraph("Esta Agencia no se responsabiliza por los datos", style_centro6)],
            [Paragraph("ingresados en el detalle de la operación", style_centro6)],
        ], colWidths=[75*mm])
    else:
        col_arca = Table([
            [Paragraph("<b><font size=9>ARCA</font></b><br/>"
                      "<font size=6>Agencia de Recaudación<br/>y Control Aduanero</font>",
                      style_centro)],
            [Spacer(1, 2*mm)],
            [Paragraph("<b><i>Comprobante Autorizado</i></b>", style_centro)],
            [Spacer(1, 1*mm)],
            [Paragraph("Esta Agencia no se responsabiliza por los datos", style_centro6)],
            [Paragraph("ingresados en el detalle de la operación", style_centro6)],
        ], colWidths=[75*mm])

    col_arca.setStyle(TableStyle([
        ('ALIGN',        (0, 0), (-1, -1), 'LEFT'),
        ('TOPPADDING',   (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 0),
        ('LEFTPADDING',  (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))

    # Columna derecha: Pág 1/1, CAE, Vto
    style_der = ParagraphStyle('der', fontSize=7, leading=10, alignment=TA_RIGHT)

    cae_content = Table([
        [Paragraph("Pág. 1/1", style_der)],
        [Spacer(1, 2*mm)],
        [Paragraph(f"<b>CAE N°:</b> {datos_factura['cae']}", style_der)],
        [Paragraph(f"<b>Fecha de Vto. de CAE:</b> {vencimiento_cae}", style_der)],
    ], colWidths=[65*mm])
    cae_content.setStyle(TableStyle([
        ('ALIGN',        (0, 0), (-1, -1), 'RIGHT'),
        ('TOPPADDING',   (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('LEFTPADDING',  (0, 0), (-1, -1), 0),
    ]))

    footer_table = Table(
        [[qr_img, col_arca, cae_content]],
        colWidths=[35*mm, 75*mm, 70*mm]
    )
    footer_table.setStyle(TableStyle([
        ('VALIGN',       (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN',        (0, 0), (0,  0),  'LEFT'),
        ('ALIGN',        (1, 0), (1,  0),  'LEFT'),
        ('ALIGN',        (2, 0), (2,  0),  'RIGHT'),
        ('RIGHTPADDING', (2, 0), (2,  0),  0),
    ]))
    story.append(footer_table)

    return story


def crear_pdf_factura(datos_factura, logo_path, output_path):
    """
    Crea un PDF con 3 copias (Original, Duplicado, Triplicado) 
    en páginas separadas, con formato AFIP.
    """
    from reportlab.platypus import PageBreak

    output_path = str(output_path)

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=15*mm,
        leftMargin=15*mm,
        topMargin=10*mm,
        bottomMargin=10*mm
    )

    full_story = []

    for i, copia in enumerate(["ORIGINAL", "DUPLICADO", "TRIPLICADO"]):
        pagina = construir_pagina(datos_factura, logo_path, copia)
        full_story.extend(pagina)
        if i < 2:
            full_story.append(PageBreak())

        buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=15*mm,
        leftMargin=15*mm,
        topMargin=10*mm,
        bottomMargin=10*mm
    )
    doc.build(full_story)
    buffer.seek(0)
    pdf_base64 = base64.b64encode(buffer.read()).decode('utf-8')
    print(f"PDF generado exitosamente (3 copias) en memoria")
    return pdf_base64
