import numpy as np
import pandas as pd
import re
import unicodedata
import os
from openpyxl.utils import get_column_letter
from openpyxl.styles import PatternFill, Font, Alignment, Color
from copy import copy
import glob
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

# CONTEXTO CORPORATIVO Y PARAMETRIZACIÓN GEOGRÁFICA (BARCELÓ HOTEL GROUP)

# Sets de sociedades organizadas por regiones operativas para la asignación de umbrales de riesgo
# por terminos de seguridad solo se pueden ver los de las UEs tratadas en el proyecto 

# Sets de sociedades organizadas por regiones operativas para la asignación de umbrales de riesgo
latam = set( ["5600","5601","5602","5603","5604","6300","7000","P300","5606", 
              "7400", "7401","7601","7800","7801","J400","7402" ])

emea = set([""])

# Diccionario de mapeo estructural: Vincula Sociedades Legales de SAP con sus respectivas Unidades de Explotación (UE/Hoteles)
map_soc_UE = {"5600":"Maya","5601":"Maya","5602":"Maya","5603":"Maya","5604":"Maya","6300":"Maya","7000":"Maya","P300":"Maya","5606":"Maya",
            "7400":"Bavaro","7401":"Bavaro","7601":"Bavaro","7800":"Bavaro","7801":"Bavaro","J400":"Bavaro","7402":"Bavaro",
             } # Aqui se añadirian todas las sociedades y su correspondiente Unidad de Explotación

# --- Parámetros globales de infraestructura de red ---
IS_DEV = False
url = "" # información confidencial
user ="" # información confidencial
password ="" # información confidencial

# FUNCIONES PRINCIPALES DEL PIPELINE DE AUDITORÍA

def fbl1n(data, carpeta=str, base_dir ="."):
    """
        Fase ETL 1: Extracción de datos transaccionales mediante servicios SOAP corporativos.
        Replica la lógica de la transacción nativa SAP FBL1N (Partidas Individuales de Proveedores).
        
        Parámetros:
        -----------
        data : list of tuples
            Contiene los parámetros de consulta de SAP: 
            (VARIANTE, CLASE, STATUS, FECHA_LOW, FECHA_HIGH, SOCIEDAD)
        carpeta : str
            Nombre del directorio de destino para almacenar los archivos CSV parciales.
        base_dir : str
            Ruta base del sistema de archivos local o del contenedor cloud.
            
        Retorna:
        --------
        pd.DataFrame
            Dataset consolidado (Master) con todas las sociedades y periodos consultados.
        """
    
    out_dir = os.path.join(base_dir, carpeta)
    os.makedirs(out_dir, exist_ok=True)


    dfs = []

    for strVariante, strClase, strStatus, fecha_partidas_low, fecha_partidas_high, sociedad in data:
        # Construcción del sobre XML SOAP según el contrato técnico de la API SAP 
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

        # Orquestación síncrona HTTP POST hacia el servidor central de SAP
        response = requests.post(
            url,
            data=inputxml.encode("utf-8"),
            headers={"Content-Type": "text/xml; charset=utf-8"},
            auth=(user, password),
            verify = False
        )

        if response.status_code != 200:
            print("Error en la llamada SOAP:", response.status_code, response.text)
            exit()

        # Parseo del árbol XML y conversión a formato tabular
        root = ET.fromstring(response.text)
        rows = []
        for item in root.findall(".//item"):
            row = {child.tag.upper(): child.text for child in item}
            rows.append(row)

        # Dataset crudo temporal equivalente a la tabla temporal del procedimiento almacenado
        df_tmp = pd.DataFrame(rows)

        # Inicialización del DataFrame estandarizado (FACT_Pagos)
        df_fact = pd.DataFrame()
        df_fact["CodHotel_Auditoria"] = -1
        df_fact["ID_PETICION"] = -1
        df_fact["ID_ETL"] = -1
        df_fact["ID_Ejecucion"] = -1
        df_fact["FyH_Ejecucion"] = datetime.now()


        # Mapeo de columnas desde #tmp_FBL1N hacia FACT_Pagos
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

        for k, v in mapeo.items():
            if k.upper() in df_tmp.columns:
                df_fact[v] = df_tmp[k.upper()]
            else:
                df_fact[v] = None

        # Inyección de variables de control temporal de auditoría
        df_fact["PARAM_FechaClave"] = pd.to_datetime(fecha_partidas_high, errors="coerce")
        df_fact["Fecha Clave"] = df_fact["PARAM_FechaClave"]

        df_fact["CLASI_Clasificacion"] = "[NO CLASIFICADO]"
        df_fact["Asignacion"] = df_tmp["ZUONR"] if "ZUONR" in df_tmp.columns else None
        
        # Guardar dataset indexado parcial por sociedad y fecha (Garantiza idempotencia)
        FACT_pagos = f"{strVariante}_{sociedad}_{fecha_partidas_high}.csv".replace("'", "")
        out_fact = os.path.join(out_dir,FACT_pagos)
        df_fact.to_csv(out_fact, index=False, encoding="utf-8-sig")

        dfs.append(df_fact)
   
    if not dfs:
        return pd.DataFrame()

    # Consolidación final mediante concatenación en memoria (Lógica Batch)
    df_master = pd.concat(dfs, ignore_index=True) if len(dfs) > 1 else dfs[0]

    if len(dfs) > 1:
        nombre_carpeta = carpeta.lower().replace(" ", "_")
        master_name = f"FACT_MASTER_{nombre_carpeta}.csv"
        df_master.to_csv(os.path.join(out_dir, master_name), index=False, encoding="utf-8-sig")

    return df_master

def preprocess(data):
    """
    Fase ETL 2: Limpieza estructural, normalización semántica e ingeniería de características.
    Prepara la matriz multidimensional con  las líneas transaccionales puras y las totales.
    
    Parámetros:
    -----------
    data : pd.DataFrame o str/Path
        Estructura de datos en memoria o ruta física del archivo CSV/Excel de origen.
        
    Retorna:
    --------
    pd.DataFrame
        Dataset ordenado cronológicamente con las nuevas variables calculadas (Antigüedad, Demora, Delta).
    """
        
    if isinstance(data, pd.DataFrame):
        df = data.copy()
        
    if isinstance(data, (str, Path)):
        path = Path(data)
        if path.suffix.lower() == ".csv":
            df = pd.read_csv(path)
        elif path.suffix.lower() in (".xlsx", ".xls"):
            df = pd.read_excel(path, engine="openpyxl")

    # Eliminación de artefactos y columnas sin valor analítico generadas por Excel
    if 'Unnamed: 0' in df.columns:
        df.drop(columns = ['Unnamed: 0'], inplace = True)

    columnas_vacias = df.columns[df.isna().all()]
    df.drop(columns=columnas_vacias, inplace=True)

    def _norm(s: str) -> str:
        """Elimina acentos, caracteres especiales y unifica separadores a snake_case."""
        s = "" if s is None else str(s)
        s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
        s = s.strip().lower()
        s = re.sub(r"[^\w]+", "_", s)
        s = re.sub(r"_+", "_", s).strip("_")
        return s
    
    # Resolución del alcance geográfico: Enlace relacional con la Unidad de Explotación (Hotel)
    df["UE"] = df["Sociedad"].astype(str).str.upper().map(map_soc_UE).fillna("OTRO")
    df = df[['UE'] + [c for c in df.columns if c != 'UE']]

    def standardize_columns_simple(df):
        """Mapea listas de alias lingüísticos heterogéneos a nombres de columnas estándar."""
        df = df.copy()
        df = df.loc[:, ~df.columns.duplicated()].copy()
        current = {_norm(c): c for c in df.columns} # Mapa: nombre normalizado -> nombre real en df

        # Alias ordenados por prioridad
        aliases = {
            "Fecha Clave": ["Fecha Clave", "Fecha_informe", "PARAM_FechaClave", "Fecha informe", "FechaInforme", "Fecha Informe", 'Fecha_informe'],
            "UE": ['ue','UE','Unidad de Explotación', 'unidad de explotación'],
            "Sociedad": ["Sociedad", "CodHotel_Auditoria", "Soc", "SocGLA"],
            "Cuenta": ["Cuenta", "Proveedor", "Vendor", "Cta_CP", "Cta.CP", "Cta_CP"],
            "Nombre1": ["Nombre1", "Nombre", "NomProveedor", "Proveedor_nombre"],
            "N_doc": ["Nºdoc.", "Nºdoc", "N_doc", "N_doc_", "N_doc.", "Ndoc", "Documento", "Doc", "Doc.Fiscal", "Doc_Fiscal", "Doc_comp", "Doc_compr"],
            "Registrado": [ "Registrado", "PostingDate", "Fecha_registro"],
            "Ej_mes": ["Ej./mes", "Ej_mes", "Ej mes", "Periodo", "Anio", "Año", "Anio_mes"],
            "Fe_contab": ["Fe_contab", "Fe.contab.", "Fe.contab", "Fecha_contable"],
            "Venc_neto": [ "Venc_neto", "Venc.neto", "Vencimiento", "Fecha_vencimiento", "Vto_neto"],
            "Fecha_doc": [ "Fecha_doc", "Fecha doc.", "Fecha documento", "DocDate", "FechaDoc"],
            "Fecha_pago": ["Fecha_pago", "Fecha pago", "FechaPago", "Fecha de pago"],
            "Antigüedad": ["Antigüedad", "Antiguedad", "Antiguedad_dias", "AgrupacionAntiguedadMaxima"],
            "Texto": ["Texto", "Texto cab. Documento", "Texto cab Documento", "Texto_cab_Documento", "Observaciones"],
            "Clase": ["Clase", "TipoDoc", "ClaseDoc", "DocType"],
            "ImpteML": ["ImporteML", "ImpteML", "Importe", "AmountML"],
            "ML": ["ML", "Mon.", "Mon", "Moneda", "Currency", "ClMo"],
            "Demora": ["Demora", "Mora", "Delay", "Demora_dias"],
            "BP": ["BP", "CME", "Ind.CME", "Ind CME", "Clave CME", "Operación especial", "Operacion especial", "CP"],
            "Factura":['Factura', 'Fact'],
        }

        rename = {}
        used_targets = set()

        for std_name, cand_list in aliases.items():
            chosen = None
            for cand in cand_list:
                cand_norm = _norm(cand)
                if cand_norm in current:
                    chosen = current[cand_norm]
                    break
            if chosen is None:
                continue
            if std_name in used_targets:  # Evitar colisiones: no renombrar 2 columnas distintas al mismo estándar
                continue

            rename[chosen] = std_name
            used_targets.add(std_name)

        df = df.rename(columns=rename)

        return df

    df = standardize_columns_simple(df)

    # Ordenación temporal y contable estricta para garantizar consistencia en auditoría externa
    df = df.sort_values(by=["Fecha Clave","UE","Sociedad", "Cuenta", "Fe_contab", "N_doc"], ascending=[ True,True,True, True, True, True]).reset_index(drop=True)

    def cpag_to_days(series: pd.Series, default_days: int = 0) -> pd.Series:
        """"Parsea cadenas alfanuméricas de condiciones de pago de SAP a enteros (días)."""
        if series is None:
            return pd.Series(default_days)

        s = series.astype(str).str.upper().str.strip()

        days = s.str.extract(r"(\d+)", expand=False)
        days = pd.to_numeric(days, errors="coerce").fillna(default_days).astype(int)

        return days
    
    # Estandarización y tipado de variables temporales (Modo fecha estricto)
    for col in ["Fecha_doc","Fe_contab","Registrado","Fecha_pago",'Venc_neto', 'Fecha Clave']:
        df[col] = pd.to_datetime(df[col], errors="coerce").dt.normalize()

    if "CPag" in df.columns:
        cpag_days = cpag_to_days(df["CPag"], default_days=0)
    else:
        cpag_days = pd.Series(0, index=df.index)

    cpag_td = pd.to_timedelta(cpag_days, unit="D")

    # FEATURE ENGINEERING)

    # Antigüedad = Fecha informe - (Fe_contab + CPag)
    if "Antigüedad" not in df.columns:
        due_teorico = df["Fe_contab"] + cpag_td
        df["Antigüedad"] = (df["Fecha Clave"] - due_teorico).dt.days
  
    # Demora = Antigüedad - (Venc_neto - Fe_contab)
    if 'Demora' not in df.columns:
        df['vt menos contable'] = (df["Venc_neto"] - df["Fe_contab"]).dt.days
        df['vt menos contable'].fillna(0)
        df['Demora'] = df['Antigüedad'] - df['vt menos contable']
        df['Demora'].fillna(0)

    # Delta = Fecha_Registro_Sistema - Fecha_Emisión_Documento
    if 'Registrado' in df.columns and 'Fecha_doc' in df.columns:
        # Manipulación de fechas (cuántos días cambió la fecha “de documento” respecto a la real)
        df["Delta_fecha_doc"] = (df["Registrado"] - df['Fecha_doc'] ).dt.days
        df["Delta_fecha_doc"].fillna(0)

    # ESTRATEGIA DE AGRUPACIÓN

    totales = (df.groupby(["Fecha Clave","UE","Sociedad", "Cuenta","Nombre1"], as_index=False)["ImpteML"].sum().rename(columns={"ImpteML": "ImpteML"}))

    # Construir filas TOTAL con las mismas columnas que df
    total_rows = pd.DataFrame(columns=df.columns)

    total_rows["Fecha Clave"]  = totales["Fecha Clave"]
    total_rows["UE"]  = totales["UE"]
    total_rows["Sociedad"]  = totales["Sociedad"]
    total_rows["Cuenta"]    = totales["Cuenta"]
    total_rows["Nombre1"] = totales["Nombre1"]
    total_rows["ImpteML"] = totales["ImpteML"]

    # Indicador binario analítico: 0 = Partida individual de línea, 1 = Fila agregada TOTAL
    df["_is_total"] = 0
    total_rows["_is_total"] = 1

    # Concatenar y ordenar: mismo proveedor + _is_total al final
    df = (pd.concat([df, total_rows], ignore_index=True, sort=False).sort_values(by=["Fecha Clave","UE","Sociedad", "Cuenta", "_is_total", "Fe_contab", "N_doc"], ascending=[True, True,True, True, True, True, True], na_position="last").reset_index(drop=True))

    # Limpieza de fechas centinela por errores de desbordamiento en exportaciones de SAP (1899-1900)
    df["Fecha_pago"] = pd.to_datetime(df["Fecha_pago"], errors="coerce")
    mask_sentinela = df["Fecha_pago"].notna() & (df["Fecha_pago"] <= pd.Timestamp("1900-01-02"))     # Limpia 1899-12-30, 1899-12-31, 1900-01-01, 1900-01-02
    df.loc[mask_sentinela, "Fecha_pago"] = pd.NaT

    # Asignación de umbrales internos corporativos condicionados por región geográfica (EMEA vs LATAM)
    df.loc[df["Sociedad"].isin(latam) & df["_is_total"].eq(0), "antig"] = 180
    df.loc[df["Sociedad"].isin(emea) & df["_is_total"].eq(0), "antig"] = 365
    df["antig"] = pd.to_numeric(df["antig"], errors="coerce").fillna(365).astype(int)

    return df

def casuistica(df: pd.DataFrame):
    """
    Fase 3: Motor de Reglas de Negocio Contables.
    Aplica de forma determinista los criterios del Manual de Auditoría Interna de Barceló
    para clasificar partidas, identificar desviaciones materiales y construir los textos de solicitudes.
    
    Parámetros:
    -----------
    df : pd.DataFrame
        Dataset preprocesado con variables homogéneas.
        
    Retorna:
    --------
    pd.DataFrame
        Dataset enriquecido con las columnas ['Casuística', 'Análisis', 'Solicitud'] formalizadas.
    """

    columnas = ['Fecha Clave','UE','Sociedad', 'Cuenta','Nombre1', 'N_doc',
       'Registrado', 'Ej_mes', 'Fe_contab', 'Venc_neto', 'Fecha_doc',
       'Antigüedad', 'Texto', 'Clase', 'ImpteML', 'ML', 'Demora','Referencia', 'Factura', 'BP', 'CPag','Fecha_pago', 'LibrMay','antig', '_is_total']

    df = df[[c for c in columnas if c in df.columns]].copy()

    # 0) Normalizaciones básicas

    df["ImpteML"]  = pd.to_numeric(df.get("ImpteML"), errors="coerce")
    df["Antigüedad"] = pd.to_numeric(df.get("Antigüedad"), errors="coerce")

    # Normalizar _is_total  
    if "_is_total" not in df.columns:
        doc_col = "N_doc" if "N_doc." in df.columns else None
        clase_col = "Clase" if "Clase" in df.columns else None
        if doc_col and clase_col:
            df["_is_total"] = (df[doc_col].isna() & df[clase_col].isna()).astype(int)
        elif doc_col:
            df["_is_total"] = (df[doc_col].isna()).astype(int)
        else:
            df["_is_total"] = 0
    else:
        df["_is_total"] = pd.to_numeric(df["_is_total"], errors="coerce").fillna(0).astype(int)
        df["_is_total"] = df["_is_total"].clip(0, 1)

    # Inicialización de nuevas columnas
    df["Casuística"] = pd.NA
    df["Análisis"]   = pd.NA
    df["Solicitud"]  = pd.NA

    # Limpieza de registros redundantes huérfanos de información temporal
    cols_check = [c for c in ["N_doc", "Clase", "Fe_contab", "Fecha_doc", "Registrado", "Venc_neto"] if c in df.columns]
    if cols_check:
        mask_total_like = (df["_is_total"].eq(0) & df["ImpteML"].notna() & df[cols_check].isna().all(axis=1))
        if mask_total_like.any():
            df = df.loc[~mask_total_like].copy()

    # Máscaras base
    mask_total    = df["_is_total"].eq(1)
    mask_partidas = df["_is_total"].eq(0)

    # Claves proveedor
    keys = ["Fecha Clave", "Sociedad", "Cuenta"]
    have_keys = all(k in df.columns for k in keys)

    
    # Recálculo geométrico/contable del saldo real acumulado mapeado en la fila TOTAL del proveedor
    if have_keys:
        saldo_grp = df.loc[mask_partidas].groupby(keys, dropna=False)["ImpteML"].sum()
        idx = pd.MultiIndex.from_frame(df[keys])
        saldo_map = pd.Series(idx.map(saldo_grp), index=df.index)
        df.loc[mask_total, "ImpteML"] = saldo_map.loc[mask_total].values
    else:
        idx = pd.Index([None]*len(df))

    # Signos de las partidas
    mask_deud = df["ImpteML"] > 0
    mask_acre = df["ImpteML"] < 0

    # Inicialización de máscaras de envejecimiento de saldos basados en umbrales de control interno
    antig = df["antig"]
    mask_deud_antigua = mask_deud & (df["Antigüedad"] > 31)
    mask_acre_antigua = mask_acre & (df["Antigüedad"] > antig)

    # Clase
    clase = df["Clase"].astype(str) if "Clase" in df.columns else pd.Series("", index=df.index)
    mask_abono   = clase.isin(["AB", "KG"])
    mask_factura = clase.isin(["KR", "RE"])
    mask_z6      = clase.eq("Z6")
    mask_pago    = clase.isin(["KZ", "ZP"])
    mask_kg      = clase.eq("KG")

    # 1) ANÁLISIS SALDO TOTAL

    df.loc[mask_total & (df["ImpteML"] < 0), "Análisis"] = "Ok saldo total acreedor"
    df.loc[mask_total & (df["ImpteML"] > 0), "Análisis"] = "Saldo total deudor"
    df.loc[mask_total & (df["ImpteML"] == 0), "Análisis"] = "Ok saldado"

    # 2) CASUÍSTICA PARTIDAS
    # Cuentas 407 (Anticipos) y 4001 (Retenciones) se aíslan para evitar sesgar el análisis de deudores ordinarios
    SPECIAL_LM = ["40700001", "40010001"]   

    lm= df["LibrMay"].astype(str).str.strip()
    mask_lm = lm.isin(SPECIAL_LM)
    df.loc[mask_partidas & mask_lm, 'Casuística'] = 'Anticipo / Retención'

    df.loc[mask_partidas & mask_acre_antigua & df["Casuística"].isna(), "Casuística"] = "Acreedora antigua"
    df.loc[mask_partidas & mask_acre & df["Casuística"].isna(), "Casuística"] = "Acreedora"
    df.loc[mask_partidas & mask_deud & df["Casuística"].isna(), "Casuística"] = "Deudora"

    # 3) ANÁLISIS PARTIDAS INDIVIDUALES

    # Acreedoras antiguas = incidencia
    df.loc[mask_partidas & mask_acre_antigua, "Análisis"] = "Acreedora antigua"

    # Deudoras: explicar todas
    abono_reciente = mask_partidas & mask_deud & (df["Antigüedad"] < 31) & mask_abono
    df.loc[abono_reciente & df["Análisis"].isna(), "Análisis"] = "Ok abono reciente"

    abono_antiguo = mask_partidas & mask_deud_antigua & mask_abono

    # Para decidir si un abono antiguo está "cubierto" por facturas posteriores pendientes:
    requiere_fechas_partida = ("Fe_contab" in df.columns) and ("Clase" in df.columns) and have_keys

    if requiere_fechas_partida:
        part_full = df.loc[mask_partidas].copy()
        part_full["_fc"] = pd.to_datetime(part_full["Fe_contab"], errors="coerce")

        if "Fecha_pago" in part_full.columns:
            part_full["_fp"] = pd.to_datetime(part_full["Fecha_pago"], errors="coerce")
        else:
            part_full["_fp"] = pd.NaT

        grp_full = part_full.groupby(keys, dropna=False)

        def flag_facturas_posteriores_pendientes(gr: pd.DataFrame):
            # Devuelve Series booleana por índice de abonos (deudoras AB/KG) antiguos:
            # True si existe factura (KR/RE, acreedora) posterior al abono y sin pagar.
            res = pd.Series(False, index=gr.index)

            fact_pend = gr[
                (gr["ImpteML"] < 0) &
                (gr["Clase"].astype(str).isin(["KR", "RE"])) &
                (gr["_fp"].isna()) &
                (gr["_fc"].notna())
            ][["_fc"]]

            if fact_pend.empty:
                return res

            # Para cada abono, si hay alguna factura posterior:
            abonos = gr[
                (gr["ImpteML"] > 0) &
                (gr["Clase"].astype(str).isin(["AB","KG"])) &
                (gr["Antigüedad"] > 31) &
                (gr["_fc"].notna())
            ][["_fc"]]

            if abonos.empty:
                return res

            fact_dates = fact_pend["_fc"].sort_values()
            for i, row in abonos.iterrows():
                res.loc[i] = (fact_dates > row["_fc"]).any()

            return res

        # Map a df completo
        flag_post_fact_grp = grp_full.apply(flag_facturas_posteriores_pendientes)
        # grp_full.apply devuelve MultiIndex; lo aplanamos mapeando por índice real:
        # Creamos una serie por index original:
        flag_post_fact = pd.Series(False, index=df.index)
        if isinstance(flag_post_fact_grp, pd.Series):
            # cuando apply retorna Series por grupo, queda con MultiIndex (keys, index)
            # reconstruimos:
            for _, s in flag_post_fact_grp.groupby(level=list(range(len(keys)))):
                # s tiene nivel extra al final (index original)
                s2 = s.droplevel(list(range(len(keys))))
                flag_post_fact.loc[s2.index] = s2.values

        # Si abono antiguo y hay facturas posteriores pendientes => OK contextual
        m_ok_post = abono_antiguo & df["Análisis"].isna() & flag_post_fact
        df.loc[m_ok_post, "Análisis"] = "Ok abono antiguo con facturas posteriores pendientes"

        # Si abono antiguo y NO hay facturas posteriores pendientes => incidencia
        m_inc = abono_antiguo & df["Análisis"].isna() & (~flag_post_fact)
        df.loc[m_inc, "Análisis"] = "Incidencia: abono antiguo sin cruce (sin facturas posteriores pendientes)"

    # Z6: siempre revisar (si no hay análisis asignado ya)
    df.loc[mask_partidas & mask_z6 & df["Análisis"].isna(), "Análisis"] = "Revisar Z6 (finiquitos/reembolsos)"

    #deudora antigua
    df.loc[mask_partidas & mask_deud_antigua, 'Análisis'] = 'Deudora Antigua'

    # Resto de partidas no analizadas
    df.loc[mask_partidas & df["Análisis"].isna(), "Análisis"] = "Ok"
    df.loc[mask_partidas & mask_lm, 'Análisis'] = ""

    # 4) FEATURES A NIVEL PROVEEDOR

    if have_keys:
        SPECIAL_LM = {"40700001", "40010001"}
        lm = df["LibrMay"].astype(str).str.strip() if "LibrMay" in df.columns else pd.Series("", index=df.index)
        bp = df["BP"].astype(str).str.strip() if "BP" in df.columns else pd.Series("", index=df.index)

        is_anticipo_ret = lm.isin(SPECIAL_LM) | bp.eq("A")   # <- si NO quieres BP, quita "| bp.eq('A')"
        mask_partidas_base = mask_partidas & (~is_anticipo_ret)

        part = df.loc[mask_partidas_base, keys + ["ImpteML", "Antigüedad", "antig"] + (["Clase"] if "Clase" in df.columns else [])].copy()
        grp = part.groupby(keys, dropna=False)

        hay_deud_grp     = grp["ImpteML"].apply(lambda s: (s > 0).any())
        hay_acre_grp     = grp["ImpteML"].apply(lambda s: (s < 0).any())
        hay_deud_ant_grp = grp.apply(lambda g: ((g["ImpteML"] > 0) & (g["Antigüedad"] > 31)).any())
        hay_acre_ant_grp = grp.apply(lambda g: ((g["ImpteML"] < 0) & (g["Antigüedad"] > g["antig"])).any())

        if "Clase" in part.columns:
            hay_z6_acre_grp = grp.apply(lambda g: ((g["ImpteML"] < 0) & (g["Clase"].astype(str).eq("Z6"))).any())
            hay_z6_grp      = grp.apply(lambda g: (g["Clase"].astype(str).eq("Z6")).any())
            hay_kg_deud_grp  = grp.apply(lambda g: ((g["ImpteML"] > 0) & (g["Clase"].astype(str).eq("KG"))).any())
            hay_pago_grp     = grp.apply(lambda g: (g["Clase"].astype(str).isin(["KZ", "ZP"])).any())
        else:
            hay_z6_acre_grp = pd.Series(False, index=hay_deud_grp.index)
            hay_z6_grp      = pd.Series(False, index=hay_deud_grp.index)
            hay_kg_deud_grp = pd.Series(False, index=hay_deud_grp.index)
            hay_pago_grp    = pd.Series(False, index=hay_deud_grp.index)

        def _todo_abonos_rec(g):
            deud = g[g["ImpteML"] > 0]
            if deud.empty or ("Clase" not in g.columns):
                return False
            return (deud["Antigüedad"] < 31).all() and deud["Clase"].astype(str).isin(["AB", "KG"]).all()

        todo_abonos_rec_grp = grp.apply(_todo_abonos_rec) if "Clase" in part.columns else pd.Series(False, index=hay_deud_grp.index)

        # Mapeo a filas (idx debe ser MultiIndex from_frame(df[keys]) calculado antes)
        hay_deud     = pd.Series(idx.map(hay_deud_grp), index=df.index).fillna(False).astype(bool)
        hay_acre     = pd.Series(idx.map(hay_acre_grp), index=df.index).fillna(False).astype(bool)
        hay_deud_ant = pd.Series(idx.map(hay_deud_ant_grp), index=df.index).fillna(False).astype(bool)
        hay_acre_ant = pd.Series(idx.map(hay_acre_ant_grp), index=df.index).fillna(False).astype(bool)

        hay_z6_acre  = pd.Series(idx.map(hay_z6_acre_grp), index=df.index).fillna(False).astype(bool)
        hay_z6       = pd.Series(idx.map(hay_z6_grp), index=df.index).fillna(False).astype(bool)

        hay_kg_deud  = pd.Series(idx.map(hay_kg_deud_grp), index=df.index).fillna(False).astype(bool)
        hay_pago     = pd.Series(idx.map(hay_pago_grp), index=df.index).fillna(False).astype(bool)
        todo_abonos_rec = pd.Series(idx.map(todo_abonos_rec_grp), index=df.index).fillna(False).astype(bool)

    saldo_deudor = df["ImpteML"] > 0

    # 5) SOLICITUDES a nivel proveedor (TOTAL)

    # A1/A2: acreedoras antiguas
    mA1 = mask_total & df["Solicitud"].isna() & hay_acre_ant & hay_pago
    df.loc[mA1, "Solicitud"] = "Acreedoras antiguas y existen pagos contabilizados: solicitar su compensación."

    mA2 = mask_total & df["Solicitud"].isna() & hay_acre_ant & (~hay_pago)
    df.loc[mA2, "Solicitud"] = "Acreedoras antiguas sin pagos identificados: confirmar si se pagará o procede ajuste a ingreso."

    # B: Z6 en el proveedor (cualquiera)
    mB = mask_total & df["Solicitud"].isna() & hay_z6
    df.loc[mB, "Solicitud"] = "Existen partidas con clase Z6: revisar compensación/soporte y confirmar tratamiento."

    # C/D: saldo deudor
    mC = mask_total & df["Solicitud"].isna() & saldo_deudor & hay_deud_ant
    df.loc[mC, "Solicitud"] = "Saldo total deudor con partidas deudoras antiguas: solicitar compensación."

    mD = mask_total & df["Solicitud"].isna() & saldo_deudor & hay_deud & hay_acre
    df.loc[mD, "Solicitud"] = "Saldo deudor con partidas deudoras y acreedoras: solicitar compensación."


    # NAunque el saldo total sea acreedor, si hay deudoras con incidencia, debe pedirse explicación
    # Detectamos si dentro del proveedor hay alguna partida deudora con "Incidencia" o Z6 "revisar"
    if have_keys:
        incid_part = df.loc[mask_partidas, ["Análisis"] + keys].copy()
        incid_part["_inc"] = incid_part["Análisis"].astype(str).str.contains("Incidencia", na=False) | incid_part["Análisis"].astype(str).str.contains("Revisar Z6", na=False)
        incid_grp = incid_part.groupby(keys, dropna=False)["_inc"].any()
        inc_map = idx.map(incid_grp).fillna(False).astype(bool)

        mE = mask_total & df["Solicitud"].isna() & (df["ImpteML"] < 0) & inc_map
        df.loc[mE, "Solicitud"] = "Saldo total acreedor pero existen partidas deudoras con incidencia/Z6: solicitar explicación y cruce/compensación."
            
        mF = mask_total & df["Solicitud"].isna() & hay_deud
        df.loc[mF, "Solicitud"] = "Revisar partidas deudoras"

    # Lógica analítica para cuentas saldadas netas cero
    mask_saldado = mask_total & df["Análisis"].eq("Ok saldado")

    # 1) Si está saldado y NO hay nada que revisar => sin solicitud
    mask_saldado_sin_revision = mask_saldado & (~hay_deud) & (~hay_z6)
    df.loc[mask_saldado_sin_revision, "Solicitud"] = pd.NA

    # 2) Si está saldado pero HAY deudoras o Z6
    mask_saldado_con_revision = mask_saldado & (hay_deud | hay_z6)

    # Si ya existía solicitud, prefijar (sin pisar)
    mask_prefijo = mask_saldado_con_revision & df["Solicitud"].notna()
    df.loc[mask_prefijo, "Solicitud"] = ("Saldo total saldado; no obstante, existen partidas a revisar. " + df.loc[mask_prefijo, "Solicitud"].astype(str))

    # Si está vacía y hay Z6, sí generamos solicitud por Z6 (opcional pero útil)
    m_saldado_z6 = mask_saldado_con_revision & df["Solicitud"].isna() & hay_z6
    df.loc[m_saldado_z6, "Solicitud"] = "Saldo total saldado; no obstante, existen partidas con clase Z6 a revisar. Solicitar soporte y confirmar tratamiento/compensación."


    return df

def anticipos_proveedores(df: pd.DataFrame) -> pd.DataFrame:
    """
    Módulo Especializado en el Análisis de Anticipos y Retenciones en Garantía.
    Audita las cuentas contables de alto riesgo operativo mediante NLP analítico heurístico básico.
    
    Parámetros:
    -----------
    df : pd.DataFrame
        Dataset base unificado.
        
    Retorna:
    --------
    pd.DataFrame
        Subconjunto estructurado filtrado únicamente con proveedores con anticipos o retenciones vigentes.
    """

    df = df.copy()

    # 1) Normalizar columnas 
    keys_full = ["Fecha Clave", "Sociedad", "Cuenta", "Nombre1"]    
    keys_prov = ["Fecha Clave", "Sociedad", "Cuenta"]             

    cols_fecha_all = ["Fecha Clave", "Fe_contab", "Venc_neto", "Fecha_doc", "Fecha_pago", "Registrado"]
    for c in cols_fecha_all:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce", dayfirst=True).dt.normalize()

    for c in ["Antigüedad", "Demora", "ImpteML", "antig"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    if "_is_total" not in df.columns:
        df["_is_total"] = 0
    df["_is_total"] = pd.to_numeric(df["_is_total"], errors="coerce").fillna(0).astype(int).clip(0, 1)

    # 2) Procuradores 
    palabras_procurador = ["procurador", "pleito", "judicial", "abogado", "demanda", "litigio", "juzgado"]
    patron_proc = re.compile("|".join(map(re.escape, palabras_procurador)), flags=re.IGNORECASE)

    # 3) Identificar proveedores con anticipo/retención 
    mask_total = df["_is_total"].eq(1)
    mask_partida = df["_is_total"].eq(0)

    # Asegurar columnas
    for colname in ["LibrMay", "Texto"]:
        if colname not in df.columns:
            df[colname] = pd.NA

    lm = df["LibrMay"].astype(str).str.strip()

    # Anticipos (detector): 40700001 o CME A
    mask_lm_anticipo = mask_partida & lm.eq("40700001")

    # Retenciones
    mask_lm_retencion = mask_partida & lm.eq("40010001")

    # Partidas relevantes ( para detectar proveedores objetivo)
    df_part_relevante = df.loc[mask_lm_anticipo| mask_lm_retencion].copy()
    proveedores_obj = df_part_relevante[keys_prov].drop_duplicates()

    # Traemos TODAS las operaciones (partidas + totales) de esos proveedores
    df2 = df.merge(proveedores_obj, on=keys_prov, how="inner")

    # Orden estable
    df2 = df2.sort_values(
        by=["Fecha Clave", "Sociedad", "Cuenta", "_is_total", "Fe_contab", "N_doc"],
        ascending=[True, True, True, True, True, True],
        na_position="last",
        kind="mergesort"
    ).reset_index(drop=True)

    mask_total2 = df2["_is_total"].eq(1)
    mask_partida2 = df2["_is_total"].eq(0)

    # 4) Inicialización columnas salida 
    df2["Etiqueta"] = pd.NA
    df2["Análisis"] = pd.NA
    df2["Solicitud"] = pd.NA

    # 5) Señales objetivables 
    if "Venc_neto" in df2.columns and "Fecha Clave" in df2.columns:
        mask_vencido = df2["Venc_neto"].notna() & df2["Fecha Clave"].notna() & (df2["Venc_neto"] < df2["Fecha Clave"])
    else:
        mask_vencido = pd.Series(False, index=df2.index)

    if "Fecha_pago" in df2.columns:
        mask_sin_pago = df2["Fecha_pago"].isna()
    else:
        mask_sin_pago = pd.Series(False, index=df2.index)

    lm2 = df2["LibrMay"].astype(str).str.strip()

    # Clasificación SOLO en partidas (no en total)
    is_retencion = mask_partida2 & lm2.eq("40010001")
    is_anticipo  = mask_partida2 &  lm2.eq("40700001")

    txt2 = df2["Texto"].astype(str).fillna("").str.strip()
    sin_texto2 = txt2.eq("") | txt2.str.lower().eq("nan")
    procurador2 = txt2.str.contains(patron_proc, na=False)

    # 6) Casuística a nivel partida 
    df2.loc[is_anticipo & df2["Etiqueta"].isna(), "Etiqueta"] = "Anticipos a proveedores"
    df2.loc[is_retencion & df2["Etiqueta"].isna(), "Etiqueta"] = "Retenciones en Garantía"

    # 6.A Anticipo pagado (fallback)
    anticipo_pagado = is_anticipo & df2["Fecha_pago"].notna() if "Fecha_pago" in df2.columns else pd.Series(False, index=df2.index)
    df2.loc[anticipo_pagado & df2["Análisis"].isna(), "Análisis"] = "Anticipo pagado"
    df2.loc[anticipo_pagado & df2["Solicitud"].isna(), "Solicitud"] = "Aportar evidencia del pago y documentación soporte del anticipo"

    # 6.1 Anticipos - procuradores
    m_proc = is_anticipo & procurador2
    df2.loc[m_proc, "Análisis"] = "Fondos a procuradores (anticipo)"
    df2.loc[m_proc, "Solicitud"] = "Revisar: el texto sugiere fondos a procuradores/caso judicial. Solicitar soporte y estado del expediente y evidencia de autorización."

    # 6.2 Anticipos - vencidos según vencimiento SAP
    m_venc = is_anticipo & mask_vencido
    df2.loc[m_venc & df2["Análisis"].isna(), "Análisis"] = "Anticipo fuera de plazo (según vencimiento SAP)"
    df2.loc[m_venc & df2["Solicitud"].isna(), "Solicitud"] = "Revisar: vencimiento en SAP anterior a la Fecha del informe. Confirmar que el anticipo sigue en plazo según contrato/pedido y que el bien/servicio continúa pendiente de recibir. Aportar contrato/pedido, autorización del pago y soporte de seguimiento."

    # 6.3 Anticipos - trazabilidad insuficiente
    m_traza = is_anticipo & sin_texto2
    df2.loc[m_traza & df2["Análisis"].isna(), "Análisis"] = "Anticipo con trazabilidad insuficiente"
    df2.loc[m_traza & df2["Solicitud"].isna(), "Solicitud"] =  "Revisar: anticipo sin descripción suficiente en el extracto. Solicitar contrato/pedido, objeto del anticipo, evidencia de autorización y confirmación de bienes/servicios pendientes de recibir (con soporte)."

    # 6.4 Anticipos - OK (último fallback)
    m_ok_anticipo = is_anticipo & df2["Análisis"].isna()
    df2.loc[m_ok_anticipo, "Análisis"] = "Anticipo (sin indicador objetivo de incidencia en SAP)"
    df2.loc[m_ok_anticipo & df2["Solicitud"].isna(), "Solicitud"] = "Sin indicador objetivo de incidencia en SAP. Requiere verificación documental (contrato/pedido, autorización, bien/servicio pendiente) y plan/fecha de compensación/regularización."

    # 6.5 Retenciones - siempre consultar
    m_ret = is_retencion
    df2.loc[m_ret, "Análisis"] = "Retención en garantía (obra / disputa)"
    df2.loc[m_ret & df2["Solicitud"].isna(), "Solicitud"] = "Solicitar a Administración: confirmar obra en curso o disputa, % retenido, condiciones de liberación, fecha estimada de finalización/recepción y soporte documental (contrato, certificaciones/actas, comunicaciones)."

    # 6.6 TOTAL: saldo total REAL del proveedor (incluye TODAS las partidas del proveedor)
     
    if all(k in df2.columns for k in keys_prov):
        saldo_total_real_grp = df2.loc[mask_partida2].groupby(keys_prov, dropna=False)["ImpteML"].sum()
        # map por fila (solo para las filas TOTAL)
        idx2 = pd.MultiIndex.from_frame(df2[keys_prov])
        saldo_total_map = pd.Series(idx2.map(saldo_total_real_grp), index=df2.index)
        df2.loc[mask_total2, "ImpteML"] = saldo_total_map.loc[mask_total2].values

    # Etiqueta para TOTAL
    df2.loc[mask_total2, "Etiqueta"] = "TOTAL proveedor (saldo real)"

    # 6.7 FILTRO FINAL DE VISUALIZACIÓN
    # - partidas clasificadas como anticipo o retención
    # - la fila TOTAL del proveedor

    df2_show = df2.loc[mask_total2 | is_anticipo | is_retencion].copy()

    columnas = [
        "Fecha Clave", "UE", "Sociedad", "BP", "LibrMay", "Cuenta", "Nombre1", "N_doc", "Clase", "Texto",
        "Fe_contab", "Fecha_doc", "Venc_neto", "Factura", "Fecha_pago",
        "ImpteML", "ML", "Antigüedad", "Demora", "Etiqueta", "Análisis", "Solicitud", "_is_total"
    ]

    df_out = df2_show[[c for c in columnas if c in df2_show.columns]].copy()

    # Fechas a date  
    cols_fecha_out = ["Fecha Clave", "Fe_contab", "Venc_neto", "Fecha_doc", "Fecha_pago"]
    for c in cols_fecha_out:
        if c in df_out.columns:
            df_out[c] = pd.to_datetime(df_out[c], errors="coerce").dt.date

    return df_out

def excel(df: pd.DataFrame, ruta: str) -> str:
    """
    Fase final: Renderizado de evidencias y estructuración del libro de Excel.
    Aplica estilos, formateo condicional de celdas para priorización visual,
    filtros automáticos y escalado de fuentes para su consumo directo por el auditor.
    """
    
    orden_cols= ["Fecha Clave","UE","Sociedad","Cuenta","Nombre1","Asignacion","N_doc","Registrado","Ej_mes","Fe_contab", "Venc_neto", "Fecha_doc","Fecha_pago","Antigüedad", "Texto", "Clase","ImpteML","ML","Casuística","Etiqueta","Análisis","Solicitud","Demora","BP","LibrMay","CPag","Referencia","Factura","antig","_is_total",]

    def activar_filtros_y_congelar(ws):
        """Habilita los filtros dinámicos superiores y congela la fila de cabecera."""
        max_row = ws.max_row
        max_col = ws.max_column
        if max_row < 1 or max_col < 1:
            return

        last_col = get_column_letter(max_col)
        ws.auto_filter.ref = f"A1:{last_col}{max_row}"

        # Congelar fila 1
        ws.freeze_panes = "A2"
        
    def _safe_str_series(s: pd.Series) -> pd.Series:
        return s.astype(str).fillna("").str.strip()

    def aplicar_anchos(ws, df_ref, widths, default_width=15):
        for i, col_name in enumerate(df_ref.columns, start=1):
            col_letter = get_column_letter(i)
            ws.column_dimensions[col_letter].width = widths.get(col_name, default_width)

    def aplicar_formato_fecha(ws, columnas_fecha, formato="DD/MM/YYYY"):
        headers = [cell.value for cell in ws[1]]
        for col_name in columnas_fecha:
            if col_name in headers:
                col_idx = headers.index(col_name) + 1
                col_letter = get_column_letter(col_idx)
                for cell in ws[col_letter][1:]:
                    if cell.value is not None:
                        cell.number_format = formato

    # Ejecución interna del Pipeline secuencial contable
    df_og = df.copy()
    df_proc = preprocess(df_og)
    df_cas = casuistica(df_proc)
    df_cas = df_cas[[c for c in orden_cols if c in df_cas.columns]]

    df_ant = anticipos_proveedores(df_proc)
    df_ant = df_ant[[c for c in orden_cols if c in df_ant.columns]]

    cols_fecha_all = ["Fecha Clave", "Fe_contab", "Venc_neto", "Fecha_doc", "Fecha_pago", "Registrado"]
    for c in cols_fecha_all:
        if c in df_cas.columns:
            df_cas[c] = pd.to_datetime(df_cas[c], errors="coerce").dt.date

    df_cas["Fecha Clave"] = pd.to_datetime(df_cas["Fecha Clave"], errors="coerce").dt.strftime("%d/%m/%Y")

    # ENERACIÓN HOJA "SOLICITUD"
    # Extrae el subconjunto de proveedores con anomalías vigentes para la revisión del Agente IA
    mask_sol = df_cas["Solicitud"].notna() & _safe_str_series(df_cas["Solicitud"]).ne("")
    keys_sol = ["Fecha Clave", "UE", "Sociedad", "Cuenta", "Nombre1"]
    proveedores_con_sol = df_cas.loc[mask_sol, keys_sol].drop_duplicates()
    df_sol = df_cas.merge(proveedores_con_sol, on=keys_sol, how="inner")

    for c in cols_fecha_all:
        if c in df_sol.columns:
            df_sol[c] = pd.to_datetime(df_sol[c], errors="coerce").dt.date

    # Diccionario maestro de anchos de columna estructurado para visualización de informes financieros
    ancho_columnas = {
        "Fecha Clave":14,"UE":15, "Sociedad":8, "Cuenta":10, "Nombre1":23, "N_doc":12, "Registrado":12,
        "Ej_mes":10, "Fe_contab":12, "Venc_neto":12, "Fecha_doc":12, "Antigüedad":8,
        "Texto":35, "Clase":8, "ImpteML":10, "ML":5,"Demora":8, 
        'Referencia':12, 'Factura':12, 'BP':8,"LibrMay": 12, 'CPag':8, "Fecha_pago":12,
         "Casuística":20,"Análisis":50, "Solicitud":65, 'antig': 8, '_is_total':5 }

    os.makedirs(os.path.dirname(ruta) or ".", exist_ok=True)

    def escalar_dict_anchos(widths: dict, scale: float, min_width: float = 4.0) -> dict:
        """Aplica un re-escalado geométrico de fuentes y celdas para optimizar la ergonomía del análisis."""
        out = {}
        for k, v in widths.items():
            try:
                out[k] = max(min_width, float(v) * scale)
            except Exception:
                # Si algún ancho no es numérico, lo dejamos igual
                out[k] = v
        return out

    def aplicar_anchos_por_df(ws, df_ref, widths, default_width=15):
        """
        Aplica anchos basados en df_ref.columns usando dict widths.
        """
        for i, col_name in enumerate(df_ref.columns, start=1):
            col_letter = get_column_letter(i)
            ws.column_dimensions[col_letter].width = widths.get(col_name, default_width)

    def aplicar_escala_hoja(
        ws,df_ref,widths_dict: dict,scale: float = 0.85,
        base_font_size: int = 11,base_row_height: float = 15.0,
        min_font_size: int = 8,min_col_width: float = 4.0,min_row_height: float = 11.0,
        default_width: float = 15.0,zoom: int | None = None,solo_rango_usado: bool = True
    ):
     
        # 1) Escalar anchos
        widths_scaled = escalar_dict_anchos(widths_dict, scale, min_width=min_col_width)
        default_width_scaled = max(min_col_width, default_width * scale)
        aplicar_anchos_por_df(ws, df_ref, widths_scaled, default_width=default_width_scaled)

        # 2) Escalar fuente
        font_size = max(min_font_size, int(round(base_font_size * scale)))
        font_scaled = Font(size=font_size)

        # 3) Escalar altura de filas
        row_h = max(min_row_height, base_row_height * scale)

        # Determinar rango donde aplicar (optimización)
        max_row = ws.max_row if solo_rango_usado else ws.max_row
        max_col = ws.max_column if solo_rango_usado else ws.max_column

        # Aplicar altura filas  
        for r in range(1, max_row + 1):
            ws.row_dimensions[r].height = row_h

        # Aplicar fuente a celdas  
        for row in ws.iter_rows(min_row=1, max_row=max_row, min_col=1, max_col=max_col):
            for cell in row:
                cell.font = Font(
                    name=cell.font.name,
                    bold=cell.font.bold,
                    italic=cell.font.italic,
                    underline=cell.font.underline,
                    color=cell.font.color,
                    size=font_size
                )

        # 4) Zoom
        if zoom is not None:
            ws.sheet_view.zoomScale = zoom

    def aplicar_estilos(ws):

        # 1) Mapear nombres de columnas a índices
        headers = [cell.value for cell in ws[1]]
        col = {h: i + 1 for i, h in enumerate(headers) if h is not None}

        c_is_total = col.get("_is_total")
        c_analisis = col.get("Análisis")
        c_casu     = col.get("Casuística")
        c_clase    = col.get("Clase")
        c_impte    = col.get("ImpteML")
        c_antigued = col.get("Antigüedad")

        if c_is_total is None or c_analisis is None:
            return

        max_row = ws.max_row
        max_col = ws.max_column

        # 2) Definir estilos
        fill_gris   = PatternFill("solid", fgColor="E6E6E6")
        fill_azul   = PatternFill("solid", fgColor="D9E8FF")  # azul suave
        fill_naranja= PatternFill("solid", fgColor="FFD9B3")  # naranja suave

        font_roja   = Font(color="9C0006")  # rojo oscuro legible
        font_bold   = Font(bold=True)

        # 3) Columna "Análisis" azul (todas las filas con datos)
        for r in range(2, max_row + 1):
            ws.cell(row=r, column=c_analisis).fill = fill_azul

        # 4) Fila TOTAL gris (
        for r in range(2, max_row + 1):
            v_total = ws.cell(row=r, column=c_is_total).value
            is_total = str(v_total).strip() == "1"

            if is_total:
                for c in range(1, max_col + 1):
                    cell = ws.cell(row=r, column=c)
                    cell.fill = fill_gris
                    cell.font = font_bold
                continue

            # 5) Reglas por tipo 
            analisis_txt = str(ws.cell(row=r, column=c_analisis).value or "").strip().lower()
            casu_txt     = str(ws.cell(row=r, column=c_casu).value or "").strip().lower() if c_casu else ""
            clase_txt    = str(ws.cell(row=r, column=c_clase).value or "").strip().upper() if c_clase else ""

            # celda en naranja + fuente roja
            def pintar_alerta(row, col_idx):
                if col_idx is None:
                    return
                cell = ws.cell(row=row, column=col_idx)
                cell.fill = fill_naranja
                # Si la celda ya tenía formato especial, lo sobreescribimos a rojo (prioridad alerta)
                cell.font = font_roja

            # Z6: Clase e Importe naranja + letras rojas
            if clase_txt == "Z6" or "revisar z6" in analisis_txt:
                pintar_alerta(r, c_clase)
                pintar_alerta(r, c_impte)
                continue

            # Acreedora antigua: Antigüedad e Importe
            if "acreedora antigua" in analisis_txt or casu_txt == "acreedora antigua":
                pintar_alerta(r, c_antigued)
                pintar_alerta(r, c_impte)
                continue

            # Deudora antigua: Antigüedad e Importe
            if "deudora antigua" in analisis_txt:
                pintar_alerta(r, c_antigued)
                pintar_alerta(r, c_impte)
                continue

            # Deudora general: solo Importe naranja + letras rojas
            if casu_txt == "deudora":
                pintar_alerta(r, c_impte)
                continue

    def aplicar_estilos_anticipos(ws):

        headers = [cell.value for cell in ws[1]]
        col = {h: i + 1 for i, h in enumerate(headers) if h is not None}

        c_is_total = col.get("_is_total")
        c_analisis = col.get("Análisis")
        c_lm       = col.get("LibrMay")
        c_bp       = col.get("BP")
        c_pag = col.get('Fecha_pago')
        c_texto = col.get('Texto')
        c_etiqueta = col.get('Etiqueta')

        if c_is_total is None:
            return

        max_row = ws.max_row
        max_col = ws.max_column

        fill_gris    = PatternFill("solid", fgColor="E6E6E6")
        fill_azul    = PatternFill("solid", fgColor="D9E8FF")
        fill_naranja = PatternFill("solid", fgColor="FFD9B3")

        rojo = Color(rgb="FF9C0006")  # ARGB (más fiable)
        align_center = Alignment(vertical="center", wrap_text=False)

        def tiene_valor(cell):
            v = cell.value
            if v is None:
                return False
            if isinstance(v, str) and v.strip().lower() in ("", "nan", "nat", "none"):
                return False
            return True

        def pintar_alerta(cell):
            cell.fill = fill_naranja
            f = copy(cell.font)
            f.color = rojo
            cell.font = f

        def normalizar_librmay(val) -> str:
            """Convierte 40700001, 40700001.0, '40700001 ' -> '40700001'"""
            if val is None:
                return ""
            if isinstance(val, (int,)):
                return str(val)
            if isinstance(val, float):
                # 40700001.0 -> 40700001
                return str(int(val)) if val.is_integer() else str(val).strip()
            s = str(val).strip()
            # por si viene como '40700001.0' en texto:
            if s.endswith(".0") and s[:-2].isdigit():
                return s[:-2]
            return s

        # 1) Columna "Análisis" azul  
        if c_analisis is not None:
            for r in range(2, max_row + 1):
                ws.cell(row=r, column=c_analisis).fill = fill_azul

        # 2) Reglas fila a fila
        for r in range(2, max_row + 1):
            is_total = str(ws.cell(row=r, column=c_is_total).value).strip() == "1"

            # TOTAL -> gris + negrita
            if is_total:
                for c in range(1, max_col + 1):
                    cell = ws.cell(row=r, column=c)
                    cell.fill = fill_gris
                    f = copy(cell.font)
                    f.bold = True
                    cell.font = f
                    cell.alignment = align_center
                continue
            
            analisis_txt = str(ws.cell(row=r, column=c_analisis).value or "").strip().lower()

            # LibrMay: naranja+rojo si 40700001 o 40010001
            if c_lm is not None:
                cell_lm = ws.cell(row=r, column=c_lm)
                lm_txt = normalizar_librmay(cell_lm.value)
                if lm_txt in ("40700001", "40010001"):
                    pintar_alerta(cell_lm)

            if c_pag is not None:
                cell_pag = ws.cell(row=r, column=c_pag)
                if tiene_valor(cell_pag):
                    pintar_alerta(cell_pag)

            # Resalte analítico avanzado mediante búsquedas de patrones textuales en descripciones
            if "procuradores" in analisis_txt:
                pintar_alerta(ws.cell(row=r, column=c_texto))

            if "trazabilidad" in analisis_txt:
                pintar_alerta(ws.cell(row=r, column=c_texto))

            if "fuera de plazo" in analisis_txt:
                pintar_alerta(ws.cell(row =r, column = col.get('Venc_neto')))
                pintar_alerta(ws.cell(row =r, column = col.get('Fecha Clave')))
                pintar_alerta(ws.cell(row =r, column = col.get('Antigüedad')))

    # ESCRITURA MULTI-PÁGINA PERSISTENTE EN DISCO (OPENPYXL ENGINE)
    with pd.ExcelWriter(ruta, engine="openpyxl") as writer:
        df_og.to_excel(writer, sheet_name="Original", index=False)
        df_cas.to_excel(writer, sheet_name="Analisis", index=False)
        df_sol.to_excel(writer, sheet_name="Solicitud", index=False)
        df_ant.to_excel(writer, sheet_name="Anticipos", index=False)

        wsO  = writer.sheets["Original"]
        wsA  = writer.sheets["Analisis"]
        wsS  = writer.sheets["Solicitud"]
        wsAP = writer.sheets["Anticipos"]

        # Formatos de fecha
        aplicar_formato_fecha(wsO,  [c for c in cols_fecha_all if c in df_og.columns])
        aplicar_formato_fecha(wsA,  [c for c in cols_fecha_all if c in df_cas.columns])
        aplicar_formato_fecha(wsAP, [c for c in cols_fecha_all if c in df_ant.columns])

        cols_fecha_sol = ["Fecha Clave", "Fe_contab", "Fecha_pago", "Registrado"]
        aplicar_formato_fecha(wsS, [c for c in cols_fecha_sol if c in df_sol.columns])

        # Anchos
        aplicar_anchos(wsO,  df_og,  ancho_columnas, default_width=15)
        aplicar_anchos(wsA,  df_cas, ancho_columnas, default_width=15)
        aplicar_anchos(wsS,  df_sol, ancho_columnas, default_width=15)
        aplicar_anchos(wsAP, df_ant, ancho_columnas, default_width=15)

        # Estilos
        aplicar_estilos(wsA)
        aplicar_estilos(wsS)
        aplicar_estilos_anticipos(wsAP)

        # Escala
        scale = 0.85
        aplicar_escala_hoja(wsA,  df_cas, ancho_columnas, scale=scale, zoom=90)
        aplicar_escala_hoja(wsS,  df_sol, ancho_columnas, scale=scale, zoom=90)
        aplicar_escala_hoja(wsAP, df_ant, ancho_columnas, scale=scale, zoom=90)
        aplicar_escala_hoja(wsO,  df_og,  ancho_columnas, scale=scale, zoom=90)

        # # Inyección perimetral de filtros interactivos y congelación de paneles superiores
        activar_filtros_y_congelar(wsO)
        activar_filtros_y_congelar(wsA)
        activar_filtros_y_congelar(wsS)
        activar_filtros_y_congelar(wsAP)