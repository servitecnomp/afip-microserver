from flask import Flask, request, jsonify
from suds.client import Client
from suds import WebFault
from suds.sax.element import Element
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

    client = Client(WSAA)
    
    try:
        response = client.service.loginCms(cms)
        
        # Extraer token y sign
        try:
            token = response.credentials.token
            sign = response.credentials.sign
        except AttributeError:
            # Parseo manual si falla
            import xml.etree.ElementTree as ET
            response_xml = str(response)
            root = ET.fromstring(response_xml)
            
            token = None
            sign = None
            
            for elem in root.iter():
                if 'token' in elem.tag.lower():
                    token = elem.text
                if 'sign' in elem.tag.lower():
                    sign = elem.text
            
            if not token or not sign:
                raise Exception("No se pudo extraer token/sign")
        
        return token, sign

    except WebFault as e:
        raise Exception(f"Error WSAA: {e.fault.faultstring}")
    except Exception as e:
        raise Exception(f"Error token: {str(e)}")

def get_wsfe_client(token, sign, cuit_emisor):
    client = Client(WSFE)
    
    # Crear headers SOAP manualmente
    token_element = Element('Token').setText(token)
    sign_element = Element('Sign').setText(sign)
    cuit_element = Element('Cuit').setText(str(cuit_emisor))
    
    client.set_options(soapheaders=[token_element, sign_element, cuit_element])
    
    return client

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

    # 2) Cliente WSFE
    client = get_wsfe_client(token, sign, cuit_emisor)

    # 3) Último comprobante
    try:
        ultimo = client.service.FECompUltimoAutorizado(punto_venta, tipo_cbte)
        cbte_nro = ultimo.CbteNro + 1
    except WebFault as e:
        raise Exception(f"Error último comprobante: {e.fault.faultstring}")
    except Exception as e:
        raise Exception(f"Error último comprobante: {str(e)}")

    # 4) Preparar comprobante usando factory de SUDS
    factory = client.factory
    
    # Crear estructura usando los tipos del WSDL
    fe_cab_req = factory.create('FECAECabRequest')
    fe_cab_req.CantReg = 1
    fe_cab_req.PtoVta = punto_venta
    fe_cab_req.CbteTipo = tipo_cbte
    
    fe_det_req = factory.create('FECAEDetRequest')
    fe_det_req.Concepto = 1
    fe_det_req.DocTipo = 80
    fe_det_req.DocNro = int(cuit_receptor)
    fe_det_req.CbteDesde = cbte_nro
    fe_det_req.CbteHasta = cbte_nro
    fe_det_req.CbteFch = int(datetime.datetime.now().strftime("%Y%m%d"))
    fe_det_req.ImpTotal = round(importe, 2)
    fe_det_req.ImpTotConc = 0.00
    fe_det_req.ImpNeto = round(importe, 2)
    fe_det_req.ImpOpEx = 0.00
    fe_det_req.ImpIVA = 0.00
    fe_det_req.ImpTrib = 0.00
    fe_det_req.MonId = 'PES'
    fe_det_req.MonCotiz = 1.00
    
    fe_cae_req = factory.create('FECAERequest')
    fe_cae_req.FeCabReq = fe_cab_req
    fe_cae_req.FeDetReq = [fe_det_req]

    # 5) Solicitar CAE
    try:
        res = client.service.FECAESolicitar(fe_cae_req)
        
        if hasattr(res, 'Errors') and res.Errors:
            error_msg = res.Errors.Err[0].Msg if res.Errors.Err else "Error desconocido"
            raise Exception(f"AFIP error: {error_msg}")
        
        det = res.FeDetResp.FECAEDetResponse[0]
        
        if not det.CAE:
            if hasattr(det, 'Observaciones') and det.Observaciones:
                obs_msg = det.Observaciones.Obs[0].Msg
                raise Exception(f"AFIP rechazó: {obs_msg}")
            else:
                raise Exception("AFIP rechazó sin CAE")
        
        return {
            "cbte_nro": cbte_nro,
            "cae": det.CAE,
            "vencimiento": det.CAEFchVto,
        }
        
    except WebFault as e:
        raise Exception(f"Error CAE: {e.fault.faultstring}")
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
    return "AFIP Microserver v2 funcionando."

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
