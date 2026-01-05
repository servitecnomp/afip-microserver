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

# Datos fijos para el diseño
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
    if len(vencimiento_str) == 8:
        return f"{vencimiento_str[6:8]}/{vencimiento_str[4:6]}/{vencimiento_str[0:4]}"
    return vencimiento_str

def generar_qr_afip(datos_factura):
    qr_data = {
        "ver": 1, "fecha": datos_factura["fecha_emision"].strftime("%Y-%m-%d"),
        "cuit": int(str(datos_factura["cuit_emisor"]).replace("-","")),
        "ptoVta": int(datos_factura["punto_venta"]),
        "tipoCmp": int(datos_factura["tipo_cbte"]),
        "nroCmp": int(datos_factura["cbte_nro"]),
        "importe": float(datos_factura["importe"]),
        "moneda": "PES", "ctz": 1, "tipoDocRec": 80,
        "nroDocRec": int(str(datos_factura["cuit_receptor"]).replace("-","")),
        "tipoCodAut": "E", "codAut": int(datos_factura["cae"])
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
    cuit_emisor = str(datos_factura["cuit_emisor"]).replace("-", "").replace(" ", "")
    fecha_emision = datos_factura["fecha_emision"]
    vencimiento_cae = formatear_vencimiento_cae(str(datos_factura["vencimiento_cae"]))
    tipo_cbte = int(datos_factura.get("tipo_cbte", 11))
    letra_cbte = "C"
    codigo_cbte = "013" if tipo_cbte == 13 else "011"
    emisor = EMISOR_DATA.get(cuit_emisor, EMISOR_DATA["27239676931"])

    doc = SimpleDocTemplate(output_path, pagesize=A4, rightMargin=15*mm, leftMargin=15*mm, topMargin=10*mm, bottomMargin=10*mm)
    styles = getSampleStyleSheet()
    
    # Estilos de texto
    style_small = ParagraphStyle('Small', fontSize=8, leading=10)
    style_letra = ParagraphStyle('LetraC', fontSize=28, alignment=TA_CENTER, leading=26)

    story = []

    # 1. Franja ORIGINAL / DUPLICADO
    tipo_copia = "ORIGINAL" if "duplicado" not in output_path.lower() else "DUPLICADO"
    story.append(Table([[tipo_copia]], colWidths=[180*mm], style=[('BOX',(0,0),(-1,-1),1,colors.black),('ALIGN',(0,0),(-1,-1),'CENTER')]))

    # 2. Preparar columnas laterales
    try:
        logo = RLImage(logo_path, width=25*mm, height=25*mm)
    except:
        logo = Paragraph("<b>LOGO</b>", style_small)

    col_izq = [
        logo,
        Spacer(1, 2*mm),
        Paragraph(f"<b><font size=14>{emisor['razon_social']}</font></b>", style_small),
        Paragraph(f"<b>Razón Social:</b> {emisor['razon_social']}", style_small),
        Paragraph(f"<b>Domicilio Comercial:</b> {emisor['domicilio']}", style_small),
        Paragraph(f"<b>Condición frente al IVA:</b> {emisor['condicion_iva']}", style_small),
    ]

    titulo_cbte = "NOTA DE CRÉDITO" if tipo_cbte == 13 else "FACTURA"
    col_der = [
        Paragraph(f"<b><font size=18>{titulo_cbte}</font></b>", ParagraphStyle('Tit', alignment=TA_CENTER)),
        Spacer(1, 4*mm),
        Paragraph(f"<b>Punto de Venta:</b> {str(datos_factura['punto_venta']).zfill(5)} &nbsp; <b>Comp. Nro:</b> {str(datos_factura['cbte_nro']).zfill(8)}", style_small),
        Paragraph(f"<b>Fecha de Emisión:</b> {fecha_emision.strftime('%d/%m/%Y')}", style_small),
        Paragraph(f"<b>CUIT:</b> {cuit_emisor}", style_small),
        Paragraph(f"<b>Ingresos Brutos:</b> {emisor['ingresos_brutos']}", style_small),
        Paragraph(f"<b>Inicio de Actividades:</b> {emisor['inicio_actividades']}", style_small),
    ]

    # 3. BLOQUE DE 4 COLUMNAS (Línea central exacta)
    # 82mm + 8mm + 8mm + 82mm = 180mm total
    bloque_afip = Table([
        [col_izq, Paragraph(f"<b>{letra_cbte}</b><br/><font size=7>COD. {codigo_cbte}</font>", style_letra), "", col_der]
    ], colWidths=[82*mm, 8*mm, 8*mm, 82*mm])

    bloque_afip.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('SPAN', (1, 0), (2, 0)),                      # Une las celdas de 8mm para la C
        ('BOX', (1, 0), (2, 0), 1, colors.black),      # Cuadrado de la C
        ('BACKGROUND', (1, 0), (2, 0), colors.white),  # Tapa la línea central
        ('LINEBEFORE', (2, 0), (2, 0), 1, colors.black), # LA LÍNEA DEL MEDIO
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (1, 0), (2, 0), 'CENTER'),
        ('TOPPADDING', (1, 0), (2, 0), 1),
    ]))
    story.append(bloque_afip)
    story.append(Spacer(1, 2*mm))

    # 4. Período y Receptor
    story.append(Table([[Paragraph(f"<b>Período Facturado Desde:</b> {fecha_emision.strftime('%d/%m/%Y')} &nbsp; <b>Hasta:</b> {fecha_emision.strftime('%d/%m/%Y')}", style_small)]], colWidths=[180*mm], style=[('BOX',(0,0),(-1,-1),1,colors.black)]))
    story.append(Spacer(1, 1*mm))
    
    rec_info = f"<b>CUIT:</b> {datos_factura['cuit_receptor']} &nbsp; <b>Razón Social:</b> {datos_factura.get('compania', 'Consumidor Final')}<br/>" \
               f"<b>Condición frente al IVA:</b> {datos_factura.get('condicion_iva', 'IVA Responsable Inscripto')}<br/>" \
               f"<b>Domicilio:</b> {datos_factura.get('domicilio', '')}"
    story.append(Table([[Paragraph(rec_info, style_small)]], colWidths=[180*mm], style=[('BOX',(0,0),(-1,-1),1,colors.black), ('LEFTPADDING',(0,0),(-1,-1),5)]))
    story.append(Spacer(1, 4*mm))

    # 5. Tabla de Productos
    importe = float(datos_factura["importe"])
    prod_table = Table([
        ["Producto / Servicio", "Cantidad", "Precio Unit.", "Subtotal"],
        [Paragraph(datos_factura.get("descripcion", "Servicio"), style_small), "1.00", f"{importe:,.2f}", f"{importe:,.2f}"]
    ], colWidths=[100*mm, 20*mm, 30*mm, 30*mm])
    prod_table.setStyle(TableStyle([('GRID',(0,0),(-1,-1),0.5,colors.black), ('BACKGROUND',(0,0),(-1,0),colors.lightgrey), ('ALIGN',(1,0),(-1,-1),'CENTER')]))
    story.append(prod_table)

    # 6. Totales y Pie (QR + CAE)
    story.append(Spacer(1, 5*mm))
    story.append(Paragraph(f"<para align=right><b>Importe Total: $ {importe:,.2f}</b></para>", styles['Normal']))
    
    qr_img = RLImage(generar_qr_afip(datos_factura), 35*mm, 35*mm)
    cae_info = f"<para align=right><b>CAE N°:</b> {datos_factura['cae']}<br/><b>Vto. CAE:</b> {vencimiento_cae}</para>"
    story.append(Spacer(1, 10*mm))
    story.append(Table([[qr_img, Paragraph(cae_info, style_small)]], colWidths=[50*mm, 130*mm], style=[('VALIGN',(0,0),(-1,-1),'BOTTOM')]))

    doc.build(story)
