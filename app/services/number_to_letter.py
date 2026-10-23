"""
Conversor de montos numéricos a letras en español para comprobantes electrónicos SUNAT.
Formato estándar: "SON: CIEN CON 00/100 SOLES" o "SON: UN MIL DOSCIENTOS CON 50/100 DOLARES"
"""

from decimal import Decimal


UNIDADES = (
    "", "UN ", "DOS ", "TRES ", "CUATRO ", "CINCO ", "SEIS ", "SIETE ", "OCHO ", "NUEVE ",
    "DIEZ ", "ONCE ", "DOCE ", "TRECE ", "CATORCE ", "QUINCE ", "DIECISEIS ", "DIECISIETE ",
    "DIECIOCHO ", "DIECINUEVE ", "VEINTE "
)

DECENAS = (
    "", "", "VEINTI", "TREINTA ", "CUARENTA ", "CINCUENTA ", "SESENTA ", "SETENTA ",
    "OCHENTA ", "NOVENTA "
)

CENTENAS = (
    "", "CIENTO ", "DOSCIENTOS ", "TRESCIENTOS ", "CUATROCIENTOS ", "QUINIENTOS ",
    "SEISCIENTOS ", "SETECIENTOS ", "OCHOCIENTOS ", "NOVECIENTOS "
)


def _seccion(num: int, divisor: int, str_singular: str, str_plural: str) -> str:
    cientos = num // divisor
    resto = num - (cientos * divisor)
    letras = ""

    if cientos > 0:
        if cientos > 1:
            letras = _centenas(cientos) + " " + str_plural
        else:
            letras = str_singular

    if resto > 0:
        letras += ""

    return letras


def _centenas(num: int) -> str:
    centenas = num // 100
    decenas = num - (centenas * 100)

    if centenas == 1 and decenas == 0:
        return "CIEN"

    resultado = CENTENAS[centenas]

    if decenas <= 20:
        resultado += UNIDADES[decenas]
    else:
        dec = decenas // 10
        uni = decenas - (dec * 10)
        if dec == 2:
            resultado += "VEINTI" + UNIDADES[uni].strip() + " "
        elif uni > 0:
            resultado += DECENAS[dec] + "Y " + UNIDADES[uni]
        else:
            resultado += DECENAS[dec]

    return resultado


def _miles(num: int) -> str:
    divisor = 1000
    cientos = num // divisor
    resto = num - (cientos * divisor)

    str_miles = _seccion(num, divisor, "UN MIL", "MIL")
    str_centenas = _centenas(resto)

    if str_miles == "":
        return str_centenas

    return (str_miles.strip() + " " + str_centenas.strip()).strip()


def _millones(num: int) -> str:
    divisor = 1000000
    cientos = num // divisor
    resto = num - (cientos * divisor)

    str_millones = _seccion(num, divisor, "UN MILLON", "MILLONES")
    str_miles = _miles(resto)

    if str_millones == "":
        return str_miles

    return (str_millones.strip() + " " + str_miles.strip()).strip()


def monto_en_letras(monto: Decimal | float, moneda: str = "PEN") -> str:
    """
    Convierte un monto numérico a su representación en letras según la normativa SUNAT.
    Ejemplo: 1250.50, PEN -> "SON: UN MIL DOSCIENTOS CINCUENTA CON 50/100 SOLES"
    """
    if isinstance(monto, float):
        monto = Decimal(str(monto))

    # Redondeo estricto a 2 decimales
    monto = monto.quantize(Decimal("0.01"))
    entero = int(monto)
    decimales = int((monto - Decimal(entero)) * 100)

    if entero == 0:
        letras = "CERO"
    else:
        letras = _millones(entero)

    nombre_moneda = "SOLES" if moneda.upper() == "PEN" else "DOLARES AMERICANOS"
    if entero == 1 and moneda.upper() == "PEN":
        nombre_moneda = "SOL"

    return f"SON: {letras.strip()} CON {decimales:02d}/100 {nombre_moneda}".upper()
