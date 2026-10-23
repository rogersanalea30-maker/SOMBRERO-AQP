# Sistema de Facturación Electrónica SUNAT (UBL 2.1) con FastAPI y Python

Sistema backend modular, escalable, open source y **100% gratuito (sin intermediarios ni pagos a OSE)** para la emisión directa de **Facturas Electrónicas (01)** y **Boletas de Venta (03)** conectándose directamente a los Web Services SOAP (`BillService`) de la **SUNAT (Perú)**.

---

## 🚀 Características Principales

- **Conexión Directa con SUNAT:** Emisión de comprobantes sin pasar por OSEs (Operadores de Servicios Electrónicos) ni plataformas de terceros que cobran por comprobante.
- **Estándar UBL 2.1 Estricto:** Cumple con la normativa oficial de SUNAT para Facturas (01) y Boletas de Venta (03), operaciones Gravadas (10), Exoneradas (20), Inafectas (30), Forma de Pago (Contado y Crédito con Cuotas) y Monto en Letras automático (Leyenda 1000).
- **Firma Digital Criptográfica (XMLDSIG):** Firma con certificado digital PKCS#12 (`.pfx` / `.p12`) utilizando canonicalización Inclusive C14N 1.0 y transform Enveloped-Signature según el estándar W3C, calculando el `DigestValue` (Hash oficial para la representación impresa en PDF y código QR).
- **Cliente SOAP Robusto con Zeep:** Conexión con `sendBill` autenticado mediante WS-Security `UsernameToken` (`RUC + Usuario SOL`), empaquetado ZIP automático (`RUC-Tipo-Serie-Correlativo.zip`) y descarga/análisis de la Constancia de Recepción (**CDR**).
- **WSDLs Offline Auto-contenidos:** Evita errores de conectividad o HTTP 401 durante el arranque del servicio al incluir las definiciones WSDL/XSD oficiales de SUNAT localmente.
- **API REST Moderna con FastAPI:** Validación automática de datos de entrada con Pydantic V2, documentación interactiva Swagger (`/docs`) y ReDoc (`/redoc`), endpoints de previsualización offline, descarga de archivos y consulta de estado de CDR.

---

## 📁 Estructura del Proyecto

```text
├── app/
│   ├── __init__.py
│   ├── main.py                  # API FastAPI, rutas y manejo de excepciones
│   ├── config.py                # Variables de entorno y configuración (pydantic-settings)
│   ├── schemas/                 # Validación de esquemas Pydantic
│   │   ├── __init__.py
│   │   ├── invoice.py           # Modelos de Emisor, Cliente, Items y Comprobante
│   │   └── response.py          # Modelos de respuesta y CDR
│   ├── services/                # Lógica del dominio de facturación
│   │   ├── __init__.py
│   │   ├── xml_builder.py       # Generador de XML UBL 2.1 según catálogos SUNAT
│   │   ├── signer.py            # Firma digital XMLDSIG con certificado .pfx
│   │   ├── sunat_client.py      # Cliente SOAP Zeep, sendBill y procesamiento de CDR
│   │   └── number_to_letter.py  # Conversión de números a letras (Leyenda 1000)
│   ├── certificates/            # Contenedor para el certificado .pfx y llaves
│   ├── storage/                 # Almacenamiento local de archivos
│   │   ├── xml/                 # XMLs originales y firmados
│   │   ├── zip/                 # ZIPs enviados a SUNAT
│   │   └── cdr/                 # CDRs (ZIPs y XMLs de respuesta)
│   └── wsdl/                    # Definiciones WSDL y esquemas XSD de SUNAT
├── scripts/
│   ├── generate_test_cert.py    # Generador de certificado .pfx autofirmado para pruebas
│   └── test_invoice_flow.py     # Suite de pruebas de integración end-to-end
├── .env.example                 # Plantilla de variables de entorno
├── requirements.txt             # Dependencias del proyecto
└── README.md                    # Documentación
```

---

## 🛠️ Instalación y Puesta en Marcha

### 1. Clonar el repositorio y crear entorno virtual

```bash
# Crear entorno virtual
python -m venv venv

# Activar entorno virtual
# En Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# En Linux / macOS:
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt
```

### 2. Configurar variables de entorno (`.env`)

Copia el archivo `.env.example` a `.env`:

```bash
cp .env.example .env
```

Configura tus credenciales en el archivo `.env`:

```env
# Entorno: BETA (pruebas) o PRODUCTION (producción)
SUNAT_ENV=BETA

# Datos del Emisor
EMISOR_RUC=20000000001
EMISOR_RAZON_SOCIAL=EMPRESA DE PRUEBA S.A.C.
EMISOR_NOMBRE_COMERCIAL=MI TIENDA ONLINE
EMISOR_UBIGEO=150101
EMISOR_DIRECCION=AV. REPUBLICA DE PANAMA 3055 - SAN ISIDRO
EMISOR_CODIGO_ESTABLECIMIENTO=0000

# Credenciales SOL (Usuario Secundario)
# En BETA de SUNAT se utiliza comúnmente MODDATOS y moddatos
SUNAT_USER=MODDATOS
SUNAT_PASSWORD=moddatos

# Certificado Digital (.pfx)
CERT_PATH=app/certificates/certificate.pfx
CERT_PASSWORD=123456
```

### 3. Generar un Certificado de Prueba (Opcional para pruebas locales)

Si no tienes un certificado digital comercial aún, puedes generar uno de prueba automáticamente:

```bash
python scripts/generate_test_cert.py
```

Esto generará `app/certificates/certificate.pfx` válido por 2 años con la clave `123456`.

### 4. Ejecutar el Servidor FastAPI

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Accede a la documentación interactiva Swagger en:
👉 **http://localhost:8000/docs**

---

## 🧪 Ejecución de Pruebas de Integración

Puedes correr la suite de pruebas completa que valida la generación, firmado, envío a SUNAT Beta y descarga de CDR:

```bash
python scripts/test_invoice_flow.py
```

---

## 📡 Endpoints de la API

### 1. Emitir y Enviar Comprobante a SUNAT
- **Método:** `POST`
- **Ruta:** `/api/v1/invoices`
- **Descripción:** Genera el XML UBL 2.1, lo firma con el certificado digital, empaqueta el ZIP, lo envía al Web Service de SUNAT y procesa la Constancia de Recepción (CDR).

#### Ejemplo de Solicitud (Factura 01):
```json
{
  "tipo_documento": "01",
  "serie": "F001",
  "correlativo": 1001,
  "moneda": "PEN",
  "forma_pago": "Contado",
  "cliente": {
    "tipo_doc": "6",
    "num_doc": "20555555551",
    "razon_social": "DISTRIBUIDORA NACIONAL S.A.C.",
    "direccion": "AV. LOS HEROES 450 - LIMA"
  },
  "items": [
    {
      "codigo": "SERV-01",
      "descripcion": "DESARROLLO DE SOFTWARE A MEDIDA",
      "unidad_medida": "ZZ",
      "cantidad": 1.0,
      "valor_unitario": 100.0,
      "tipo_afectacion_igv": "10",
      "porcentaje_igv": 18.0
    }
  ]
}
```

#### Ejemplo de Respuesta Exitosa:
```json
{
  "success": true,
  "message": "Comprobante aceptado por SUNAT: La Factura numero F001-00001001, ha sido aceptada",
  "document_id": "F001-00001001",
  "tipo_documento": "01",
  "hash_cpe": "vwRGqZ2DyR+OwHXjgEZjEEdy5DM=",
  "cdr": {
    "response_code": "0",
    "description": "La Factura numero F001-00001001, ha sido aceptada",
    "notes": [],
    "response_date": "2026-10-23",
    "response_time": "16:53:09",
    "accepted": true
  },
  "files": {
    "xml": "app/storage/xml/20000000001-01-F001-00001001-unsigned.xml",
    "signed_xml": "app/storage/xml/20000000001-01-F001-00001001.xml",
    "zip": "app/storage/zip/20000000001-01-F001-00001001.zip",
    "cdr_zip": "app/storage/cdr/R-20000000001-01-F001-00001001.zip",
    "cdr_xml": "app/storage/cdr/R-20000000001-01-F001-00001001.xml"
  },
  "errors": null
}
```

---

### 2. Previsualizar XML Firmado (Offline / Pruebas)
- **Método:** `POST`
- **Ruta:** `/api/v1/invoices/preview-xml`
- **Descripción:** Genera y firma el XML sin enviar a SUNAT. Devuelve el contenido completo del XML y el código Hash `DigestValue`.

---

### 3. Descargar Archivos Generados
- **Método:** `GET`
- **Ruta:** `/api/v1/invoices/{document_id}/download/{file_type}`
- **Parámetros de ruta:**
  - `document_id`: `F001-00001001`
  - `file_type`: `xml`, `signed-xml`, `zip`, `cdr-zip`, `cdr-xml`

---

### 4. Consultar CDR Almacenado
- **Método:** `GET`
- **Ruta:** `/api/v1/invoices/{document_id}/cdr`
- **Descripción:** Lee y parsea la Constancia de Recepción guardada en storage para verificar el estado de aceptación.

---

## 📑 Catálogos SUNAT Implementados

| Catálogo | Descripción | Valores Soportados |
| :--- | :--- | :--- |
| **Catálogo 01** | Tipo de Comprobante | `01` (Factura), `03` (Boleta de Venta) |
| **Catálogo 02** | Código de Moneda | `PEN` (Soles), `USD` (Dólares Americanos) |
| **Catálogo 06** | Tipo de Doc. Identidad | `6` (RUC), `1` (DNI), `4` (C.E.), `7` (Pasaporte), `0` (Otros) |
| **Catálogo 07** | Afectación al IGV | `10` (Gravado), `20` (Exonerado), `30` (Inafecto), `40` (Exportación) |
| **Catálogo 16** | Tipo de Precio | `01` (Precio Unitario con Impuestos) |
| **Catálogo 51** | Tipo de Operación | `0101` (Venta Interna) |
| **Catálogo 52** | Códigos de Leyendas | `1000` (Monto en Letras) |

---

## 🔒 Consideraciones de Seguridad y Producción

1. **Certificado Digital para Producción:**
   Para emitir con validez tributaria real, debes contar con un Certificado Digital emitido por una entidad de certificación acreditada en el Perú (Llamasoft, Reniec, Camerfirma, Avansi, etc.). Reemplaza `CERT_PATH` y `CERT_PASSWORD` en `.env`.
2. **Usuario Secundario SOL:**
   Crea un usuario secundario en SUNAT Operaciones en Línea (SOL) asignándole los permisos necesarios del Sistema de Emisión Electrónica (SEE).
3. **Paso a Producción:**
   Cambia en el `.env` la variable `SUNAT_ENV=PRODUCTION`. El sistema apuntará automáticamente al endpoint de producción:
   `https://e-factura.sunat.gob.pe/ol-ti-itcpfegem/billService`.
