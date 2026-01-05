import qrcode
import base64
import json
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

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

def formatear_vencimiento_cae(vencimiento_str):
    """Convierte AAAAMMDD a DD/MM/AAAA"""
    if len(vencimiento_str) == 8:
        anio = vencimiento_str[0:4]
        mes = vencimiento_str[4:6]
        dia = vencimiento_str[6:8]
        return f"{dia}/{mes}/{anio}"
    return vencimiento_str

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

def crear_pdf_factura(datos_factura, logo_path, output_path):
    """Crea un PDF de factura con el encabezado exacto de AFIP"""
    
    # --- Configuración de datos inicial ---
    cuit_emisor = str(datos_factura["cuit_emisor"]).replace("-", "").replace(" ", "")
    cuit_receptor = str(datos_factura["cuit_receptor"]).replace("-", "").replace(" ", "")
    fecha_emision = datos_factura["fecha_emision"]
    vencimiento_cae = formatear_vencimiento_cae(str(datos_factura["vencimiento_cae"]))
    tipo_cbte = int(datos_factura.get("tipo_cbte", 11))
    es_nota_credito = (tipo_cbte == 13)
    letra_cbte = "C"
    codigo_cbte = "013" if es_nota_credito else "011"
    emisor = EMISOR_DATA.get(cuit_emisor, EMISOR_DATA["27239676931"])
    
    # Receptor logic
    if datos_factura.get("compania"):
        receptor = {
            "razon_social": datos_factura.get("compania"),
            "domicilio": datos_factura.get("domicilio", ""),
            "condicion_iva": datos_factura.get("condicion_iva", "IVA Responsable Inscripto")
        }
    else:
        receptor = COMPANIAS.get(cuit_receptor, {"razon_social": "Cliente", "domicilio": "", "condicion_iva": "IVA Responsable Inscripto"})

    qr_buffer = generar_qr_afip(datos_factura)

    # --- Documento ---
    doc = SimpleDocTemplate(output_path, pagesize=A4, rightMargin=15*mm, leftMargin=15*mm, topMargin=10*mm, bottomMargin=10*mm)
    styles = getSampleStyleSheet()
    
    # Estilos personalizados
    style_label = ParagraphStyle('Label', fontSize=8, fontName='Helvetica-Bold')
    style_value = ParagraphStyle('Value', fontSize=8, fontName='Helvetica')
    style_header_title = ParagraphStyle('HeaderTitle', fontSize=16, fontName='Helvetica-Bold', alignment=TA_CENTER)
    style_emisor_title = ParagraphStyle('EmisorTitle', fontSize=12, fontName='Helvetica-Bold', alignment=TA_CENTER)

    story = []

    # 1. ORIGINAL / DUPLICADO
    encabezado = Table([["ORIGINAL"]], colWidths=[180*mm])
    encabezado.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
    ]))
    story.append(encabezado)

    # 2. CUADRADO CENTRAL (LA LETRA C)
    celda_letra = Table([
        [Paragraph(f"<b>{letra_cbte}</b>", ParagraphStyle('C', fontSize=26, alignment=TA_CENTER))],
        [Paragraph(f"COD. {codigo_cbte}", ParagraphStyle('Cod', fontSize=7, alignment=TA_CENTER))]
    ], colWidths=[16*mm], rowHeights=[12*mm, 6*mm])

    celda_letra.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))

    # 3. CONTENIDO IZQUIERDO (LOGO Y EMISOR)
    try:
        logo = RLImage(logo_path, width=25*mm, height=25*mm)
    except:
        logo = Paragraph("<b>LOGO</b>", styles['Normal'])

    col_izq_content = [
        logo,
        Spacer(1, 2*mm),
        Paragraph(emisor['razon_social'], style_emisor_title),
        Spacer(1, 4*mm),
        Paragraph(f"<b>Razón Social:</b> {emisor['razon_social']}", style_value),
        Paragraph(f"<b>Domicilio Comercial:</b> {emisor['domicilio']}", style_value),
        Paragraph(f"<b>Condición frente al IVA:</b> {emisor['condicion_iva']}", style_value),
    ]

    # 4. CONTENIDO DERECHO (FACTURA)
    titulo_cbte = "NOTA DE CRÉDITO" if es_nota_credito else "FACTURA"
    col_der_content = [
        Paragraph(titulo_cbte, style_header_title),
        Spacer(1, 4*mm),
        Paragraph(f"<b>Punto de Venta:</b> {str(datos_factura['punto_venta']).zfill(5)} &nbsp;&nbsp; <b>Comp. Nro:</b> {str(datos_factura['cbte_nro']).zfill(8)}", style_value),
        Paragraph(f"<b>Fecha de Emisión:</b> {fecha_emision.strftime('%d/%m/%Y')}", style_value),
        Spacer(1, 4*mm),
        Paragraph(f"<b>CUIT:</b> {cuit_emisor}", style_value),
        Paragraph(f"<b>Ingresos Brutos:</b> {emisor['ingresos_brutos']}", style_value),
        Paragraph(f"<b>Fecha de Inicio de Actividades:</b> {emisor['inicio_actividades']}", style_value),
    ]

    # 5. BLOQUE PRINCIPAL (ESTRUCTURA 3 COLUMNAS AFIP)
    # Anchos: 82mm + 16mm + 82mm = 180mm
    bloque_principal = Table(
        [[col_izq_content, celda_letra, col_der_content]],
        colWidths=[82*mm, 16*mm, 82*mm]
    )

    bloque_principal.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        # Las líneas verticales que dividen el documento nacen del cuadrado
        ('LINEBEFORE', (1, 0), (1, 0), 1, colors.black),
        ('LINEAFTER', (1, 0), (1, 0), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
        ('TOPPADDING', (1, 0), (1, 0), -0.1), # Pega la C al borde superior
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))

    story.append(bloque_principal)
    story.append(Spacer(1, 2*mm))

    # --- Resto del documento (Período, Receptor, etc.) ---
    # Período
    periodo_table = Table([[Paragraph(f"<b>Período Facturado Desde:</b> {fecha_emision.strftime('%d/%m/%Y')} &nbsp; <b>Hasta:</b> {fecha_emision.strftime('%d/%m/%Y')} &nbsp; <b>Fecha de Vto. para el pago:</b> {fecha_emision.strftime('%d/%m/%Y')}", style_value)]], colWidths=[180*mm])
    periodo_table.setStyle(TableStyle([('BOX', (0, 0), (-1, -1), 1, colors.black), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')]))
    story.append(periodo_table)
    story.append(Spacer(1, 2*mm))

    # Receptor
    receptor_content = f"<b>CUIT:</b> {cuit_receptor} &nbsp;&nbsp; <b>Apellido y Nombre / Razón Social:</b> {receptor['razon_social']}<br/>" \
                       f"<b>Condición frente al IVA:</b> {receptor['condicion_iva']}<br/>" \
                       f"<b>Domicilio:</b> {receptor['domicilio']}<br/>" \
                       f"<b>Condición de venta:</b> Otra"
    receptor_table = Table([[Paragraph(receptor_content, style_value)]], colWidths=[180*mm])
    receptor_table.setStyle(TableStyle([('BOX', (0, 0), (-1, -1), 1, colors.black), ('LEFTPADDING', (0, 0), (-1, -1), 5), ('TOPPADDING', (0, 0), (-1, -1), 5), ('BOTTOMPADDING', (0, 0), (-1, -1), 5)]))
    story.append(receptor_table)
    story.append(Spacer(1, 3*mm))

    # Tabla de productos y footer (mantén tu lógica actual aquí...)
    # ... (omitido para brevedad, pero usa tu código original para estas partes)
    
    doc.build(story)
    print(f"PDF generado: {output_path}")
