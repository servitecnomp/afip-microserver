"""
Generador de PDFs para facturas AFIP con código QR
Según especificaciones RG 5198/2022
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
import qrcode
from io import BytesIO
import json
import base64
from datetime import datetime

# Datos del emisor
EMISOR_DATA = {
    "27239676931": {
        "razon_social": "DEVRIES MARIA PAULA",
        "domicilio": "Rodriguez Peña 1789 - Mar Del Plata Sur, Buenos Aires",
        "cuit": "27239676931",
        "condicion_iva": "Responsable Monotributo",
        "ingresos_brutos": "27239676931",
        "inicio_actividades": "01/01/2021"
    },
    "27461124149": {
        "razon_social": "CACCIATO MARIA MERCEDES",
        "domicilio": "General Paz 4662 - Mar Del Plata Sur, Buenos Aires",
        "cuit": "27461124149",
        "condicion_iva": "Responsable Monotributo",
        "ingresos_brutos": "27461124149",
        "inicio_actividades": "01/12/2023"
    }
}

# Mapeo de compañías de seguros
COMPANIAS = {
    "20226717871": {
        "razon_social": "LA SEGUNDA COOPERATIVA LIMITADA DE SEGUROS GENERALES",
        "domicilio": "Juan Manuel De Rosas 957 - Rosario Norte, Santa Fe",
        "condicion_iva": "IVA Responsable Inscripto"
    },
    "30500017704": {
        "razon_social": "LA SEGUNDA COOPERATIVA LTDA DE SEGUROS GENERALES",
        "domicilio": "Juan Manuel De Rosas 957 - Rosario Norte, Santa Fe",
        "condicion_iva": "IVA Responsable Inscripto"
    },
    "30546744449": {
        "razon_social": "MERCANTIL ANDINA SEGUROS SA",
        "domicilio": "Av. Corrientes 330 - CABA, Buenos Aires",
        "condicion_iva": "IVA Responsable Inscripto"
    },
    "30500036911": {
        "razon_social": "COMPAÑIA DE SEGUROS LA MERCANTIL ANDINA S.A.",
        "domicilio": "Belgrano Av. 672 - Capital Federal, Ciudad de Buenos Aires",
        "condicion_iva": "IVA Responsable Inscripto"
    },
    "30682305009": {
        "razon_social": "LA CAJA DE SEGUROS SA",
        "domicilio": "Av. Belgrano 1370 - CABA, Buenos Aires",
        "condicion_iva": "IVA Responsable Inscripto"
    },
    "30601327416": {
        "razon_social": "TRIUNFO COOPERATIVA DE SEGUROS LTDA",
        "domicilio": "Av. Corrientes 327 - CABA, Buenos Aires",
        "condicion_iva": "IVA Responsable Inscripto"
    }
}

def formatear_vencimiento_cae(vencimiento):
    """Convierte AAAAMMDD a DD/MM/AAAA"""
    if isinstance(vencimiento, str) and len(vencimiento) == 8:
        return f"{vencimiento[6:8]}/{vencimiento[4:6]}/{vencimiento[0:4]}"
    return vencimiento

def generar_qr_afip(datos_factura):
    """Genera código QR según especificaciones AFIP"""
    qr_data = {
        "ver": 1,
        "fecha": datos_factura["fecha_emision"].strftime("%Y-%m-%d"),
        "cuit": int(datos_factura["cuit_emisor"].replace("-", "")),
        "ptoVta": int(datos_factura["punto_venta"]),
        "tipoCmp": int(datos_factura["tipo_cbte"]),
        "nroCmp": int(datos_factura["cbte_nro"]),
        "importe": float(datos_factura["importe"]),
        "moneda": "PES",
        "ctz": 1,
        "tipoDocRec": 80,
        "nroDocRec": int(datos_factura["cuit_receptor"].replace("-", "")),
        "tipoCodAut": "E",
        "codAut": int(datos_factura["cae"])
    }
    
    json_str = json.dumps(qr_data, separators=(',', ':'))
    base64_data = base64.b64encode(json_str.encode()).decode()
    qr_url = f"https://www.arca.gob.ar/fe/qr/?p={base64_data}"
    
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
    qr.add_data(qr_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    
    img_buffer = BytesIO()
    qr_img.save(img_buffer, format='PNG')
    img_buffer.seek(0)
    return img_buffer

def crear_pdf_factura(datos_factura, logo_path, output_path):
    """Crea un PDF de factura con formato AFIP oficial"""
    
    cuit_emisor = str(datos_factura["cuit_emisor"]).replace("-", "").replace(" ", "")
    cuit_receptor = str(datos_factura["cuit_receptor"]).replace("-", "").replace(" ", "")
    fecha_emision = datos_factura["fecha_emision"]
    vencimiento_cae = formatear_vencimiento_cae(str(datos_factura["vencimiento_cae"]))
    
    # Obtener datos del emisor
    emisor = EMISOR_DATA.get(cuit_emisor, EMISOR_DATA["27239676931"])
    
    # Obtener datos del receptor - PRIMERO de datos_factura, sino del mapeo
    if datos_factura.get("compania"):
        # Si hay compañía en datos_factura, usarla (domicilio puede estar vacío)
        receptor = {
            "razon_social": datos_factura.get("compania", "Cliente"),
            "domicilio": datos_factura.get("domicilio", ""),
            "condicion_iva": datos_factura.get("condicion_iva", "IVA Responsable Inscripto")
        }
    else:
        # Fallback al mapeo hardcodeado
        receptor = COMPANIAS.get(cuit_receptor, {
            "razon_social": "Cliente",
            "domicilio": "",
            "condicion_iva": "IVA Responsable Inscripto"
        })
    
    qr_buffer = generar_qr_afip(datos_factura)
    
    doc = SimpleDocTemplate(output_path, pagesize=A4, rightMargin=20*mm, leftMargin=20*mm, topMargin=15*mm, bottomMargin=15*mm)
    
    styles = getSampleStyleSheet()
    style_normal = ParagraphStyle('Normal', parent=styles['Normal'], fontSize=8, leading=10)
    
    story = []
    
    # ENCABEZADO ORIGINAL
    encabezado_table = Table([["ORIGINAL"]], colWidths=[170*mm])
    encabezado_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(encabezado_table)
    story.append(Spacer(1, 3*mm))
    
    # BLOQUE PRINCIPAL CON LOGO
    try:
        logo = RLImage(logo_path, width=25*mm, height=25*mm)
    except:
        logo = Paragraph("<b>LOGO</b>", style_normal)
    
    main_table = Table([
        [logo,
         Paragraph("<para align=center><b><font size=24>C</font></b><br/><font size=8>COD. 011</font></para>", style_normal),
         Paragraph(f"<b>FACTURA</b><br/><br/>"
                  f"Punto de Venta: {str(datos_factura['punto_venta']).zfill(5)}  "
                  f"Comp. Nro: {str(datos_factura['cbte_nro']).zfill(8)}<br/>"
                  f"Fecha de Emisión: {fecha_emision.strftime('%d/%m/%Y')}<br/>"
                  f"CUIT: {cuit_emisor}<br/>"
                  f"Ingresos Brutos: {emisor['ingresos_brutos']}<br/>"
                  f"Fecha de Inicio de Actividades: {emisor['inicio_actividades']}", style_normal)]
    ], colWidths=[30*mm, 25*mm, 115*mm])
    
    main_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, 0), 'CENTER'),
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
        ('ALIGN', (2, 0), (2, 0), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('BOX', (1, 0), (1, 0), 2, colors.black),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    
    # Emisor en segunda fila
    emisor_text = Paragraph(f"<b>{emisor['razon_social']}</b><br/><br/>"
                           f"Razón Social: {emisor['razon_social']}<br/>"
                           f"Domicilio Comercial: {emisor['domicilio']}<br/>"
                           f"Condición frente al IVA: {emisor['condicion_iva']}", style_normal)
    
    combined_table = Table([
        [main_table],
        [emisor_text]
    ], colWidths=[170*mm])
    
    combined_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('TOPPADDING', (0, 1), (0, 1), 8),
        ('BOTTOMPADDING', (0, 1), (0, 1), 8),
        ('LEFTPADDING', (0, 1), (0, 1), 8),
    ]))
    
    story.append(combined_table)
    story.append(Spacer(1, 2*mm))
    
    # PERÍODO
    fecha_str = fecha_emision.strftime("%d/%m/%Y")
    periodo_table = Table([[Paragraph(f"Período Facturado Desde: {fecha_str}  Hasta: {fecha_str}  "
                                     f"Fecha de Vto. para el pago: {fecha_str}", style_normal)]], colWidths=[170*mm])
    periodo_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(periodo_table)
    story.append(Spacer(1, 2*mm))
    
    # RECEPTOR
    receptor_table = Table([[Paragraph(f"CUIT: {cuit_receptor}<br/>"
                                      f"Apellido y Nombre / Razón Social: {receptor['razon_social']}<br/>"
                                      f"Condición frente al IVA: {receptor['condicion_iva']}<br/>"
                                      f"Domicilio: {receptor['domicilio']}<br/>"
                                      f"Condición de venta: Otra", style_normal)]], colWidths=[170*mm])
    receptor_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(receptor_table)
    story.append(Spacer(1, 5*mm))
    
    # DETALLE
    importe = float(datos_factura["importe"])
    detalle_table = Table([
        [Paragraph("<b>Código</b>", style_normal), Paragraph("<b>Producto / Servicio</b>", style_normal),
         Paragraph("<b>Cantidad</b>", style_normal), Paragraph("<b>U. Medida</b>", style_normal),
         Paragraph("<b>Precio Unit.</b>", style_normal), Paragraph("<b>% Bonif</b>", style_normal),
         Paragraph("<b>Imp. Bonif.</b>", style_normal), Paragraph("<b>Subtotal</b>", style_normal)],
        ["", Paragraph(datos_factura.get("descripcion", ""), style_normal), "1,00", "unidades",
         f"{importe:,.2f}", "0,00", "0,00", f"{importe:,.2f}"]
    ], colWidths=[15*mm, 60*mm, 15*mm, 18*mm, 20*mm, 13*mm, 18*mm, 21*mm])
    
    detalle_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('FONTSIZE', (0, 0), (-1, -1), 7),
    ]))
    story.append(detalle_table)
    story.append(Spacer(1, 50*mm))
    
    # TOTALES
    totales_table = Table([
        ["", "Subtotal: $", f"{importe:,.2f}"],
        ["", "Importe Otros Tributos: $", "0,00"],
        ["", "Importe Total: $", f"{importe:,.2f}"]
    ], colWidths=[95*mm, 40*mm, 35*mm])
    totales_table.setStyle(TableStyle([
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
        ('FONTNAME', (1, 0), (2, -1), 'Helvetica-Bold'),
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
    ]))
    story.append(totales_table)
    story.append(Spacer(1, 10*mm))
    
    # CAE Y QR
    qr_image = RLImage(qr_buffer, width=40*mm, height=40*mm)
    cae_table = Table([
        [qr_image,
         Paragraph(f"<para align=right>Pág. 1/1<br/><br/>"
                  f"<b>CAE N°: {datos_factura['cae']}</b><br/>"
                  f"<b>Fecha de Vto. de CAE: {vencimiento_cae}</b><br/><br/>"
                  f"<b>Comprobante Autorizado</b><br/>"
                  f"<font size=6>Esta Agencia no se responsabiliza por los datos ingresados en el detalle de la operación</font></para>",
                  style_normal)]
    ], colWidths=[50*mm, 120*mm])
    story.append(cae_table)
    
    doc.build(story)
    print(f"PDF generado exitosamente: {output_path}")
    return output_path
