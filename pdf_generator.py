import qrcode
import base64
import json
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfgen import canvas
import os

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

def crear_pdf_factura(datos, logo_path, output_path):
    """
    Genera un PDF de factura o nota de crédito.
    
    datos: diccionario con los datos del comprobante
    logo_path: ruta al logo
    output_path: donde guardar el PDF
    """
    
    # Extraer datos
    cuit_emisor = str(datos.get("cuit_emisor", ""))
    cuit_receptor = str(datos.get("cuit_receptor", ""))
    punto_venta = int(datos.get("punto_venta", 2))
    tipo_cbte = int(datos.get("tipo_cbte", 11))
    cbte_nro = int(datos.get("cbte_nro", 0))
    fecha_emision = datos.get("fecha_emision")
    cae = str(datos.get("cae", ""))
    vencimiento_cae_raw = datos.get("vencimiento_cae", "")
    importe = float(datos.get("importe", 0))
    descripcion = datos.get("descripcion", "")
    compania = datos.get("compania", "")
    domicilio = datos.get("domicilio", "")
    condicion_iva = datos.get("condicion_iva", "")
    nombre_asegurado = datos.get("nombre_asegurado", "")
    
    # Determinar si es NC
    es_nota_credito = (tipo_cbte == 13)
    
    # Formatear fecha de emisión
    if hasattr(fecha_emision, 'strftime'):
        fecha_emision = fecha_emision.strftime("%d/%m/%Y")
    
    # Formatear vencimiento CAE
    if vencimiento_cae_raw and len(str(vencimiento_cae_raw)) == 8:
        venc_str = str(vencimiento_cae_raw)
        vencimiento_cae = f"{venc_str[6:8]}/{venc_str[4:6]}/{venc_str[0:4]}"
    else:
        vencimiento_cae = str(vencimiento_cae_raw)
    
    # Obtener datos del emisor
    emisor_info = EMISOR_DATA.get(cuit_emisor, {})
    razon_social_emisor = emisor_info.get("razon_social", "")
    domicilio_emisor = emisor_info.get("domicilio", "")
    iibb_emisor = emisor_info.get("ingresos_brutos", "")
    inicio_actividades = emisor_info.get("inicio_actividades", "")
    condicion_iva_emisor = emisor_info.get("condicion_iva", "")
    
    # Crear PDF
    c = canvas.Canvas(output_path, pagesize=A4)
    width, height = A4
    margin = 20 * mm
    
    # ================================================================
    # ENCABEZADO
    # ================================================================
    
    # Logo (arriba izquierda)
    if os.path.exists(logo_path):
        try:
            c.drawImage(logo_path, margin, height - 40*mm, width=30*mm, height=30*mm, preserveAspectRatio=True, mask='auto')
        except:
            pass
    
    # Letra "C" en el centro (bajada 4mm)
    c.setFont("Helvetica-Bold", 40)
    letra_x = width / 2 - 10*mm
    letra_y = height - 32*mm
    
    # LÍNEA VERTICAL DIVISORIA
    linea_vertical_x = width / 2
    c.setStrokeColor(colors.black)
    c.setLineWidth(1.5)
    c.line(linea_vertical_x, height - 8*mm, linea_vertical_x, letra_y + 20*mm + 2*mm)
    c.line(linea_vertical_x, letra_y - 2*mm, linea_vertical_x, height - 79*mm)
    
    # Cuadro para la letra C
    c.setStrokeColor(colors.black)
    c.setLineWidth(1.5)
    c.rect(letra_x, letra_y, 20*mm, 20*mm)
    
    # Letra C
    c.drawCentredString(letra_x + 10*mm, letra_y + 5*mm, "C")
    
    # COD. 011 o 013
    codigo_cbte = "011" if not es_nota_credito else "013"
    c.setFont("Helvetica", 8)
    c.drawCentredString(letra_x + 10*mm, letra_y + 2*mm, f"COD. {codigo_cbte}")
    
    # FACTURA o NOTA DE CRÉDITO arriba
    titulo_cbte = "FACTURA" if not es_nota_credito else "NOTA DE CRÉDITO"
    c.setFont("Helvetica", 12 if not es_nota_credito else 10)
    c.drawCentredString(letra_x + 10*mm, letra_y + 22*mm, titulo_cbte)
    
    # ================================================================
    # DATOS DEL EMISOR (Izquierda)
    # ================================================================
    
    emisor_x = margin
    emisor_y = height - 45*mm
    
    c.setFont("Helvetica-Bold", 10)
    c.drawString(emisor_x, emisor_y, razon_social_emisor)
    
    emisor_y -= 5*mm
    c.setFont("Helvetica", 9)
    c.drawString(emisor_x, emisor_y, domicilio_emisor)
    
    emisor_y -= 5*mm
    c.drawString(emisor_x, emisor_y, condicion_iva_emisor)
    
    # ================================================================
    # DATOS FISCALES (Derecha)
    # ================================================================
    
    fiscal_x = width / 2 + 5*mm
    fiscal_y = height - 45*mm
    
    c.setFont("Helvetica", 9)
    c.drawString(fiscal_x, fiscal_y, f"Punto de Venta: {str(punto_venta).zfill(4)}  Comp. Nro: {str(cbte_nro).zfill(8)}")
    
    fiscal_y -= 5*mm
    c.drawString(fiscal_x, fiscal_y, f"Fecha de Emisión: {fecha_emision}")
    
    fiscal_y -= 5*mm
    c.drawString(fiscal_x, fiscal_y, f"CUIT: {cuit_emisor}")
    
    fiscal_y -= 5*mm
    c.drawString(fiscal_x, fiscal_y, f"Ingresos Brutos: {iibb_emisor}")
    
    fiscal_y -= 5*mm
    c.drawString(fiscal_x, fiscal_y, f"Fecha de Inicio de Actividades: {inicio_actividades}")
    
    # ================================================================
    # SEPARADOR
    # ================================================================
    
    separador_y_pos = height - 79*mm
    c.setStrokeColor(colors.black)
    c.setLineWidth(1.5)
    c.line(margin, separador_y_pos, width - margin, separador_y_pos)
    
    # ================================================================
    # DATOS DEL RECEPTOR
    # ================================================================
    
    receptor_y = separador_y_pos - 10*mm
    
    # Si es NC, mostrar "ANULA FACTURA" en rojo
    if es_nota_credito:
        cbte_asoc_nro = datos.get("cbte_asoc_nro", "")
        cbte_asoc_pto_vta = datos.get("cbte_asoc_pto_vta", punto_venta)
        c.setFont("Helvetica-Bold", 9)
        c.setFillColor(colors.red)
        c.drawString(margin, receptor_y, f"ANULA FACTURA Nº {str(cbte_asoc_pto_vta).zfill(4)}-{str(cbte_asoc_nro).zfill(8)}")
        receptor_y -= 7*mm
        c.setFillColor(colors.black)
    
    c.setFont("Helvetica-Bold", 9)
    c.drawString(margin, receptor_y, "DATOS DEL RECEPTOR")
    
    receptor_y -= 6*mm
    c.setFont("Helvetica", 9)
    c.drawString(margin, receptor_y, f"Razón Social: {compania}")
    
    receptor_y -= 5*mm
    c.drawString(margin, receptor_y, f"Domicilio: {domicilio}")
    
    receptor_y -= 5*mm
    c.drawString(margin, receptor_y, f"CUIT: {cuit_receptor}")
    
    receptor_y -= 5*mm
    c.drawString(margin, receptor_y, f"Condición IVA: {condicion_iva}")
    
    if nombre_asegurado:
        receptor_y -= 5*mm
        c.setFont("Helvetica-Bold", 9)
        c.drawString(margin, receptor_y, f"Asegurado: {nombre_asegurado}")
    
    # ================================================================
    # DETALLE
    # ================================================================
    
    detalle_y = receptor_y - 12*mm
    
    c.setFont("Helvetica-Bold", 9)
    c.drawString(margin, detalle_y, "DETALLE")
    
    detalle_y -= 6*mm
    c.setFont("Helvetica", 9)
    c.drawString(margin, detalle_y, descripcion)
    
    # ================================================================
    # TOTALES
    # ================================================================
    
    totales_y = 100*mm
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
    # CÓDIGO QR
    # ================================================================
    
    qr_data = {
        "ver": 1,
        "fecha": fecha_emision.replace("/", ""),
        "cuit": int(cuit_emisor),
        "ptoVta": int(punto_venta),
        "tipoCmp": tipo_cbte,
        "nroCmp": int(cbte_nro),
        "importe": importe,
        "moneda": "PES",
        "ctz": 1,
        "tipoDocRec": 96 if len(cuit_receptor) <= 8 else 80,
        "nroDocRec": int(cuit_receptor) if cuit_receptor else 0,
        "tipoCodAut": "E",
        "codAut": int(cae) if cae else 0
    }
    
    qr_json = json.dumps(qr_data, separators=(',', ':'))
    qr_url = f"https://www.afip.gob.ar/fe/qr/?p={qr_json}"
    
    # Generar código QR
    qr = qrcode.QRCode(version=1, box_size=3, border=1)
    qr.add_data(qr_url)
    qr.make(fit=True)
    
    qr_img = qr.make_image(fill_color="black", back_color="white")
    
    # Convertir a BytesIO
    buffer = BytesIO()
    qr_img.save(buffer, format='PNG')
    buffer.seek(0)
    
    # Dibujar QR en el PDF
    qr_x = margin
    qr_y = 30*mm
    c.drawImage(buffer, qr_x, qr_y, width=35*mm, height=35*mm)
    
    # ================================================================
    # CAE y AUTORIZACIÓN
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
    c.drawString(info_x, info_y, "datos contenidos en la presente factura.")
    
    # Guardar PDF
    c.save()
    
    print(f"PDF generado exitosamente: {output_path}")
