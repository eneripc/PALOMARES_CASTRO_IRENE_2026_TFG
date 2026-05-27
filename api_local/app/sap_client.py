
import re, json, uuid, shutil, glob, os, requests, pandas as pd, numpy as np, xml.etree.ElementTree as ET, unicodedata
from typing import Optional, List, Dict, Any, Literal, Tuple
import xml.etree.ElementTree as ET
from datetime import datetime
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from openpyxl.utils import get_column_letter
from openpyxl.styles import PatternFill, Font, Alignment
from .config import settings

#data = (VARIANTE, CLASE, STATUS, FECHA_PARTIDAS_LOW, FECHA_PARTIDAS_HIGH, SOCIEDAD )
#       [("PAG_MASTER", "3", "1", "2025-11-10", "2025-11-10", "2214"),(),(),...]

def fbl1n(data, carpeta=str, base_dir ="."):

    out_dir = os.path.join(base_dir, carpeta)
    os.makedirs(out_dir, exist_ok=True)

    for strVariante, strClase, strStatus, fecha_partidas_low, fecha_partidas_high, sociedad in data:
        # --- Construcción del XML de entrada ---
        inputxml = f"""
    <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:urn="urn:sap-com:document:sap:rfc:functions">
        <soapenv:Header/>
        <soapenv:Body>
            <urn:Z_FBL1N_WS>
                <CLASE>{strClase}</CLASE>
                <CUENTA_HIGH></CUENTA_HIGH>
                <CUENTA_LOW></CUENTA_LOW>
                <FECHA_PARTIDAS_HIGH>{fecha_partidas_high}</FECHA_PARTIDAS_HIGH>
                <FECHA_PARTIDAS_LOW>{fecha_partidas_low}</FECHA_PARTIDAS_LOW>
                <SOCIEDAD>{sociedad}</SOCIEDAD>
                <STATUS>{strStatus}</STATUS>
                <VARIANTE>{strVariante}</VARIANTE>
                <IT_CME></IT_CME>
                <IT_ITEMS></IT_ITEMS>
                <IT_SOCIEDADGL></IT_SOCIEDADGL>
            </urn:Z_FBL1N_WS>
        </soapenv:Body>
    </soapenv:Envelope>
    """

        print("Llamando al servicio SOAP...")

        # --- Enviar la petición SOAP ---
        response = requests.post(
                        settings.SAP_URL,
                        data=inputxml.encode("utf-8"),
                        headers={"Content-Type": "text/xml; charset=utf-8"},
                        auth=(settings.SAP_USER, settings.SAP_PASSWORD),
                        verify=settings.SAP_VERIFY_SSL
                    )


        if response.status_code != 200:
            print("Error en la llamada SOAP:", response.status_code, response.text)
            raise RuntimeError(f"Error en la llamada SOAP: {response.status_code} - {response.text[:2000]}")

        # --- Parsear la respuesta XML ---
        root = ET.fromstring(response.text)

        # Busca los nodos 'item' dentro del cuerpo SOAP
        rows = []
        for item in root.findall(".//item"):
            row = {child.tag.upper(): child.text for child in item}
            rows.append(row)

        # Crear DataFrame equivalente a #tmp_FBL5N
        df_tmp = pd.DataFrame(rows)

        # --- Transformaciones para FACT_Cobros ---
        df_fact = pd.DataFrame()
        df_fact["CodHotel_Auditoria"] = -1
        df_fact["ID_PETICION"] = -1
        df_fact["ID_ETL"] = -1
        df_fact["ID_Ejecucion"] = -1
        df_fact["FyH_Ejecucion"] = datetime.now()

        # --- Mapeo de columnas desde #tmp_FBL1N hacia FACT_Pagos ---
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
            "ZZNAME1": "Nombre1"
        }

        # Aplicar mapeo
        for k, v in mapeo.items():
            if k.upper() in df_tmp.columns:
                df_fact[v] = df_tmp[k.upper()]
            else:
                df_fact[v] = None

        # --- Campos adicionales según FACT_Pagos ---
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
            "U_CPUDT": "Registrado2"
        }.items():
            if src in df_tmp.columns:
                df_fact[dest] = to_datetime_safe(df_tmp[src])
            else:
                df_fact[dest] = None

        #FACT_pagos = f"{strVariante}_{sociedad}_{fecha_partidas_high}.csv".replace("'", "")
        #out_fact = os.path.join(out_dir,FACT_pagos)
        #df_fact.to_csv(out_fact, index=False, encoding="utf-8-sig")

        return df_fact
