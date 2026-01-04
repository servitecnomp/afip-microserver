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
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import mm
    from reportlab.lib import colors

    c = canvas.Canvas(output_path, pagesize=A4)
    width, height = A4

    margen_x = 20
    margen_y = 20

    # =========================
    # CABECERA GENERAL
    # =========================

    c.setLineWidth(1)
    c.rect(margen_x, height - 60, width - 2 * margen_x, 40)
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(width / 2, height - 40, "ORIGINAL")

    # =========================
    # BLOQUE IZQUIERDO (EMISOR)
    # =========================

    c.rect(margen_x, height - 260, width / 2 - margen_x, 180)

    if logo_path:
        c.drawImage(logo_path, margen_x + 10, height - 120, width=80, preserveAspectRatio=True)

    c.setFont("Helvetica-Bold", 9)
    c.drawString(margen_x + 10, height - 135, "DEVRIES MARIA PAULA")

    c.setFont("Helvetica", 8)
    c.drawString(margen_x + 10, height - 150, "Razón Social: DEVRIES MARIA PAULA")
    c.drawString(margen_x + 10, height - 165, "Domicilio Comercial: Rodriguez Peña 1789 - Mar Del Plata Sur, Buenos Aires")
    c.drawString(margen_x + 10, height - 180, "Condición frente al IVA: Responsable Monotributo")

    # =========================
    # BLOQUE DERECHO (FACTURA)
    # =========================

    factura_x = width / 2
    factura_y = height - 260
    factura_width = width / 2 - margen_x
    factura_height = 180

    c.rect(factura_x, factura_y, factura_width, factura_height)

    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(factura_x + factura_width / 2, factura_y + factura_height - 20, "FACTURA")

    # Centro horizontal del bloque FACTURA
    factura_centro_x = factura_x + factura_width / 2

    # =========================
    # CUADRO LETRA C (CENTRADO)
    # =========================

    cuadro_size = 30
    c.rect(
        factura_centro_x - cuadro_size / 2,
        factura_y + factura_height - 70,
        cuadro_size,
        cuadro_size
    )

    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(
        factura_centro_x,
        factura_y + factura_height - 60,
        "C"
    )

    # =========================
    # TEXTO FACTURA
    # =========================

    c.setFont("Helvetica", 8)
    c.drawCentredString(
        factura_centro_x,
        factura_y + factura_height - 90,
        "Punto de Venta: 00002  Comp. Nro: 00000017"
    )

    c.drawCentredString(
        factura_centro_x,
        factura_y + factura_height - 105,
        "Fecha de Emisión: 04/01/2026"
    )

    # =========================
    # BLOQUE COD / CAE (CENTRADO)
    # =========================

    c.setFont("Helvetica-Bold", 8)
    c.drawCentredString(
        factura_centro_x,
        factura_y + factura_height - 125,
        "COD. 011"
    )

    c.setFont("Helvetica", 8)
    c.drawCentredString(
        factura_centro_x,
        factura_y + factura_height - 140,
        "CUIT: 2739676931"
    )

    c.drawCentredString(
        factura_centro_x,
        factura_y + factura_height - 155,
        "Ingresos Brutos: 2739676931"
    )

    c.drawCentredString(
        factura_centro_x,
        factura_y + factura_height - 170,
        "Fecha de Inicio de Actividades: 01/01/2021"
    )

    # =========================
    # PIE CLIENTE
    # =========================

    c.rect(margen_x, height - 330, width - 2 * margen_x, 60)

    c.setFont("Helvetica", 8)
    c.drawString(margen_x + 10, height - 350, "CUIT: 27308177")
    c.drawString(margen_x + 10, height - 365, "Apellido y Nombre / Razón Social: Marcos Cacciato")
    c.drawString(margen_x + 10, height - 380, "Condición frente al IVA: Consumidor Final")
    c.drawString(margen_x + 10, height - 395, "Domicilio:")
    c.drawString(margen_x + 10, height - 410, "Condición de venta: Otra")

    c.showPage()
    c.save()

    print(f"PDF generado exitosamente: {output_path}")

