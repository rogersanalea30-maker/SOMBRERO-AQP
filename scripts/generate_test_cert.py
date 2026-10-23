"""
Script para generar un Certificado Digital de Prueba (.pfx)
Permite realizar pruebas locales de firmado XML y comunicación con el entorno Beta de SUNAT
sin necesidad de adquirir un certificado comercial inmediatamente.
"""

import os
import datetime
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography import x509
from cryptography.x509.oid import NameOID


def generate_self_signed_pfx(
    output_path: str = "app/certificates/certificate.pfx",
    password: str = "123456",
    ruc: str = "20000000001",
    razon_social: str = "EMPRESA DE PRUEBA S.A.C."
) -> str:
    """Genera un certificado digital autofirmado en formato PKCS#12 (.pfx)."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # 1. Generar llave privada RSA 2048 bits
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    # 2. Configurar Subject e Issuer (Autofirmado)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "PE"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, razon_social),
        x509.NameAttribute(NameOID.COMMON_NAME, f"RUC {ruc}"),
    ])

    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=365 * 2))  # Válido 2 años
        .add_extension(
            x509.BasicConstraints(ca=False, path_length=None), critical=True
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=True,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True
        )
        .sign(private_key, hashes.SHA256())
    )

    # 3. Serializar a PKCS#12 (.pfx)
    pfx_bytes = pkcs12.serialize_key_and_certificates(
        name=b"SUNAT_CERT_BETA",
        key=private_key,
        cert=cert,
        cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(password.encode("utf-8"))
    )

    with open(output_path, "wb") as f:
        f.write(pfx_bytes)

    print(f"[OK] Certificado generado exitosamente en: {output_path}")
    print(f"     Password: {password}")
    print(f"     RUC: {ruc}")
    print(f"     Validez: 2 anos a partir de hoy")
    return output_path


if __name__ == "__main__":
    generate_self_signed_pfx()
