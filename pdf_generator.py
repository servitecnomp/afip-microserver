"""
Generador de PDFs para facturas AFIP
Genera PDFs con formato oficial incluyendo código de barras
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfgen import canvas
from reportlab.graphics.barcode import code128
from reportlab.graphics.shapes import Drawing
from reportlab.graphics import renderPDF
import os
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
        "razon_social": "DEVRIES MARIA PAULA",  # Ajustar si es diferente
        "domicilio": "Rodriguez Peña 1789 - Mar Del Plata Sur, Buenos Aires",
        "cuit": "27461124149",
        "condicion_iva": "Responsable Monotributo",
        "ingresos_brutos": "27461124149",
        "inicio_actividades": "01/01/2021"
    }
}

# Mapeo de compañías de seguros
COMPANIAS = {
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

def generar_codigo_barras(cuit_emisor, tipo_cbte, punto_venta, cae, vencimiento_cae):
    """
    Genera el código de barras según especificaciones AFIP
    Formato: CUIT (11) + Tipo Cbte (2) + PtoVta (4) + CAE (14) + Vto (8)
    """
    # Limpiar CUIT
    cuit_limpio = cuit_emisor.replace("-", "").replace(" ", "")
    
    # Formatear cada componente
    tipo_cbte_str = str(tipo_cbte).zfill(2)
    pto_vta_str = str(punto_venta).zfill(4)
    cae_str = str(cae)
    vto_str = vencimiento_cae.replace("/", "").replace("-", "")  # AAAAMMDD
    
    # Construir código
    codigo = f"{cuit_limpio}{tipo_cbte_str}{pto_vta_str}{cae_str}{vto_str}"
    
    return codigo

def crear_pdf_factura(datos_factura, logo_path, output_path):
    """
    Crea un PDF de factura con formato AFIP oficial
    
    Parámetros:
    - datos_factura: dict con todos los datos de la factura
    - logo_path: ruta al archivo del logo
    - output_path: ruta donde guardar el PDF
    """
    
    # Extraer datos
    cuit_emisor = str(datos_factura["cuit_emisor"]).replace("-", "").replace(" ", "")
    cuit_receptor = str(datos_factura["cuit_receptor"]).replace("-", "").replace(" ", "")
    punto_venta = datos_factura["punto_venta"]
    tipo_cbte = datos_factura["tipo_cbte"]
    cbte_nro = datos_factura["cbte_nro"]
    fecha_emision = datos_factura["fecha_emision"]
    cae = datos_factura["cae"]
    vencimiento_cae = datos_factura["vencimiento_cae"]
    importe = datos_factura["importe"]
    descripcion = datos_factura.get("descripcion", "")
    
    # Obtener datos del emisor
    emisor = EMISOR_DATA.get(cuit_emisor, EMISOR_DATA["27239676931"])
    
    # Obtener datos del receptor
    receptor = COMPANIAS.get(cuit_receptor, {
        "razon_social": "Cliente",
        "domicilio": "",
        "condicion_iva": "IVA Responsable Inscripto"
    })
    
    # Crear documento
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=20*mm,
        leftMargin=20*mm,
        topMargin=15*mm,
        bottomMargin=15*mm
    )
    
    # Estilos
    styles = getSampleStyleSheet()
    style_normal = ParagraphStyle(
        'Normal',
        parent=styles['Normal'],
        fontSize=8,
        leading=10
    )
    style_bold = ParagraphStyle(
        'Bold',
        parent=styles['Normal'],
        fontSize=8,
        fontName='Helvetica-Bold',
        leading=10
    )
    style_titulo = ParagraphStyle(
        'Titulo',
        parent=styles['Normal'],
        fontSize=10,
        fontName='Helvetica-Bold',
        alignment=TA_CENTER
    )
    
    # Contenido
    story = []
    
    # === ENCABEZADO "ORIGINAL" ===
    encabezado_table = Table(
        [["ORIGINAL"]],
        colWidths=[170*mm]
    )
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
    
    # === BLOQUE SUPERIOR: Emisor + Tipo + Factura ===
    
    # Columna izquierda: Logo y datos del emisor
    if os.path.exists(logo_path):
        logo = Image(logo_path, width=25*mm, height=25*mm)
    else:
        logo = Paragraph("", style_normal)
    
    datos_emisor = [
        [Paragraph(f"<b>{emisor['razon_social']}</b>", style_bold)],
        [Paragraph(f"<b>Razón Social:</b> {emisor['razon_social']}", style_normal)],
        [Paragraph(f"<b>Domicilio Comercial:</b> {emisor['domicilio']}", style_normal)],
        [Paragraph(f"<b>Condición frente al IVA:</b> {emisor['condicion_iva']}", style_normal)]
    ]
    
    table_emisor = Table(datos_emisor, colWidths=[80*mm])
    table_emisor.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    
    # Columna centro: Tipo de comprobante (C)
    tipo_c = Table(
        [[Paragraph("<b>C</b>", style_titulo)], [Paragraph("COD. 011", style_normal)]],
        colWidths=[20*mm],
        rowHeights=[15*mm, 5*mm]
    )
    tipo_c.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (0, 0), 'MIDDLE'),
        ('BOX', (0, 0), (-1, -1), 2, colors.black),
        ('FONTSIZE', (0, 0), (0, 0), 24),
        ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
    ]))
    
    # Columna derecha: Datos de la factura
    punto_venta_str = str(punto_venta).zfill(5)
    cbte_nro_str = str(cbte_nro).zfill(8)
    
    datos_factura_derecha = [
        [Paragraph("<b>FACTURA</b>", style_titulo)],
        [Paragraph(f"<b>Punto de Venta:</b> {punto_venta_str}  <b>Comp. Nro:</b> {cbte_nro_str}", style_normal)],
        [Paragraph(f"<b>Fecha de Emisión:</b> {fecha_emision}", style_normal)],
        [Paragraph(f"<b>CUIT:</b> {cuit_emisor}", style_normal)],
        [Paragraph(f"<b>Ingresos Brutos:</b> {emisor['ingresos_brutos']}", style_normal)],
        [Paragraph(f"<b>Fecha de Inicio de Actividades:</b> {emisor['inicio_actividades']}", style_normal)]
    ]
    
    table_factura = Table(datos_factura_derecha, colWidths=[65*mm])
    table_factura.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    
    # Combinar las tres columnas
    bloque_superior = Table(
        [[logo, "", tipo_c, "", table_factura]],
        colWidths=[25*mm, 3*mm, 20*mm, 3*mm, 119*mm]
    )
    bloque_superior.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (2, 0), (2, 0), 'CENTER'),
        ('ALIGN', (4, 0), (4, 0), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    
    story.append(bloque_superior)
    story.append(Spacer(1, 2*mm))
    
    # === PERÍODO FACTURADO ===
    periodo_data = [[
        Paragraph(f"<b>Período Facturado Desde:</b> {fecha_emision}", style_normal),
        Paragraph(f"<b>Hasta:</b> {fecha_emision}", style_normal),
        Paragraph(f"<b>Fecha de Vto. para el pago:</b> {fecha_emision}", style_normal)
    ]]
    
    periodo_table = Table(periodo_data, colWidths=[57*mm, 57*mm, 56*mm])
    periodo_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    
    story.append(periodo_table)
    story.append(Spacer(1, 2*mm))
    
    # === DATOS DEL RECEPTOR ===
    receptor_data = [
        [
            Paragraph(f"<b>CUIT:</b> {cuit_receptor}", style_normal),
            Paragraph(f"<b>Apellido y Nombre / Razón Social:</b> {receptor['razon_social']}", style_normal)
        ],
        [
            Paragraph(f"<b>Condición frente al IVA:</b> {receptor['condicion_iva']}", style_normal),
            Paragraph(f"<b>Domicilio:</b> {receptor['domicilio']}", style_normal)
        ],
        [
            Paragraph(f"<b>Condición de venta:</b> Otra", style_normal),
            Paragraph("", style_normal)
        ]
    ]
    
    receptor_table = Table(receptor_data, colWidths=[85*mm, 85*mm])
    receptor_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    
    story.append(receptor_table)
    story.append(Spacer(1, 5*mm))
    
    # === DETALLE DEL COMPROBANTE ===
    detalle_headers = [
        Paragraph("<b>Código</b>", style_bold),
        Paragraph("<b>Producto / Servicio</b>", style_bold),
        Paragraph("<b>Cantidad</b>", style_bold),
        Paragraph("<b>U. Medida</b>", style_bold),
        Paragraph("<b>Precio Unit.</b>", style_bold),
        Paragraph("<b>% Bonif</b>", style_bold),
        Paragraph("<b>Imp. Bonif.</b>", style_bold),
        Paragraph("<b>Subtotal</b>", style_bold)
    ]
    
    detalle_row = [
        Paragraph("", style_normal),
        Paragraph(descripcion, style_normal),
        Paragraph("1,00", style_normal),
        Paragraph("unidades", style_normal),
        Paragraph(f"{importe:,.2f}", style_normal),
        Paragraph("0,00", style_normal),
        Paragraph("0,00", style_normal),
        Paragraph(f"{importe:,.2f}", style_normal)
    ]
    
    detalle_table = Table(
        [detalle_headers, detalle_row],
        colWidths=[15*mm, 60*mm, 15*mm, 18*mm, 20*mm, 13*mm, 18*mm, 21*mm]
    )
    detalle_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 7),
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    
    story.append(detalle_table)
    story.append(Spacer(1, 50*mm))
    
    # === TOTALES ===
    totales_data = [
        ["", "Subtotal: $", f"{importe:,.2f}"],
        ["", "Importe Otros Tributos: $", "0,00"],
        ["", "Importe Total: $", f"{importe:,.2f}"]
    ]
    
    totales_table = Table(totales_data, colWidths=[95*mm, 40*mm, 35*mm])
    totales_table.setStyle(TableStyle([
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
        ('FONTNAME', (1, 0), (2, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    
    story.append(totales_table)
    story.append(Spacer(1, 10*mm))
    
    # === CAE Y CÓDIGO DE BARRAS ===
    codigo_barras_str = generar_codigo_barras(
        cuit_emisor, tipo_cbte, punto_venta, cae, vencimiento_cae
    )
    
    # Crear código de barras
    barcode = code128.Code128(codigo_barras_str, barHeight=15*mm, barWidth=0.8)
    
    # Datos CAE
    cae_data = [
        [
            "",
            Paragraph(f"<b>CAE N°:</b> {cae}", style_bold),
            Paragraph(f"<b>Fecha de Vto. de CAE:</b> {vencimiento_cae}", style_bold)
        ],
        [
            barcode,
            Paragraph("<b>Comprobante Autorizado</b>", style_bold),
            Paragraph("Esta Agencia no se responsabiliza por los datos ingresados en el detalle de la operación", 
                     ParagraphStyle('Small', parent=styles['Normal'], fontSize=6))
        ]
    ]
    
    cae_table = Table(cae_data, colWidths=[60*mm, 60*mm, 50*mm], rowHeights=[8*mm, 20*mm])
    cae_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('ALIGN', (1, 0), (2, 0), 'LEFT'),
        ('ALIGN', (1, 1), (1, 1), 'CENTER'),
        ('ALIGN', (2, 1), (2, 1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('SPAN', (0, 0), (0, 1)),
    ]))
    
    story.append(cae_table)
    
    # Generar PDF
    doc.build(story)
    
    print(f"PDF generado exitosamente: {output_path}")
    return output_path
