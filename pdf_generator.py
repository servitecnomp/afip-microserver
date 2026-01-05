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
    if len(vencimiento_str) == 8:
        anio = vencimiento_str[0:4]
        mes = vencimiento_str[4:6]
        dia = vencimiento_str[6:8]
        return f"{dia}/{mes}/{anio}"
    return vencimiento_str

def generar_qr_afip(datos_factura):
    cuitt_emisor = str(datos_factura["cuit_emisor"]).replace("-", "")
    cuit_receptor = str(datos_factura["cuit_receptor"]).replace("-", "")
    
    qr_data = {
        "ver": 1,
        "fecha": datos_factura["fecha_emision"].strftime("%Y-%m-%d"),
        "cuit": int(cuitt_emisor),
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
    cuit_emisor = str(datos_factura["cuit_emisor"]).replace("-", "").replace(" ", "")
    cuit_receptor = str(datos_factura["cuit_receptor"]).replace("-", "").replace(" ", "")
    fecha_emision = datos_factura["fecha_emision"]
    vencimiento_cae = formatear_vencimiento_cae(str(datos_factura["vencimiento_cae"]))

    tipo_cbte = int(datos_factura.get("tipo_cbte", 11))
    es_nota_credito = (tipo_cbte == 13)
    letra_cbte = "C"
    codigo_cbte = "013" if es_nota_credito else "011"

    emisor = EMISOR_DATA.get(cuit_emisor, EMISOR_DATA["27239676931"])

    if datos_factura.get("compania"):
        receptor = {
            "razon_social": datos_factura.get("compania"),
            "domicilio": datos_factura.get("domicilio", ""),
            "condicion_iva": datos_factura.get("condicion_iva", "IVA Responsable Inscripto")
        }
    else:
        receptor = COMPANIAS.get(cuit_receptor, {"razon_social": "Cliente", "domicilio": "", "condicion_iva": "IVA Responsable Inscripto"})

    qr_buffer = generar_qr_afip(datos_factura)

    doc = SimpleDocTemplate(output_path, pagesize=A4, rightMargin=15*mm, leftMargin=15*mm, topMargin=10*mm, bottomMargin=10*mm)
    styles = getSampleStyleSheet()
    style_small = ParagraphStyle('Small', fontSize=8, leading=10)

    story = []

    # ===================== 1. ORIGINAL =====================
    encabezado_top = Table([["ORIGINAL"]], colWidths=[180*mm])
    encabezado_top.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
    ]))
    story.append(encabezado_top)

    # ===================== 2. BLOQUE PRINCIPAL AFIP =====================
    # Contenido Izquierdo
    try:
        logo = RLImage(logo_path, width=25*mm, height=25*mm)
    except:
        logo = Paragraph("<b>LOGO</b>", style_small)

    col_izq = [
        logo,
        Spacer(1, 2*mm),
        Paragraph(f"<b><font size=12>{emisor['razon_social']}</font></b>", style_small),
        Spacer(1, 2*mm),
        Paragraph(f"<b>Razón Social:</b> {emisor['razon_social']}", style_small),
        Paragraph(f"<b>Domicilio Comercial:</b> {emisor['domicilio']}", style_small),
        Paragraph(f"<b>Condición frente al IVA:</b> {emisor['condicion_iva']}", style_small),
    ]

    # Cuadrado Central
    celda_letra = Table([
        [Paragraph(f"<b>{letra_cbte}</b>", ParagraphStyle('C', fontSize=28, alignment=TA_CENTER))],
        [Paragraph(f"COD. {codigo_cbte}", ParagraphStyle('Cod', fontSize=8, alignment=TA_CENTER))]
    ], colWidths=[16*mm], rowHeights=[12*mm, 6*mm])
    celda_letra.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))

    # Contenido Derecho
    titulo_texto = "NOTA DE CRÉDITO" if es_nota_credito else "FACTURA"
    col_der = [
        Paragraph(f"<b><font size=18>{titulo_texto}</font></b>", ParagraphStyle('Tit', alignment=TA_CENTER)),
        Spacer(1, 4*mm),
        Paragraph(f"<b>Punto de Venta:</b> {str(datos_factura['punto_venta']).zfill(5)} &nbsp; <b>Comp. Nro:</b> {str(datos_factura['cbte_nro']).zfill(8)}", style_small),
        Paragraph(f"<b>Fecha de Emisión:</b> {fecha_emision.strftime('%d/%m/%Y')}", style_small),
        Spacer(1, 2*mm),
        Paragraph(f"<b>CUIT:</b> {cuit_emisor}", style_small),
        Paragraph(f"<b>Ingresos Brutos:</b> {emisor['ingresos_brutos']}", style_small),
        Paragraph(f"<b>Fecha de Inicio de Actividades:</b> {emisor['inicio_actividades']}", style_small),
    ]

    bloque_principal = Table([[col_izq, celda_letra, col_der]], colWidths=[82*mm, 16*mm, 82*mm])
    bloque_principal.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('LINEBEFORE', (1, 0), (1, 0), 1, colors.black),
        ('LINEAFTER', (1, 0), (1, 0), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
        ('TOPPADDING', (1, 0), (1, 0), -0.1),
    ]))
    story.append(bloque_principal)
    story.append(Spacer(1, 2*mm))

    # ===================== 3. PERÍODO =====================
    periodo_table = Table([[Paragraph(f"<b>Período Facturado Desde:</b> {fecha_emision.strftime('%d/%m/%Y')} &nbsp; <b>Hasta:</b> {fecha_emision.strftime('%d/%m/%Y')} &nbsp; <b>Fecha de Vto. para el pago:</b> {fecha_emision.strftime('%d/%m/%Y')}", style_small)]], colWidths=[180*mm])
    periodo_table.setStyle(TableStyle([('BOX', (0, 0), (-1, -1), 1, colors.black)]))
    story.append(periodo_table)
    story.append(Spacer(1, 2*mm))

    # ===================== 4. RECEPTOR =====================
    rec_text = f"<b>CUIT:</b> {cuit_receptor} &nbsp; <b>Apellido y Nombre / Razón Social:</b> {receptor['razon_social']}<br/>" \
               f"<b>Condición frente al IVA:</b> {receptor['condicion_iva']}<br/>" \
               f"<b>Domicilio:</b> {receptor['domicilio']}<br/>" \
               f"<b>Condición de venta:</b> Otra"
    receptor_table = Table([[Paragraph(rec_text, style_small)]], colWidths=[180*mm])
    receptor_table.setStyle(TableStyle([('BOX', (0, 0), (-1, -1), 1, colors.black), ('LEFTPADDING', (0, 0), (-1, -1), 5)]))
    story.append(receptor_table)
    story.append(Spacer(1, 3*mm))

    # ===================== 5. PRODUCTOS =====================
    importe = float(datos_factura["importe"])
    productos_table = Table([
        ["Código", "Producto / Servicio", "Cantidad", "U. Medida", "Precio Unit.", "% Bonif", "Imp. Bonif.", "Subtotal"],
        ["", datos_factura.get("descripcion", "Servicio"), "1,00", "unidades", f"{importe:,.2f}", "0,00", "0,00", f"{importe:,.2f}"]
    ], colWidths=[15*mm, 65*mm, 18*mm, 18*mm, 20*mm, 13*mm, 13*mm, 18*mm])
    productos_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTSIZE', (0, 0), (-1, -1), 7),
    ]))
    story.append(productos_table)
    story.append(Spacer(1, 5*mm))

    # ===================== 6. TOTALES =====================
    totales_table = Table([
        ["", "Importe Neto Gravado $", f"{importe:,.2f}"],
        ["", "Importe Otros Tributos $", "0,00"],
        ["", "Importe Total $", f"{importe:,.2f}"]
    ], colWidths=[100*mm, 60*mm, 20*mm])
    totales_table.setStyle(TableStyle([('ALIGN', (1, 0), (-1, -1), 'RIGHT'), ('FONTNAME', (2, 2), (2, 2), 'Helvetica-Bold')]))
    story.append(totales_table)
    story.append(Spacer(1, 10*mm))

    # ===================== 7. FOOTER (QR Y CAE) =====================
    qr_img = RLImage(qr_buffer, width=35*mm, height=35*mm)
    footer_text = f"<para align=right>Pág. 1/1<br/><br/><b>CAE N°:</b> {datos_factura['cae']}<br/>" \
                  f"<b>Fecha de Vto. de CAE:</b> {vencimiento_cae}<br/><br/>" \
                  f"<b>Comprobante Autorizado</b></para>"
    
    footer_table = Table([[qr_img, "", Paragraph(footer_text, style_small)]], colWidths=[40*mm, 90*mm, 50*mm])
    footer_table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'BOTTOM')]))
    story.append(footer_table)

    doc.build(story)
    print(f"Factura generada en: {output_path}")
