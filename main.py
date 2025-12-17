from flask import Flask, request, jsonify
from zeep import Client
from zeep.transports import Transport
from zeep.exceptions import Fault
from requests import Session
import datetime
import os
import base64
import subprocess

app = Flask(__name__)

# ----------------------------------------------------------------------
# CONFIGURACIÓN CUITS Y CERTIFICADOS
# ----------------------------------------------------------------------

CUIT_1 = "27239676931"
CUIT_2 = "27461124149"

CERT_1 = "facturacion27239676931.crt"
KEY_1  = "cuit_27239676931.key"

CERT_2 = "facturacion27461124149.crt"
KEY_2  = "cuit_27461124149.key"

# ----------------------------------------------------------------------
# AFIP ENDPOINTS
# ----------------------------------------------------------------------

WSAA = "https://wsaa.afip.gov.ar/ws/services/LoginCms?wsdl"
WSFE = "https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL"

# ----------------------------------------------------------------------
# UTILIDADES
# ----------------------------------------------------------------------

def load_cert(cuit_emisor):
    if cuit_emisor == CUIT_1:
        return CERT_1, KEY_1
    elif cuit_emisor == CUIT_2:
        return CERT_2, KEY_2
    else:
        raise Exception("CUIT emisor sin certificado configurado")

def create_cms(tra_path, cert_file, key_file):
    cmd_list = [
        "openssl", "cms", "-sign", "-in", tra_path,
        "-signer", cert_file, "-inkey", key_file,
        "-nodetach", "-outform", "der"
    ]
    
    try:
        result = subprocess.run(cmd_list, capture_output=True, check=True)
        cms_bin = result.stdout
    except subprocess.CalledProcessError as e:
        error_message = e.stderr.decode('utf-8', errors='ignore')
        raise Exception(f"Error OpenSSL: {error_message}")

    cms_b64 = base64.b64encode(cms_bin).decode("ascii")
    return cms_b64

def get_token_sign(cert_file, key_file):
    now = datetime.datetime.utcnow()
    
    generation_time = now.strftime('%Y-%m-%dT%H:%M:%S.000-00:00')
    expiration_time = (now + datetime.timedelta(hours=12)).strftime('%Y-%m-%dT%H:%M:%S.000-00:00')

    tra = f"""<?xml version="1.0" encoding="UTF-8"?>
<loginTicketRequest version="1.0">
  <header>
    <uniqueId>{int(now.timestamp())}</uniqueId>
    <generationTime>{generation_time}</generationTime>
    <expirationTime>{expiration_time}</expirationTime>
  </header>
  <service>wsfe</service>
</loginTicketRequest>"""

    tra_path = os.path.join(os.getcwd(), "tra.xml")
    
    with open(tra_path, "w") as f:
        f.write(tra)

    cms = create_cms(tra_path, cert_file, key_file)
    
    os.remove(tra_path)

    session = Session()
    transport = Transport(session=session)
    client = Client(WSAA, transport=transport)
    
    try:
        response = client.service.loginCms(cms)
        # Zeep devuelve objetos, no diccionarios
        token = response.credentials.token
        sign = response.credentials.sign
        return token, sign
    except Fault as e:
        raise Exception(f"Error WSAA: {e.message}")
    except Exception as e:
        raise Exception(f"Error token: {str(e)}")

# ----------------------------------------------------------------------
# FACTURACIÓN
# ----------------------------------------------------------------------

def crear_factura(data):
    cuit_emisor   = str(data["cuit_emisor"])
    cuit_receptor = str(data["cuit_receptor"])
    punto_venta   = int(data["punto_venta"])
    tipo_cbte     = int(data["tipo_cbte"])
    importe       = float(data["importe"])

    cert_file, key_file = load_cert(cuit_emisor)

    # 1) Token AFIP
    token, sign = get_token_sign(cert_file, key_file)

    # 2) Cliente WSFE con headers
    session = Session()
    session.headers.update({
        'Content-Type': 'text/xml; charset=utf-8'
    })
    transport = Transport(session=session)
    client = Client(WSFE, transport=transport)

    # 3) Último comprobante
    try:
        ultimo = client.service.FECompUltimoAutorizado(
            Auth={'Token': token, 'Sign': sign, 'Cuit': int(cuit_emisor)},
            PtoVta=punto_venta,
            CbteTipo=tipo_cbte
        )
        cbte_nro = ultimo.CbteNro + 1
    except Fault as e:
        raise Exception(f"Error último comprobante: {e.message}")
    except Exception as e:
        raise Exception(f"Error último comprobante: {str(e)}")

    # 4) Preparar comprobante
    fecha = int(datetime.datetime.now().strftime("%Y%m%d"))
    
    FeCabReq = {
        'CantReg': 1,
        'PtoVta': punto_venta,
        'CbteTipo': tipo_cbte
    }
    
    FeDetReq = [{
        'Concepto': 1,
        'DocTipo': 80,
        'DocNro': int(cuit_receptor),
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
        'MonCotiz': 1.00
    }]

    # 5) Solicitar CAE
    try:
        resultado = client.service.FECAESolicitar(
            Auth={'Token': token, 'Sign': sign, 'Cuit': int(cuit_emisor)},
            FeCAEReq={'FeCabReq': FeCabReq, 'FeDetReq': FeDetReq}
        )
        
        # Verificar errores generales
        if hasattr(resultado, 'Errors') and resultado.Errors:
            error_msg = resultado.Errors.Err[0].Msg
            raise Exception(f"AFIP error: {error_msg}")
        
        # Obtener respuesta del detalle
        det_resp = resultado.FeDetResp.FECAEDetResponse[0]
        
        # Verificar si hay CAE
        if not det_resp.CAE:
            if hasattr(det_resp, 'Observaciones') and det_resp.Observaciones:
                obs_msg = det_resp.Observaciones.Obs[0].Msg
                raise Exception(f"AFIP rechazó: {obs_msg}")
            else:
                raise Exception("AFIP rechazó sin CAE ni observaciones")
        
        return {
            "cbte_nro": cbte_nro,
            "cae": det_resp.CAE,
            "vencimiento": det_resp.CAEFchVto,
        }
        
    except Fault as e:
        raise Exception(f"Error CAE: {e.message}")
    except Exception as e:
        if "AFIP" in str(e):
            raise
        raise Exception(f"Error CAE: {str(e)}")

# ----------------------------------------------------------------------
# ENDPOINTS
# ----------------------------------------------------------------------

@app.route("/facturar", methods=["POST"])
def facturar():
    try:
        data = request.json
        factura = crear_factura(data)
        return jsonify({"status": "OK", "factura": factura})
    except Exception as e:
        return jsonify({"status": "ERROR", "detalle": str(e)})

@app.route("/", methods=["GET"])
def home():
    return "AFIP Microserver v3 con Zeep funcionando."

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
