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
    """Crea un PDF de factura o nota de crédito con formato AFIP"""

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

    qr_buffer = generar_qr_afip(datos_factura)

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=15*mm,
        leftMargin=15*mm,
        topMargin=10*mm,
        bottomMargin=10*mm
    )

    styles = getSampleStyleSheet()
    style_normal = ParagraphStyle('Normal', fontSize=8, leading=10)
    style_small = ParagraphStyle('Small', fontSize=7, leading=9)

    story = []

    # ===================== ORIGINAL =====================
    encabezado = Table([["ORIGINAL"]], colWidths=[180*mm])
    encabezado.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
    ]))
    story.append(encabezado)
    story.append(Spacer(1, 2*mm))

    # ===================== LOGO =====================
    try:
        logo = RLImage(logo_path, width=20*mm, height=20*mm)
    except:
        logo = Paragraph("<b>LOGO</b>", style_normal)

    # ===================== EMISOR =====================
    col_emisor = Table([
        [logo],
        [Paragraph(
            f"<b>{emisor['razon_social']}</b><br/><br/>"
            f"<b>Razón Social:</b> {emisor['razon_social']}<br/>"
            f"<b>Domicilio Comercial:</b> {emisor['domicilio']}<br/>"
            f"<b>Condición frente al IVA:</b> {emisor['condicion_iva']}",
            style_small
        )]
    ], colWidths=[85*mm], rowHeights=[20*mm, None])

    # ===================== CUADRADO CENTRAL AFIP =====================
    codigo_cbte = "013" if es_nota_credito else "011"

    col_letra = Table([
        [Paragraph("<para align=center><b><font size=28>C</font></b></para>", style_normal)],
        [Paragraph(f"<para align=center><font size=8>COD. {codigo_cbte}</font></para>", style_normal)]
    ], colWidths=[20*mm], rowHeights=[14*mm, 6*mm])

    col_letra.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1.5, colors.black),
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))

    # ===================== FACTURA =====================
    titulo_cbte = "NOTA DE CRÉDITO" if es_nota_credito else "FACTURA"

    col_factura = Paragraph(
        f"<b><font size=11>{titulo_cbte}</font></b><br/><br/>"
        f"<b>Punto de Venta:</b> {str(datos_factura['punto_venta']).zfill(5)}  "
        f"<b>Comp. Nro:</b> {str(datos_factura['cbte_nro']).zfill(8)}<br/>"
        f"<b>Fecha de Emisión:</b> {fecha_emision.strftime('%d/%m/%Y')}<br/><br/>"
        f"<b>CUIT:</b> {cuit_emisor}<br/>"
        f"<b>Ingresos Brutos:</b> {emisor['ingresos_brutos']}<br/>"
        f"<b>Fecha de Inicio de Actividades:</b> {emisor['inicio_actividades']}",
        style_small
    )

    # ===================== BLOQUE PRINCIPAL AFIP =====================
    bloque_principal = Table(
        [[col_emisor, col_letra, col_factura]],
        colWidths=[80*mm, 20*mm, 80*mm]
    )

bloque_principal.setStyle(TableStyle([
    ('BOX', (0, 0), (-1, -1), 1, colors.black),

    # Línea divisoria AFIP
    ('LINEAFTER', (0, 0), (0, 0), 1.2, colors.black),

    ('VALIGN', (0, 0), (-1, -1), 'TOP'),

    # ❌ SIN padding horizontal (CLAVE)
    ('LEFTPADDING', (0, 0), (-1, -1), 0),
    ('RIGHTPADDING', (0, 0), (-1, -1), 0),

    # Padding vertical mínimo
    ('TOPPADDING', (0, 0), (-1, -1), 4),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
]))


    story.append(bloque_principal)
    story.append(Spacer(1, 2*mm))

    # ===================== PERÍODO =====================
    periodo_table = Table([[
        Paragraph(
            f"<b>Período Facturado Desde:</b> {fecha_emision.strftime('%d/%m/%Y')}  "
            f"<b>Hasta:</b> {fecha_emision.strftime('%d/%m/%Y')}  "
            f"<b>Fecha de Vto. para el pago:</b> {fecha_emision.strftime('%d/%m/%Y')}",
            style_small
        )
    ]], colWidths=[180*mm])

    periodo_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
    ]))
    story.append(periodo_table)
    story.append(Spacer(1, 2*mm))

    # ===================== RECEPTOR =====================
    receptor_content = (
        f"<b>CUIT:</b> {cuit_receptor}<br/>"
        f"<b>Apellido y Nombre / Razón Social:</b> {receptor['razon_social']}<br/>"
        f"<b>Condición frente al IVA:</b> {receptor['condicion_iva']}<br/>"
        f"<b>Domicilio:</b> {receptor['domicilio']}<br/>"
        f"<b>Condición de venta:</b> Otra"
    )

    receptor_table = Table([[Paragraph(receptor_content, style_small)]], colWidths=[180*mm])
    receptor_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
    ]))
    story.append(receptor_table)
    story.append(Spacer(1, 3*mm))

    # ===================== PRODUCTOS =====================
    importe = float(datos_factura["importe"])
    descripcion = datos_factura.get("descripcion", "Servicio")

    productos_table = Table([
        ["", "Producto / Servicio", "Cantidad", "U. Medida", "Precio Unit.", "% Bonif", "Imp. Bonif.", "Subtotal"],
        ["", descripcion, "1,00", "unidades", f"{importe:,.2f}", "0,00", "0,00", f"{importe:,.2f}"]
    ], colWidths=[15*mm, 70*mm, 18*mm, 18*mm, 18*mm, 13*mm, 13*mm, 18*mm])

    productos_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (1, 1), (1, 1), 'LEFT'),
    ]))

    story.append(productos_table)
    story.append(Spacer(1, 3*mm))

    # ===================== TOTALES =====================
    totales_table = Table([
        ["", "Subtotal $", f"{importe:,.2f}"],
        ["", "Importe Otros Tributos $", "0,00"],
        ["", "Importe Total $", f"{importe:,.2f}"]
    ], colWidths=[100*mm, 60*mm, 20*mm])

    totales_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
    ]))
    story.append(totales_table)
    story.append(Spacer(1, 5*mm))

    # ===================== FOOTER =====================
    qr_img = RLImage(qr_buffer, width=40*mm, height=40*mm)

    footer = Table([
        [qr_img, "",
         Paragraph(
             f"<para align=right>"
             f"Pág. 1/1<br/><br/>"
             f"<b>CAE N°:</b> {datos_factura['cae']}<br/>"
             f"<b>Fecha de Vto. de CAE:</b> {vencimiento_cae}<br/><br/>"
             f"<b>Comprobante Autorizado</b><br/>"
             f"<font size=6>Esta Agencia no se responsabiliza por los datos ingresados</font>"
             f"</para>",
             style_small
         )]
    ], colWidths=[45*mm, 90*mm, 45*mm])

    story.append(footer)

    doc.build(story)
    print(f"PDF generado exitosamente: {output_path}")


