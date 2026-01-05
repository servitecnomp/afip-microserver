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
    if len(str(vencimiento_str)) == 8:
        v = str(vencimiento_str)
        return f"{v[6:8]}/{v[4:6]}/{v[0:4]}"
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
    vencimiento_cae = formatear_vencimiento_cae(datos_factura["vencimiento_cae"])
    tipo_cbte = int(datos_factura.get("tipo_cbte", 11))
    letra_cbte = "C"
    codigo_cbte = "013" if tipo_cbte == 13 else "011"
    emisor = EMISOR_DATA.get(cuit_emisor, EMISOR_DATA["27239676931"])

    doc = SimpleDocTemplate(output_path, pagesize=A4, rightMargin=15*mm, leftMargin=15*mm, topMargin=10*mm, bottomMargin=10*mm)
    styles = getSampleStyleSheet()
    style_small = ParagraphStyle('Small', fontSize=8, leading=10)
    style_letra = ParagraphStyle('LetraC', fontSize=28, alignment=TA_CENTER, leading=26)
    style_cod = ParagraphStyle('Cod', fontSize=7, alignment=TA_CENTER)

    story = []

    # 1. ORIGINAL / DUPLICADO
    tipo_copia = "ORIGINAL" if "duplicado" not in output_path.lower() else "DUPLICADO"
    story.append(Table([[tipo_copia]], colWidths=[180*mm], style=[('BOX',(0,0),(-1,-1),1,colors.black),('ALIGN',(0,0),(-1,-1),'CENTER')]))

    # 2. Contenido Izquierdo y Derecho
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

    col_der = [
        Paragraph(f"<b><font size=18>{'NOTA DE CRÉDITO' if tipo_cbte == 13 else 'FACTURA'}</font></b>", ParagraphStyle('Tit', alignment=TA_CENTER)),
        Spacer(1, 4*mm),
        Paragraph(f"<b>Punto de Venta:</b> {str(datos_factura['punto_venta']).zfill(5)} &nbsp; <b>Comp. Nro:</b> {str(datos_factura['cbte_nro']).zfill(8)}", style_small),
        Paragraph(f"<b>Fecha de Emisión:</b> {fecha_emision.strftime('%d/%m/%Y')}", style_small),
        Paragraph(f"<b>CUIT:</b> {cuit_emisor}", style_small),
        Paragraph(f"<b>Ingresos Brutos:</b> {emisor['ingresos_brutos']}", style_small),
        Paragraph(f"<b>Inicio Actividades:</b> {emisor['inicio_actividades']}", style_small),
    ]

    # 3. ENCABEZADO: 4 Columnas con línea central única
    bloque_afip = Table([
        [col_izq, Paragraph(f"<b>{letra_cbte}</b><br/><font size=7>COD. {codigo_cbte}</font>", style_letra), "", col_der]
    ], colWidths=[82*mm, 8*mm, 8*mm, 82*mm])

    bloque_afip.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('SPAN', (1, 0), (2, 0)),                      # Une las celdas del medio para el cuadrado
        ('BOX', (1, 0), (2, 0), 1, colors.black),      # Dibuja el cuadrado de la C
        ('BACKGROUND', (1, 0), (2, 0), colors.white),  # Tapa la línea que pasa por detrás
        ('LINEBEFORE', (2, 0), (2, 0), 1, colors.black), # ESTA ES LA ÚNICA LÍNEA CENTRAL
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (1, 0), (2, 0), 'CENTER'),
    ]))
    story.append(bloque_afip)
    story.append(Spacer(1, 2*mm))

    # 4. Período y Receptor
    story.append(Table([[Paragraph(f"<b>Período Facturado Desde:</b> {fecha_emision.strftime('%d/%m/%Y')} &nbsp; <b>Hasta:</b> {fecha_emision.strftime('%d/%m/%Y')} &nbsp; <b>Fecha de Vto. para el pago:</b> {fecha_emision.strftime('%d/%m/%Y')}", style_small)]], colWidths=[180*mm], style=[('BOX',(0,0),(-1,-1),1,colors.black)]))
    story.append(Spacer(1, 1*mm))
    
    rec_info = f"<b>CUIT:</b> {datos_factura['cuit_receptor']} &nbsp; <b>Razón Social:</b> {datos_factura.get('compania', 'Consumidor Final')}<br/>" \
               f"<b>Condición frente al IVA:</b> {datos_factura.get('condicion_iva', 'IVA Responsable Inscripto')}<br/>" \
               f"<b>Domicilio:</b> {datos_factura.get('domicilio', '')}"
    story.append(Table([[Paragraph(rec_info, style_small)]], colWidths=[180*mm], style=[('BOX',(0,0),(-1,-1),1,colors.black), ('LEFTPADDING',(0,0),(-1,-1),5)]))
    story.append(Spacer(1, 4*mm))

    # 5. TABLA DE PRODUCTOS (8 COLUMNAS)
    importe = float(datos_factura["importe"])
    prod_header = ["Código", "Producto / Servicio", "Cantidad", "U. Medida", "Precio Unit.", "% Bonif", "Imp. Bonif.", "Subtotal"]
    prod_row = ["", Paragraph(datos_factura.get("descripcion", "Servicio"), style_small), "1,00", "unidades", f"{importe:,.2f}", "0,00", "0,00", f"{importe:,.2f}"]
    
    t_prod = Table([prod_header, prod_row], colWidths=[15*mm, 65*mm, 18*mm, 18*mm, 20*mm, 14*mm, 15*mm, 15*mm])
    t_prod.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('FONTSIZE', (0,0), (-1,-1), 7),
        ('ALIGN', (2,0), (-1,-1), 'CENTER'),
    ]))
    story.append(t_prod)

    # 6. Totales y Pie (QR + CAE)
    story.append(Spacer(1, 5*mm))
    totales = [["", "Importe Neto Gravado $", f"{importe:,.2f}"], ["", "Importe Otros Tributos $", "0,00"], ["", "Importe Total $", f"{importe:,.2f}"]]
    t_tot = Table(totales, colWidths=[110*mm, 45*mm, 25*mm])
    t_tot.setStyle(TableStyle([('ALIGN', (1,0), (-1,-1), 'RIGHT'), ('FONTNAME', (2,2), (2,2), 'Helvetica-Bold')]))
    story.append(t_tot)

    qr_img = RLImage(generar_qr_afip(datos_factura), 35*mm, 35*mm)
    footer_text = f"<para align=right>Pág. 1/1<br/><br/><b>CAE N°:</b> {datos_factura['cae']}<br/>" \
                  f"<b>Fecha de Vto. de CAE:</b> {vencimiento_cae}<br/><br/><b>Comprobante Autorizado</b></para>"
    
    story.append(Spacer(1, 10*mm))
    story.append(Table([[qr_img, "", Paragraph(footer_text, style_small)]], colWidths=[40*mm, 90*mm, 50*mm], style=[('VALIGN',(0,0),(-1,-1),'BOTTOM')]))

    doc.build(story)
