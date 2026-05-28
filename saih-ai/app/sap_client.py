# app/sap_client.py
# Cliente SOAP para consultar SAP FBL1N y mapear la respuesta a un DataFrame

from datetime import datetime
from typing import Iterable

import pandas as pd
import requests
import xml.etree.ElementTree as ET

from .config import settings


def _build_fbl1n_xml(
    variante: str,
    clase: str,
    status: str,
    fecha_partidas_low: str,
    fecha_partidas_high: str,
    sociedad: str,
) -> str:
    """
    Construye el sobre SOAP para la llamada al servicio Z_FBL1N_WS.
    """
    return f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:urn="urn:sap-com:document:sap:rfc:functions">
    <soapenv:Header/>
    <soapenv:Body>
        <urn:Z_FBL1N_WS>
            <CLASE>{clase}</CLASE>
            <CUENTA_HIGH></CUENTA_HIGH>
            <CUENTA_LOW></CUENTA_LOW>
            <FECHA_PARTIDAS_HIGH>{fecha_partidas_high}</FECHA_PARTIDAS_HIGH>
            <FECHA_PARTIDAS_LOW>{fecha_partidas_low}</FECHA_PARTIDAS_LOW>
            <SOCIEDAD>{sociedad}</SOCIEDAD>
            <STATUS>{status}</STATUS>
            <VARIANTE>{variante}</VARIANTE>
            <IT_CME></IT_CME>
            <IT_ITEMS></IT_ITEMS>
            <IT_SOCIEDADGL></IT_SOCIEDADGL>
        </urn:Z_FBL1N_WS>
    </soapenv:Body>
</soapenv:Envelope>"""


def _parse_items_from_xml(xml_text: str) -> list[dict]:
    """
    Parsea la respuesta SOAP y extrae los nodos item como diccionarios.
    Se eliminan namespaces en las etiquetas para trabajar más cómodo.
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        raise RuntimeError(f"No se pudo parsear la respuesta XML de SAP: {e}") from e

    rows = []
    for item in root.findall(".//item"):
        row = {}
        for child in item:
            tag = child.tag.split("}", 1)[-1].upper()  # elimina namespace si existe
            row[tag] = child.text
        rows.append(row)

    return rows


def _map_tmp_to_fact(df_tmp: pd.DataFrame, fecha_partidas_high: str) -> pd.DataFrame:
    """
    Mapea el DataFrame temporal devuelto por SAP al formato FACT_Pagos usado por el pipeline.
    """
    df_fact = pd.DataFrame()

    # Campos técnicos / trazabilidad
    df_fact["CodHotel_Auditoria"] = -1
    df_fact["ID_PETICION"] = -1
    df_fact["ID_ETL"] = -1
    df_fact["ID_Ejecucion"] = -1
    df_fact["FyH_Ejecucion"] = datetime.now()

    mapeo = {
        "ANLN1": "Act_fijo",
        "AUGBL": "Doc_comp",
        "AUGDT": "Compens",
        "BLART": "Clase",
        "BLDAT": "Fecha_doc",
        "BSCHL": "CT",
        "BUDAT": "Fe_contab",
        "BUKRS": "Sociedad",
        "BWWR2": "ImpteML2",
        "BWWR3": "ImpteML3",
        "BWWRT": "ImpteML",
        "CCBTC": "Liquid",
        "EBELN": "Doc_compr",
        "FAEDT": "Venc_neto",
        "FILKD": "Subsid",
        "GJAHR": "Anio",
        "GKONT": "Cta_CP",
        "HKONT": "LibrMay",
        "HWAE2": "ML2",
        "HWAE3": "ML3",
        "HWAER": "ML",
        "KIDNO": "Refer_pago",
        "KOART": "ClCta",
        "KONTO": "Cuenta",
        "KOSTL": "Ce_coste",
        "MONAT": "Ej_mes",
        "REBZG": "Factura",
        "BUZEI": "Posicion",
        "U_ALTKT": "Cta_grp",
        "U_BELNR_FISCAL": "N_doc",
        "U_CHECF": "Hasta",
        "U_CPUDT": "Registrado",
        "U_TCODE": "CodT",
        "U_USNAM": "Usuario",
        "U_ZZTG": "Ti",
        "U_MSKS": "IO",
        "VBEWA": "ClMo",
        "VBUND": "SocGLA",
        "VERZN": "Demora",
        "WAERS": "Mon",
        "WRSHB": "ImpteMD",
        "XARCH": "Ár",
        "XBLNR": "Referencia",
        "XPYPR": "Orden pago",
        "XREF1": "Clv_ref_1",
        "XREF3": "Pos",
        "XSTRP": "L",
        "ZALDT": "Fecha_pago",
        "ZLSCH": "VP",
        "ZLSPR": "BP",
        "ZTERM": "CPag",
        "ZZEILE": "Observaciones",
        "SGTXT": "Texto",
        "ZZNAME1": "Nombre1",
    }

    for src, dest in mapeo.items():
        df_fact[dest] = df_tmp[src] if src in df_tmp.columns else None

    df_fact["PARAM_FechaClave"] = pd.to_datetime(fecha_partidas_high, errors="coerce")
    df_fact["Fecha Clave"] = df_fact["PARAM_FechaClave"]

    df_fact["CLASI_Clasificacion"] = "[NO CLASIFICADO]"
    df_fact["Asignacion"] = df_tmp["ZUONR"] if "ZUONR" in df_tmp.columns else None

    def to_datetime_safe(series):
        return pd.to_datetime(series, errors="coerce")

    for src, dest in {
        "BUDAT": "Fe_contab2",
        "ZALDT": "Fecha_pago2",
        "BLDAT": "Fecha_doc2",
        "FAEDT": "Venc_Neto2",
        "U_CPUDT": "Registrado2",
    }.items():
        df_fact[dest] = to_datetime_safe(df_tmp[src]) if src in df_tmp.columns else None

    return df_fact


def fbl1n(
    data: Iterable[tuple[str, str, str, str, str, str]],
    carpeta: str = "sap_tmp",
    base_dir: str = ".",
) -> pd.DataFrame:
    """
    Ejecuta una o varias llamadas SOAP al servicio FBL1N y devuelve un único DataFrame concatenado.
    Parámetros por tupla:
        (VARIANTE, CLASE, STATUS, FECHA_PARTIDAS_LOW, FECHA_PARTIDAS_HIGH, SOCIEDAD)

    Nota:
    - 'carpeta' y 'base_dir' se mantienen por compatibilidad, pero actualmente no se usan
      para persistir archivos en disco.
    """
    all_facts = []

    for variante, clase, status, fecha_partidas_low, fecha_partidas_high, sociedad in data:
        input_xml = _build_fbl1n_xml(
            variante=variante,
            clase=clase,
            status=status,
            fecha_partidas_low=fecha_partidas_low,
            fecha_partidas_high=fecha_partidas_high,
            sociedad=sociedad,
        )

        response = requests.post(
            settings.SAP_URL,
            data=input_xml.encode("utf-8"),
            headers={"Content-Type": "text/xml; charset=utf-8"},
            auth=(settings.SAP_USER, settings.SAP_PASSWORD),
            verify=settings.SAP_VERIFY_SSL,
            timeout=120,
        )

        if response.status_code != 200:
            raise RuntimeError(
                f"Error en la llamada SOAP a SAP: {response.status_code} - {response.text[:2000]}"
            )

        rows = _parse_items_from_xml(response.text)
        df_tmp = pd.DataFrame(rows)

        if df_tmp.empty:
            # Si una sociedad no devuelve datos, añadimos un DF vacío pero no rompemos.
            all_facts.append(pd.DataFrame())
            continue

        df_fact = _map_tmp_to_fact(df_tmp, fecha_partidas_high)
        all_facts.append(df_fact)

    if not all_facts:
        return pd.DataFrame()

    non_empty = [df for df in all_facts if not df.empty]
    if not non_empty:
        return pd.DataFrame()

    return pd.concat(non_empty, ignore_index=True)