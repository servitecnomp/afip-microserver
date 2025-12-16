from flask import Flask, request, jsonify
import datetime
import os
from pyafipws.wsaa import WSAA
from pyafipws.wsfev1 import WSFEv1

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

# HOMOLOGACIÓN
WSAA_URL = "https://wsaa.afip.gov.ar/ws/services/LoginCms?wsdl"
WSFEV1_URL = "https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL"

# PRODUCCIÓN (activar cuando esté todo OK)
# WSFEV1_URL = "https://servicios1.afip.gov.ar/wsfev1/service.asmx?WSDL"

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


def get_token_sign(cert_file, key_file, cuit):
    """Obtener token y sign de AFIP usando WSAA"""
    wsaa = WSAA()
    
    # Configurar certificado
    wsaa.Cuit = cuit
    wsaa.Certificado = cert_file
    wsaa.PrivateKey = key_file
    
    # Crear ticket de acceso
    tra = wsaa.CreateTRA(service="wsfe")
    cms = wsaa.SignTRA(tra, cert_file, key_file)
    
    # Llamar a WSAA
    wsaa.Conectar(wsdl=WSAA_URL)
    wsaa.LoginCMS(cms)
    
    if wsaa.Excepcion:
        raise Exception(f"Error WSAA: {wsaa.Excepcion}")
    
    return wsaa.Token, wsaa.Sign


def crear_factura(data):
    cuit_emisor   = str(data["cuit_emisor"])
    cuit_receptor = str(data["cuit_receptor"])
    punto_venta   = int(data["punto_venta"])
    tipo_cbte     = int(data["tipo_cbte"])
    importe       = float(data["importe"])

    cert_file, key_file = load_cert(cuit_emisor)

    # 1) Autenticación WSAA
    try:
        token, sign = get_token_sign(cert_file, key_file, cuit_emisor)
    except Exception as e:
        raise Exception(f"Error al obtener token AFIP: {str(e)}")

    # 2) Conectar a WSFEv1
    wsfe = WSFEv1()
    wsfe.Cuit = cuit_emisor
    wsfe.Token = token
    wsfe.Sign = sign
    
    cache_dir = ""  # No usar cache
    wsfe.Conectar(cache_dir, WSFEV1_URL)
    
    if wsfe.Excepcion:
        raise Exception(f"Error al conectar a WSFE: {wsfe.Excepcion}")

    # 3) Obtener último comprobante
    ultimo = wsfe.CompUltimoAutorizado(tipo_cbte, punto_venta)
    
    if wsfe.Excepcion:
        raise Exception(f"Error al obtener último comprobante: {wsfe.Excepcion}")
    
    cbte_nro = int(ultimo) + 1

    # 4) Crear comprobante
    fecha = datetime.datetime.now().strftime("%Y%m%d")
    
    # Crear factura
    wsfe.CrearFactura(
        concepto=1,              # Productos
        tipo_doc=80,             # CUIT
        nro_doc=int(cuit_receptor),
        tipo_cbte=tipo_cbte,
        punto_vta=punto_venta,
        cbt_desde=cbte_nro,
        cbt_hasta=cbte_nro,
        imp_total=importe,
        imp_tot_conc=0.00,       # Importe neto no gravado
        imp_neto=importe,        # Importe neto gravado
        imp_iva=0.00,            # Importe IVA
        imp_trib=0.00,           # Importe tributos
        imp_op_ex=0.00,          # Importe operaciones exentas
        fecha_cbte=fecha,
        fecha_venc_pago=None,
        fecha_serv_desde=None,
        fecha_serv_hasta=None,
        moneda_id="PES",
        moneda_ctz=1.000
    )

    # 5) Solicitar CAE
    wsfe.CAESolicitar()
    
    if wsfe.Excepcion:
        raise Exception(f"Error AFIP al solicitar CAE: {wsfe.Excepcion}. {wsfe.ErrMsg}")
    
    # Verificar errores/observaciones
    if wsfe.Resultado != "A":  # A = Aprobado
        obs = wsfe.Obs or "Sin descripción"
        raise Exception(f"AFIP rechazó la factura: {obs}")
    
    return {
        "cbte_nro": cbte_nro,
        "cae": wsfe.CAE,
        "vencimiento": wsfe.Vencimiento,
    }


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
    return "AFIP Microserver funcionando con PyAfipWS."


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
