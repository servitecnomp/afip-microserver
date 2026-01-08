import os
import datetime
from flask import Flask, request, jsonify, send_from_directory
from zeep import Client
from zeep.transports import Transport
from requests import Session
from requests.adapters import HTTPAdapter
import ssl
from zeep.exceptions import Fault
from pdf_generator import crear_pdf_factura
from io import BytesIO
from pathlib import Path

app = Flask(__name__)

# ======================================================================
# CONFIGURACIÓN
# ======================================================================

# MODO = "HOMOLOGACION"  
# MODO = "HOMOLOGACION"  # Usar solo para pruebas
MODO = "PRODUCCION"      # ← Facturas reales con CAE válido ( SEGUN LO QUE PONGA ACA, EL PROGRRAMA HACE PRUEBAS SIN FACTURAR: HOMOLOGACION Y PRODUCCIO PARA FACTURAR

CUIT_1 = "27239676931"
CUIT_2 = "27461124149"

# Certificados
if MODO == "PRODUCCION":
    CERT_1 = "facturacion27239676931.crt"
    KEY_1 = "cuit_27239676931.key"
    CERT_2 = "facturacion27461124149.crt"
    KEY_2 = "cuit_27461124149.key"
    WSAA = "https://wsaa.afip.gov.ar/ws/services/LoginCms?wsdl"
    WSFE = "https://servicios1.afip.gov.ar/wsfev1/service.asmx?WSDL"
else:
    CERT_1 = "homologacion_27239676931.crt"
    KEY_1 = "homologacion_27239676931.key"
    CERT_2 = "homologacion_Meme.crt"
    KEY_2 = "homologacion_Meme.key"
    WSAA = "https://wsaahomo.afip.gov.ar/ws/services/LoginCms?wsdl"
    WSFE = "https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL"

# Directorio para PDFs
PDF_DIR = os.path.join(os.path.dirname(__file__), "pdfs")
os.makedirs(PDF_DIR, exist_ok=True)

# Logo - CON VERIFICACIÓN ROBUSTA
LOGO_PATH = None
try:
    logo_candidate = os.path.join(os.path.dirname(__file__), "logo.jpeg")
    print(f"DEBUG - Buscando logo en: {logo_candidate}")
    if os.path.exists(logo_candidate):
        LOGO_PATH = str(logo_candidate)
        print(f"✓ Logo encontrado: {LOGO_PATH}")
    else:
        print(f"⚠ Logo no encontrado en: {logo_candidate}")
except Exception as e:
    print(f"⚠ Error al configurar logo: {e}")

TOKEN_CACHE = {}

# ======================================================================
# ADAPTADOR SSL
# ======================================================================

class DESAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        context = ssl.create_default_context()
        context.set_ciphers('DEFAULT@SECLEVEL=1')
        kwargs['ssl_context'] = context
        return super().init_poolmanager(*args, **kwargs)

# ======================================================================
# AUTENTICACIÓN
# ======================================================================

def load_cert(cuit):
    if cuit == CUIT_1:
        return CERT_1, KEY_1
    elif cuit == CUIT_2:
        return CERT_2, KEY_2
    else:
        raise Exception(f"CUIT {cuit} no configurado")

def create_tra(service="wsfe"):
    now = datetime.datetime.utcnow()
    generation_time = now.strftime('%Y-%m-%dT%H:%M:%S.000-00:00')
    expiration_time = (now + datetime.timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M:%S.000-00:00')
    unique_id = int(now.timestamp())
    
    tra = f"""<?xml version="1.0" encoding="UTF-8"?>
<loginTicketRequest version="1.0">
  <header>
    <uniqueId>{unique_id}</uniqueId>
    <generationTime>{generation_time}</generationTime>
    <expirationTime>{expiration_time}</expirationTime>
  </header>
  <service>{service}</service>
</loginTicketRequest>"""
    return tra

def sign_tra(tra, cert_file, key_file):
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.serialization import pkcs7
    from cryptography.hazmat.backends import default_backend
    from cryptography import x509
    
    with open(cert_file, 'rb') as f:
        cert_data = f.read()
        cert = x509.load_pem_x509_certificate(cert_data, default_backend())
    
    with open(key_file, 'rb') as f:
        key_data = f.read()
        key = serialization.load_pem_private_key(key_data, password=None, backend=default_backend())
    
    options = [pkcs7.PKCS7Options.Binary]
    signed_data = pkcs7.PKCS7SignatureBuilder().set_data(
        tra.encode('utf-8')
    ).add_signer(
        cert, key, hashes.SHA256()
    ).sign(
        serialization.Encoding.DER, options
    )
    
    import base64
    return base64.b64encode(signed_data).decode('utf-8')

def get_cached_token(cuit, cert_file, key_file):
    if cuit in TOKEN_CACHE:
        cached = TOKEN_CACHE[cuit]
        expiration = cached.get("expiration")
        if expiration and expiration > datetime.datetime.utcnow() + datetime.timedelta(minutes=15):
            print(f"✓ Reutilizando token en caché para {cuit}")
            return cached["token"], cached["sign"]
    
    print(f"Generando nuevo token para {cuit}...")
    token, sign = get_token(cert_file, key_file)
    TOKEN_CACHE[cuit] = {
        "token": token,
        "sign": sign,
        "expiration": datetime.datetime.utcnow() + datetime.timedelta(hours=2)
    }
    print(f"✓ Token generado y almacenado en caché")
    return token, sign

def get_token(cert_file, key_file):
    try:
        tra = create_tra()
        cms = sign_tra(tra, cert_file, key_file)
        
        session = Session()
        session.mount('https://', DESAdapter())
        session.headers.update({'Content-Type': 'text/xml; charset=utf-8'})
        transport = Transport(session=session)
        client = Client(WSAA, transport=transport)
        
        response = client.service.loginCms(cms)
        print(f"DEBUG Response type: {type(response)}")
        
        try:
            token = response.credentials.token
            sign = response.credentials.sign
            print("✓ Token y Sign obtenidos exitosamente")
        except AttributeError:
            try:
                token = response['credentials']['token']
                sign = response['credentials']['sign']
                print("✓ Token y Sign obtenidos exitosamente (dict)")
            except (KeyError, TypeError):
                import xml.etree.ElementTree as ET
                response_str = str(response)
                root = ET.fromstring(response_str)
                token = None
                sign = None
                for elem in root.iter():
                    tag_lower = elem.tag.lower()
                    if 'token' in tag_lower and elem.text:
                        token = elem.text
                    if 'sign' in tag_lower and elem.text:
                        sign = elem.text
                if not token or not sign:
                    raise Exception(f"No se pudo extraer token/sign")
                print("✓ Token y Sign obtenidos exitosamente (XML)")
        return token, sign
    except Fault as e:
        raise Exception(f"Error WSAA: {e.message}")
    except Exception as e:
        raise Exception(f"Error token: {str(e)}")

# ======================================================================
# FACTURACIÓN
# ======================================================================

def crear_factura(data):
    cuit_emisor = str(data["cuit_emisor"]).replace("-", "").replace(" ", "").strip()
    doc_receptor = str(data.get("doc_receptor") or data.get("cuit_receptor", "")).replace("-", "").replace(" ", "").strip()
    tipo_doc_receptor = int(data.get("tipo_doc_receptor", 80))
    punto_venta = int(data["punto_venta"])
    tipo_cbte = int(data["tipo_cbte"])
    importe = float(data["importe"])
    
    print(f"\n=== INICIANDO FACTURACIÓN ===")
    print(f"MODO: {MODO}")
    print(f"CUIT Emisor: {cuit_emisor}")
    print(f"Doc Receptor: {doc_receptor} (Tipo: {tipo_doc_receptor})")
    print(f"Punto Venta: {punto_venta}")
    print(f"Tipo Comprobante: {tipo_cbte}")
    print(f"Importe: {importe}")

    cert_file, key_file = load_cert(cuit_emisor)
    print(f"Certificado: {cert_file}")

    print("\n1. Obteniendo token AFIP...")
    token, sign = get_cached_token(cuit_emisor, cert_file, key_file)

    print("2. Conectando a WSFE...")
    session = Session()
    session.mount('https://', DESAdapter())
    session.headers.update({'Content-Type': 'text/xml; charset=utf-8'})
    transport = Transport(session=session)
    client = Client(WSFE, transport=transport)

    print(f"3. Consultando último comprobante (PtoVta: {punto_venta}, Tipo: {tipo_cbte})...")
    try:
        ultimo = client.service.FECompUltimoAutorizado(
            Auth={'Token': token, 'Sign': sign, 'Cuit': int(cuit_emisor)},
            PtoVta=punto_venta,
            CbteTipo=tipo_cbte
        )
        cbte_nro = ultimo.CbteNro + 1
        print(f"✓ Último comprobante: {ultimo.CbteNro}, Próximo: {cbte_nro}")
    except Exception as e:
        print(f"✗ Error en último comprobante: {str(e)}")
        raise

    print("4. Preparando comprobante...")
    fecha = int(datetime.datetime.now().strftime("%Y%m%d"))
    
    if 'condicion_iva_receptor' in data and data['condicion_iva_receptor']:
        condicion_iva_receptor = int(data['condicion_iva_receptor'])
    else:
        condicion_iva_receptor = 5 if tipo_doc_receptor == 96 else 1
    
    print(f"Condición IVA Receptor: {condicion_iva_receptor}")
    
    FeCabReq = {'CantReg': 1, 'PtoVta': punto_venta, 'CbteTipo': tipo_cbte}
    FeDetReq = {
        'Concepto': 1,
        'DocTipo': tipo_doc_receptor,
        'DocNro': int(doc_receptor),
        'CbteDesde': cbte_nro,
        'CbteHasta': cbte_nro,
        'CbteFch': fecha,
        'ImpTotal': round(importe, 2),
        'ImpTotConc': 0.00,
        'ImpNeto': round(importe, 2),
        'ImpOpEx': 0.00,
        'ImpIVA': 0.00,
        'ImpTrib': 0.00,
        'MonId': 'PES',
        'MonCotiz': 1.00,
        'CondicionIVAReceptorId': condicion_iva_receptor
    }
    
    if tipo_cbte == 13:
        cbte_asoc_tipo = int(data.get("cbte_asoc_tipo", 11))
        cbte_asoc_pto_vta = int(data.get("cbte_asoc_pto_vta", punto_venta))
        cbte_asoc_nro = int(data.get("cbte_asoc_nro"))
        FeDetReq['CbtesAsoc'] = {
            'CbteAsoc': [{'Tipo': cbte_asoc_tipo, 'PtoVta': cbte_asoc_pto_vta, 'Nro': cbte_asoc_nro}]
        }
        print(f"Nota de Crédito - Factura asociada:")
        print(f"  - Tipo: {cbte_asoc_tipo}")
        print(f"  - Punto Venta: {cbte_asoc_pto_vta}")
        print(f"  - Número: {cbte_asoc_nro}")
    
    FeCAEReq = {'FeCabReq': FeCabReq, 'FeDetReq': {'FECAEDetRequest': [FeDetReq]}}
    
    print(f"Comprobante preparado:")
    print(f"  - Fecha: {fecha}")
    print(f"  - Número: {cbte_nro}")
    print(f"  - Doc Receptor: {int(doc_receptor)}")
    print(f"  - Importe Total: {round(importe, 2)}")
    print(f"  - Condición IVA: {condicion_iva_receptor}")

    print("5. Solicitando CAE a AFIP...")
    try:
        resultado = client.service.FECAESolicitar(
            Auth={'Token': token, 'Sign': sign, 'Cuit': int(cuit_emisor)},
            FeCAEReq=FeCAEReq
        )
        print(f"Respuesta AFIP recibida")
        
        if hasattr(resultado, 'Errors') and resultado.Errors:
            error_msg = resultado.Errors.Err[0].Msg
            error_code = resultado.Errors.Err[0].Code
            print(f"✗ AFIP devolvió error {error_code}: {error_msg}")
            raise Exception(f"AFIP error {error_code}: {error_msg}")
        
        det_resp = resultado.FeDetResp.FECAEDetResponse[0]
        print(f"Resultado detallado:")
        print(f"  - Resultado: {det_resp.Resultado}")
        
        if hasattr(det_resp, 'Observaciones') and det_resp.Observaciones:
            for obs in det_resp.Observaciones.Obs:
                print(f"  - Observación {obs.Code}: {obs.Msg}")
        
        if det_resp.Resultado == 'A':
            cae = det_resp.CAE
            vencimiento = det_resp.CAEFchVto
            print(f"✓ CAE obtenido: {cae}")
            print(f"✓ Vencimiento: {vencimiento}")
            return {"cbte_nro": cbte_nro, "cae": cae, "vencimiento": vencimiento, "fecha": fecha}
        else:
            msg_obs = "Sin observaciones"
            if hasattr(det_resp, 'Observaciones') and det_resp.Observaciones:
                msg_obs = det_resp.Observaciones.Obs[0].Msg
            print(f"✗ Comprobante rechazado: {msg_obs}")
            raise Exception(f"Comprobante rechazado por AFIP: {msg_obs}")
    except Exception as e:
        print(f"✗ Error: {str(e)}")
        raise

# ======================================================================
# ENDPOINTS
# ======================================================================

@app.route("/facturar", methods=["POST"])
def facturar():
    try:
        data = request.json
        print(f"\n{'='*60}")
        print(f"NUEVA SOLICITUD DE FACTURACIÓN")
        print(f"{'='*60}")
        factura = crear_factura(data)
        
        print("Generando PDF...")
        print(f"DEBUG - Datos recibidos:")
        print(f"  compania: {data.get('compania', '')}")
        print(f"  domicilio: {data.get('domicilio', '')}")
        print(f"  condicion_iva: {data.get('condicion_iva', '')}")
        print(f"  nombre_asegurado: {data.get('nombre_asegurado', '')}")
        
        try:
            cuit_emisor = data.get("cuit_emisor")
            punto_venta = data.get("punto_venta", 2)
            cbte_nro = factura["cbte_nro"]
            tipo_cbte = data.get("tipo_cbte", 11)
            
            nombre_asegurado = data.get("nombre_asegurado", "")
            nombre_archivo = ""
            if nombre_asegurado:
                import unicodedata
                nombre_limpio = ''.join(c for c in unicodedata.normalize('NFD', nombre_asegurado) 
                                       if unicodedata.category(c) != 'Mn')
                nombre_limpio = ''.join(c if c.isalnum() else '' for c in nombre_limpio)
                nombre_archivo = f"_{nombre_limpio[:30]}"
            
            codigo_cbte = "011" if tipo_cbte == 11 else "013"
            pdf_filename = f"{cuit_emisor}_{codigo_cbte}_{punto_venta}_{cbte_nro}{nombre_archivo}.pdf"
            pdf_path = os.path.join(PDF_DIR, pdf_filename)
            
            # ASEGURAR QUE pdf_path ES STRING
            pdf_path = str(pdf_path)
            print(f"DEBUG - PDF path: {pdf_path} (tipo: {type(pdf_path)})")
            
            datos_pdf = {
                "cuit_emisor": cuit_emisor,
                "cuit_receptor": data.get("doc_receptor") or data.get("cuit_receptor", ""),
                "punto_venta": punto_venta,
                "tipo_cbte": tipo_cbte,
                "cbte_nro": cbte_nro,
                "fecha_emision": datetime.datetime.now(),
                "cae": factura["cae"],
                "vencimiento_cae": factura["vencimiento"],
                "importe": data.get("importe"),
                "descripcion": data.get("descripcion", ""),
                "compania": data.get("compania", ""),
                "domicilio": data.get("domicilio", ""),
                "condicion_iva": data.get("condicion_iva", "IVA Responsable Inscripto"),
                "nombre_asegurado": nombre_asegurado
            }
            
            if tipo_cbte == 13:
                datos_pdf["cbte_asoc_nro"] = data.get("cbte_asoc_nro", "")
                datos_pdf["cbte_asoc_pto_vta"] = data.get("cbte_asoc_pto_vta", punto_venta)
            
            # VERIFICAR LOGO
            logo_a_usar = None
            if LOGO_PATH:
                if isinstance(LOGO_PATH, (BytesIO, bytes)):
                    print(f"⚠ LOGO_PATH es {type(LOGO_PATH)}. Usando None.")
                else:
                    logo_a_usar = str(LOGO_PATH)
                    print(f"DEBUG - Logo: {logo_a_usar}")
            
            # GENERAR PDF
            print(f"DEBUG - Llamando a crear_pdf_factura...")
            print(f"  pdf_path: {pdf_path} (tipo: {type(pdf_path)})")
            print(f"  logo: {logo_a_usar} (tipo: {type(logo_a_usar)})")
            
            crear_pdf_factura(datos_pdf, logo_a_usar, pdf_path)
            
            if os.path.exists(pdf_path):
                pdf_url = f"https://afip-microserver-1.onrender.com/descargar_pdf/{pdf_filename}"
                factura["pdf_url"] = pdf_url
                print(f"✓ PDF generado: {pdf_filename}")
            else:
                print(f"✗ PDF no se creó")
        except Exception as e:
            print(f"⚠ Error generando PDF (factura OK): {str(e)}")
            import traceback
            traceback.print_exc()
        
        return jsonify({"status": "OK", "factura": factura})
    except Exception as e:
        print(f"\n{'='*60}")
        print(f"ERROR EN FACTURACIÓN: {str(e)}")
        print(f"{'='*60}\n")
        return jsonify({"status": "ERROR", "detalle": str(e)})

@app.route("/", methods=["GET"])
def home():
    return f"AFIP Microserver v6 - Modo: {MODO}"

@app.route("/descargar_pdf/<filename>", methods=["GET"])
def descargar_pdf(filename):
    try:
        return send_from_directory(PDF_DIR, filename, as_attachment=True)
    except Exception as e:
        return jsonify({"status": "ERROR", "detalle": f"PDF no encontrado: {str(e)}"}), 404

@app.route("/test", methods=["GET"])
def test():
    return jsonify({
        "status": "OK",
        "modo": MODO,
        "message": "Servidor funcionando correctamente",
        "cuits_configurados": [CUIT_1, CUIT_2],
        "tokens_en_cache": len(TOKEN_CACHE)
    })

@app.route("/limpiar_cache", methods=["POST"])
def limpiar_cache():
    global TOKEN_CACHE
    TOKEN_CACHE = {}
    return jsonify({"status": "OK", "message": "Caché de tokens limpiado"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
