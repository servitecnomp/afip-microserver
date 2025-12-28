from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
import qrcode
from io import BytesIO
import os

def crear_pdf_factura(datos, logo_path, output_path):
    """
    Genera un PDF de factura con diseño profesional según modelos AFIP
    """
    
    # Configuración de página
    c = canvas.Canvas(output_path, pagesize=A4)
    width, height = A4
    
    # Márgenes
    margin = 15 * mm
    
    # ================================================================
    # ENCABEZADO
    # ================================================================
    
    # Logo (arriba izquierda - más pequeño)
    if os.path.exists(logo_path):
        try:
            c.drawImage(logo_path, margin, height - 40*mm, width=30*mm, height=30*mm, preserveAspectRatio=True, mask='auto')
        except:
            pass
    
    # Letra "C" en el centro (más pequeña)
    c.setFont("Helvetica-Bold", 40)
    letra_x = width / 2 - 10*mm
    letra_y = height - 28*mm
    
    # LÍNEA VERTICAL DIVISORIA (cortada para no atravesar la C)
    linea_vertical_x = width / 2
    c.setStrokeColor(colors.black)
    c.setLineWidth(1.5)
    # Línea superior (hasta arriba del cuadrado)
    c.line(linea_vertical_x, height - 10*mm, linea_vertical_x, letra_y + 20*mm + 2*mm)
    # Línea inferior (desde abajo del cuadrado)
    c.line(linea_vertical_x, letra_y - 2*mm, linea_vertical_x, height - 75*mm)
    
    # Cuadro para la letra C (más pequeño)
    c.setStrokeColor(colors.black)
    c.setLineWidth(1.5)
    c.rect(letra_x, letra_y, 20*mm, 20*mm)
    
    # Letra C
    c.drawCentredString(letra_x + 10*mm, letra_y + 5*mm, "C")
    
    # COD. 011 debajo de la letra
    c.setFont("Helvetica", 8)
    c.drawCentredString(letra_x + 10*mm, letra_y + 2*mm, "COD. 011")
    
    # FACTURA arriba de la letra
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(letra_x + 10*mm, letra_y + 22*mm, "FACTURA")
    
    # ORIGINAL en la parte superior
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(width / 2, height - 8*mm, "ORIGINAL")
    
    # ================================================================
    # DATOS DEL EMISOR (Izquierda de la línea vertical)
    # ================================================================
    
    emisor_x = margin
    emisor_y = height - 48*mm
    max_ancho_izq = (width / 2) - margin - 5*mm  # Limitar al ancho de la mitad izquierda
    
    # Determinar datos del emisor
    emisor_data = {
        "27239676931": {
            "razon_social": "DEVRIES MARIA PAULA",
            "domicilio": "Rodriguez Peña 1789 - Mar Del Plata Sur, Buenos Aires",
            "condicion_iva": "Responsable Monotributo",
            "ingresos_brutos": "27239676931",
            "inicio_actividades": "01/01/2021"
        },
        "27461124149": {
            "razon_social": "CACCIATO MARIA MERCEDES",
            "domicilio": "General Paz 4662 - Mar Del Plata Sur, Buenos Aires",
            "condicion_iva": "Responsable Monotributo",
            "ingresos_brutos": "27461124149",
            "inicio_actividades": "01/12/2023"
        }
    }
    
    cuit_emisor = str(datos.get("cuit_emisor", "")).replace("-", "").strip()
    emisor = emisor_data.get(cuit_emisor, emisor_data["27239676931"])
    
    c.setFont("Helvetica-Bold", 10)
    c.drawString(emisor_x, emisor_y, f"Razón Social: {emisor['razon_social']}")
    
    c.setFont("Helvetica", 9)
    emisor_y -= 4*mm
    
    # Domicilio con ajuste de texto para que no se pase de la línea
    domicilio_texto = f"Domicilio Comercial: {emisor['domicilio']}"
    ancho_maximo = (width / 2) - margin - 7*mm  # Dejar margen antes de la línea vertical
    
    # Usar textObject para manejar el texto largo
    texto_obj = c.beginText(emisor_x, emisor_y)
    texto_obj.setFont("Helvetica", 9)
    
    # Dividir el texto si es muy largo
    palabras = domicilio_texto.split()
    linea_actual = ""
    
    for palabra in palabras:
        linea_prueba = linea_actual + " " + palabra if linea_actual else palabra
        ancho_linea = c.stringWidth(linea_prueba, "Helvetica", 9)
        
        if ancho_linea <= ancho_maximo:
            linea_actual = linea_prueba
        else:
            texto_obj.textLine(linea_actual)
            linea_actual = palabra
            emisor_y -= 4*mm
    
    if linea_actual:
        texto_obj.textLine(linea_actual)
    
    c.drawText(texto_obj)
    emisor_y -= 4*mm
    
    c.drawString(emisor_x, emisor_y, f"Condición frente al IVA: {emisor['condicion_iva']}")
    
    # ================================================================
    # DATOS FISCALES DEL EMISOR (Derecha de la línea vertical)
    # ================================================================
    
    fiscal_x = width / 2 + 5*mm  # Justo después de la línea vertical
    fiscal_y = height - 48*mm
    
    # Formatear punto de venta y número sin tantos ceros
    punto_venta_raw = datos.get("punto_venta", 2)
    cbte_nro_raw = datos.get("cbte_nro", 1)
    punto_venta = str(punto_venta_raw).zfill(4)  # 4 dígitos en lugar de 5
    cbte_nro = str(cbte_nro_raw).zfill(8)  # Mantener 8 para el número
    fecha_emision = datos.get("fecha_emision").strftime("%d/%m/%Y") if hasattr(datos.get("fecha_emision"), 'strftime') else "28/12/2025"
    
    c.setFont("Helvetica", 9)
    c.drawString(fiscal_x, fiscal_y, f"Punto de Venta: {punto_venta}  Comp. Nro: {cbte_nro}")
    
    fiscal_y -= 4*mm
    c.drawString(fiscal_x, fiscal_y, f"Fecha de Emisión: {fecha_emision}")
    
    fiscal_y -= 5*mm
    c.setFont("Helvetica-Bold", 9)
    c.drawString(fiscal_x, fiscal_y, f"CUIT: {cuit_emisor}")
    
    c.setFont("Helvetica", 9)
    fiscal_y -= 4*mm
    c.drawString(fiscal_x, fiscal_y, f"Ingresos Brutos: {emisor['ingresos_brutos']}")
    
    fiscal_y -= 4*mm
    c.drawString(fiscal_x, fiscal_y, f"Fecha de Inicio de Actividades: {emisor['inicio_actividades']}")
    
    # Línea separadora
    separador_y = height - 75*mm
    c.setStrokeColor(colors.black)
    c.setLineWidth(0.5)
    c.line(margin, separador_y, width - margin, separador_y)
    
    # ================================================================
    # PERÍODO FACTURADO
    # ================================================================
    
    periodo_y = separador_y - 5*mm
    c.setFont("Helvetica", 8)
    c.drawString(margin, periodo_y, f"Período Facturado Desde: {fecha_emision}  Hasta: {fecha_emision}  Fecha de Vto. para el pago: {fecha_emision}")
    
    # ================================================================
    # DATOS DEL RECEPTOR
    # ================================================================
    
    receptor_y = periodo_y - 8*mm
    
    # Determinar si es DNI o CUIT
    doc_receptor = str(datos.get("cuit_receptor", "")).replace("-", "").strip()
    if len(doc_receptor) <= 8:
        tipo_doc = "DNI"
    else:
        tipo_doc = "CUIT"
    
    c.setFont("Helvetica-Bold", 9)
    c.drawString(margin, receptor_y, f"{tipo_doc}: {doc_receptor}")
    
    receptor_y -= 4*mm
    c.setFont("Helvetica", 9)
    nombre_receptor = datos.get("compania", "")
    c.drawString(margin, receptor_y, f"Apellido y Nombre / Razón Social: {nombre_receptor}")
    
    receptor_y -= 4*mm
    condicion_iva_texto = datos.get("condicion_iva", "Consumidor Final")
    c.drawString(margin, receptor_y, f"Condición frente al IVA: {condicion_iva_texto}")
    
    receptor_y -= 4*mm
    domicilio_receptor = datos.get("domicilio", "")
    c.drawString(margin, receptor_y, f"Domicilio: {domicilio_receptor}")
    
    receptor_y -= 4*mm
    c.drawString(margin, receptor_y, "Condición de venta: Contado")
    
    # Línea separadora
    separador2_y = receptor_y - 3*mm
    c.line(margin, separador2_y, width - margin, separador2_y)
    
    # ================================================================
    # TABLA DE PRODUCTOS/SERVICIOS
    # ================================================================
    
    tabla_y = separador2_y - 5*mm
    
    # Encabezados de tabla
    headers = ["Código", "Producto / Servicio", "Cantidad", "U. Medida", "Precio Unit.", "% Bonif", "Imp. Bonif.", "Subtotal"]
    
    # Datos
    descripcion_texto = datos.get("descripcion", "Servicio")
    importe = float(datos.get("importe", 0))
    
    # Crear Paragraph para la descripción con word wrap
    estilo_descripcion = ParagraphStyle(
        'Descripcion',
        fontName='Helvetica',
        fontSize=8,
        leading=10,
        alignment=TA_LEFT
    )
    descripcion_paragraph = Paragraph(descripcion_texto, estilo_descripcion)
    
    data = [
        headers,
        ["", descripcion_paragraph, "1,00", "unidades", f"{importe:,.2f}", "0,00", "0,00", f"{importe:,.2f}"]
    ]
    
    # Crear tabla con columna de descripción más ancha
    tabla = Table(data, colWidths=[15*mm, 80*mm, 15*mm, 15*mm, 18*mm, 12*mm, 15*mm, 18*mm])
    
    tabla.setStyle(TableStyle([
        ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 8),
        ('FONT', (0, 1), (-1, -1), 'Helvetica', 8),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (1, 1), (1, -1), 'LEFT'),  # Descripción alineada a la izquierda
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),  # Alineación vertical arriba
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('WORDWRAP', (1, 1), (1, -1)),  # Word wrap en la columna de descripción
        ('ROWHEIGHT', (0, 1), (-1, -1), None),  # Altura automática según contenido
    ]))
    
    tabla.wrapOn(c, width, height)
    tabla_height = tabla._height
    tabla.drawOn(c, margin, tabla_y - tabla_height)
    
    # ================================================================
    # TOTALES
    # ================================================================
    
    totales_y = tabla_y - tabla_height - 8*mm
    totales_x = width - margin - 50*mm
    
    c.setFont("Helvetica-Bold", 10)
    c.drawRightString(totales_x, totales_y, "Subtotal: $")
    c.drawRightString(width - margin, totales_y, f"{importe:,.2f}")
    
    totales_y -= 5*mm
    c.drawRightString(totales_x, totales_y, "Importe Otros Tributos: $")
    c.drawRightString(width - margin, totales_y, "0,00")
    
    totales_y -= 5*mm
    c.setFont("Helvetica-Bold", 12)
    c.drawRightString(totales_x, totales_y, "Importe Total: $")
    c.drawRightString(width - margin, totales_y, f"{importe:,.2f}")
    
    # ================================================================
    # CÓDIGO QR (Abajo izquierda)
    # ================================================================
    
    # Generar QR según Resolución 5198/2022
    cae = datos.get("cae", "")
    vencimiento_cae = datos.get("vencimiento_cae", "")
    tipo_cbte = datos.get("tipo_cbte", 11)
    
    # Formato: https://www.afip.gob.ar/fe/qr/?p=parametros
    qr_data = {
        "ver": 1,
        "fecha": fecha_emision.replace("/", ""),
        "cuit": int(cuit_emisor),
        "ptoVta": int(datos.get("punto_venta", 2)),
        "tipoCmp": tipo_cbte,
        "nroCmp": int(cbte_nro),
        "importe": importe,
        "moneda": "PES",
        "ctz": 1,
        "tipoDocRec": 96 if len(doc_receptor) <= 8 else 80,
        "nroDocRec": int(doc_receptor) if doc_receptor else 0,
        "tipoCodAut": "E",
        "codAut": int(cae) if cae else 0
    }
    
    # Convertir a JSON
    import json
    qr_json = json.dumps(qr_data, separators=(',', ':'))
    qr_url = f"https://www.afip.gob.ar/fe/qr/?p={qr_json}"
    
    # Generar código QR
    qr = qrcode.QRCode(version=1, box_size=3, border=1)
    qr.add_data(qr_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    
    # Guardar QR en buffer
    qr_buffer = BytesIO()
    qr_img.save(qr_buffer, format='PNG')
    qr_buffer.seek(0)
    
    # Dibujar QR
    qr_size = 35*mm
    qr_x = margin
    qr_y = 25*mm
    c.drawImage(ImageReader(qr_buffer), qr_x, qr_y, width=qr_size, height=qr_size)
    
    # ================================================================
    # CAE Y INFORMACIÓN FINAL (Abajo derecha)
    # ================================================================
    
    info_x = width - margin - 70*mm
    info_y = 55*mm
    
    c.setFont("Helvetica", 8)
    c.drawRightString(width - margin - 35*mm, info_y, "Pág. 1/1")
    
    info_y -= 8*mm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(info_x, info_y, f"CAE N°: {cae}")
    
    info_y -= 5*mm
    c.drawString(info_x, info_y, f"Fecha de Vto. de CAE: {vencimiento_cae}")
    
    info_y -= 8*mm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(info_x, info_y, "Comprobante Autorizado")
    
    info_y -= 5*mm
    c.setFont("Helvetica", 7)
    c.drawString(info_x, info_y, "Esta Agencia no se responsabiliza por los")
    info_y -= 3*mm
    c.drawString(info_x, info_y, "datos ingresados en el detalle de la operación")
    
    # ================================================================
    # FINALIZAR PDF
    # ================================================================
    
    c.showPage()
    c.save()
    
    return output_path
