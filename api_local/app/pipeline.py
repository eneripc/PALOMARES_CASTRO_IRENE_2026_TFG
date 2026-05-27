
import os
import pandas as pd
from datetime import datetime
from .config import settings
from .sap_client import call_fbl1n_soap, map_to_fact_pagos
from .hotel_map import resolve_sociedades

import re, json, uuid, shutil, glob, os, requests, pandas as pd, numpy as np, xml.etree.ElementTree as ET, unicodedata
from typing import Optional, List, Dict, Any, Literal, Tuple
import xml.etree.ElementTree as ET
from datetime import datetime
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from openpyxl.utils import get_column_letter
from openpyxl.styles import PatternFill, Font, Alignment
from pathlib import Path


latam = set( ["5001", "5002","5003","5004","5005","5006","5007","5100","5200","5300","5301","5601", "5602","5603","5604","5605","5606","5700","5800","5900","6000","6100","6200", "7200","7300","7400","7402","7601","7800","7801","7900","8100","8201", "M300",
              "H800", "H900","J400","M000","M600","N000","N100","N300","N400","N500","N600","N700","N800", "P000","SV01"])

emea = set(["6400","6800","6700","7100","P400","AJ04","M301","M601","M800","M800","E700","N401","E200","E400","N701","1001","1131","1301","1401","1901","1902","1903","1904","1907","1908","2001","2101","2200","2201","2203","2204","2205","2206","2207","2208","2209",
            "2300","2301","2302","2303","2304","2305","2306","2307","2501","2601","2701","2704","2705","2706","2707","2708","2901","3200","3201","4301","4302","5500","8300","8303","8304","8504","8505","8506","8700","8701","8802","8803","8804","8805","8806","8807",
            "8808","8809","8810","8811","8812","8813","8814","8815","8816","8817","8819","8820","8821","8822","8823","8824","8825","8826","8827","8829","8831","8832","8833","8837","8838","8839","8840", "8901","8902","8903","8904","8905","8906","8907","8908","9001",
            "9002","9003","9004","9006","9007","9101","9301","9600","9800","A301","A302","A303","A801","A802","AD01","AJ00","AJ02","AJ03","CK01","AK01","AL00","AL01","AL02","AL03","AN01","BF00","BF01","BF02","BJ01","BL00","BL01","BM01","BU01","BX01","CB01","H000",
            "MG01","H900","J100","M400","M900","NB01"])

map_soc_UE = {"5600":"Maya","5601":"Maya","5602":"Maya","5603":"Maya","5604":"Maya","6300":"Maya","7000":"Maya","P300":"Maya","5606":"Maya",
            "7400":"Bavaro","7401":"Bavaro","7601":"Bavaro","7800":"Bavaro","7801":"Bavaro","J400":"Bavaro","7402":"Bavaro",
            "8504":"Sants",
            "3200":"Punta Umbria Beach","3201":"Punta Umbria Beach",
            "1001": "Illetas Albatros" } # añadir todas las sociedades

def preprocess(data):
        
    if isinstance(data, pd.DataFrame):
        df = data.copy()
        
    if isinstance(data, (str, Path)):
        path = Path(data)
        if path.suffix.lower() == ".csv":
            df = pd.read_csv(path)
        elif path.suffix.lower() in (".xlsx", ".xls"):
            df = pd.read_excel(path, engine="openpyxl")

    if 'Unnamed: 0' in df.columns:
        df.drop(columns = ['Unnamed: 0'], inplace = True)

    columnas_vacias = df.columns[df.isna().all()]
    df.drop(columns=columnas_vacias, inplace=True)

    def _norm(s: str) -> str:
        """Normaliza nombres para comparar: sin acentos, minúsculas, separadores a '_'."""
        s = "" if s is None else str(s)
        s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
        s = s.strip().lower()
        s = re.sub(r"[^\w]+", "_", s)
        s = re.sub(r"_+", "_", s).strip("_")
        return s

    df["UE"] = df["Sociedad"].astype(str).str.upper().map(map_soc_UE).fillna("OTRO")
    df = df[['UE'] + [c for c in df.columns if c != 'UE']]

    def standardize_columns_simple(df):

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

    df = df.sort_values(by=["Fecha Clave","UE","Sociedad", "Cuenta", "Fe_contab", "N_doc"], ascending=[ True,True,True, True, True, True]).reset_index(drop=True)

    def cpag_to_days(series: pd.Series, default_days: int = 0) -> pd.Series:
        """
        Convierte condiciones tipo '30FF', '60FF', 'NET30', '30D', '030FF' a días (int).
        """
        if series is None:
            return pd.Series(default_days)

        s = series.astype(str).str.upper().str.strip()

        days = s.str.extract(r"(\d+)", expand=False)
        days = pd.to_numeric(days, errors="coerce").fillna(default_days).astype(int)

        return days
    
    # clacular
    for col in ["Fecha_doc","Fe_contab","Registrado","Fecha_pago",'Venc_neto', 'Fecha Clave']:
        df[col] = pd.to_datetime(df[col], errors="coerce").dt.normalize()

    if "CPag" in df.columns:
        cpag_days = cpag_to_days(df["CPag"], default_days=0)
    else:
        cpag_days = pd.Series(0, index=df.index)

    cpag_td = pd.to_timedelta(cpag_days, unit="D")


    #Antigüedad = Fecha informe - (Fe_contab + CPag)
    if "Antigüedad" not in df.columns:
        due_teorico = df["Fe_contab"] + cpag_td
        df["Antigüedad"] = (df["Fecha Clave"] - due_teorico).dt.days
  
    if 'Demora' not in df.columns:
        df['vt menos contable'] = (df["Venc_neto"] - df["Fe_contab"]).dt.days
        df['vt menos contable'].fillna(0)
        df['Demora'] = df['Antigüedad'] - df['vt menos contable']
        df['Demora'].fillna(0)

    if 'Registrado' in df.columns and 'Fecha_doc' in df.columns:
        # Manipulación de fechas (cuántos días cambió la fecha “de documento” respecto a la real)
        df["Delta_fecha_doc"] = (df["Registrado"] - df['Fecha_doc'] ).dt.days
        df["Delta_fecha_doc"].fillna(0)

    totales = (df.groupby(["Fecha Clave","UE","Sociedad", "Cuenta","Nombre1"], as_index=False)["ImpteML"].sum().rename(columns={"ImpteML": "ImpteML"}))

    # Construir filas TOTAL con las mismas columnas que df
    total_rows = pd.DataFrame(columns=df.columns)

    total_rows["Fecha Clave"]  = totales["Fecha Clave"]
    total_rows["UE"]  = totales["UE"]
    total_rows["Sociedad"]  = totales["Sociedad"]
    total_rows["Cuenta"]    = totales["Cuenta"]
    total_rows["Nombre1"] = totales["Nombre1"]
    total_rows["ImpteML"] = totales["ImpteML"]
    total_rows
    df["_is_total"] = 0
    total_rows["_is_total"] = 1

    # Concatenar y ordenar: mismo proveedor + _is_total al final
    df = (pd.concat([df, total_rows], ignore_index=True, sort=False).sort_values(by=["Fecha Clave","UE","Sociedad", "Cuenta", "_is_total", "Fe_contab", "N_doc"], ascending=[True, True,True, True, True, True, True], na_position="last").reset_index(drop=True))

    df["Fecha_pago"] = pd.to_datetime(df["Fecha_pago"], errors="coerce")
    mask_sentinela = df["Fecha_pago"].notna() & (df["Fecha_pago"] <= pd.Timestamp("1900-01-02"))     # Limpia 1899-12-30, 1899-12-31, 1900-01-01, 1900-01-02
    df.loc[mask_sentinela, "Fecha_pago"] = pd.NaT

    df.loc[df["Sociedad"].isin(latam) & df["_is_total"].eq(0), "antig"] = 180
    df.loc[df["Sociedad"].isin(emea) & df["_is_total"].eq(0), "antig"] = 365
    df["antig"] = pd.to_numeric(df["antig"], errors="coerce").fillna(365).astype(int)

    return df

def casuistica(df: pd.DataFrame):

    columnas = ['Fecha Clave','UE','Sociedad', 'Cuenta','Nombre1', 'N_doc',
       'Registrado', 'Ej_mes', 'Fe_contab', 'Venc_neto', 'Fecha_doc',
       'Antigüedad', 'Texto', 'Clase', 'ImpteML', 'ML', 'Demora','Referencia', 'Factura', 'BP', 'CPag','Fecha_pago', 'LibrMay','antig', '_is_total']

    df = df[[c for c in columnas if c in df.columns]].copy()

    SPECIAL_LM = ["40700001", "40010001"]  # 407 anticipos, 40010001 retenciones
    
    lm= df["LibrMay"].astype(str).str.strip()
    df = df[~lm.isin(SPECIAL_LM)].copy()


    # =========================
    # 0) Normalizaciones básicas
    # =========================
    df["ImpteML"]  = pd.to_numeric(df.get("ImpteML"), errors="coerce")
    df["Antigüedad"] = pd.to_numeric(df.get("Antigüedad"), errors="coerce")

    # Normalizar _is_total (muy importante)
    if "_is_total" not in df.columns:
        # Inferencia conservadora: si no hay Nºdoc o Clase, lo tratamos como total-like
        # (ajústalo según tu extract real)
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

    # Inicialización
    df["Casuística"] = pd.NA
    df["Análisis"]   = pd.NA
    df["Solicitud"]  = pd.NA

    # Eliminar filas total-like preexistentes (si procede)
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

    
    # Recalcular saldo total en fila TOTAL
    if have_keys:
        saldo_grp = df.loc[mask_partidas].groupby(keys, dropna=False)["ImpteML"].sum()
        idx = pd.MultiIndex.from_frame(df[keys])
        saldo_map = pd.Series(idx.map(saldo_grp), index=df.index)
        df.loc[mask_total, "ImpteML"] = saldo_map.loc[mask_total].values
    else:
        idx = pd.Index([None]*len(df))

    # Signos
    mask_deud = df["ImpteML"] > 0
    mask_acre = df["ImpteML"] < 0

    # Antigüedad
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

    # =========================
    # 1) ANÁLISIS SALDO TOTAL
    # =========================
    df.loc[mask_total & (df["ImpteML"] < 0), "Análisis"] = "Ok saldo total acreedor"
    df.loc[mask_total & (df["ImpteML"] > 0), "Análisis"] = "Saldo total deudor"
    df.loc[mask_total & (df["ImpteML"] == 0), "Análisis"] = "Ok saldado"

    # =========================
    # 2) CASUÍSTICA PARTIDAS
    # =========================
    df.loc[mask_partidas & mask_acre_antigua, "Casuística"] = "Acreedora antigua"
    df.loc[mask_partidas & mask_acre & df["Casuística"].isna(), "Casuística"] = "Acreedora"
    df.loc[mask_partidas & mask_deud, "Casuística"] = "Deudora"

    # Z6 como casuística específica (no solo acreedoras)
    #df.loc[mask_partidas & mask_z6, "Casuística"] = "Z6 finiquitos/reembolsos"

    # =========================
    # 3) ANÁLISIS PARTIDAS
    # =========================
    # Acreedoras antiguas = incidencia
    df.loc[mask_partidas & mask_acre_antigua, "Análisis"] = "Acreedora antigua"

    # Deudoras: explicar todas
    abono_reciente = mask_partidas & mask_deud & (df["Antigüedad"] < 31) & mask_abono
    df.loc[abono_reciente & df["Análisis"].isna(), "Análisis"] = "Ok abono reciente"

    abono_antiguo = mask_partidas & mask_deud_antigua & mask_abono

    # Para decidir si un abono antiguo está "cubierto" por facturas posteriores pendientes:
    # - requiere Fe.contab. y (opcional) Fecha pago
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

            # Chequeo por abono: existe factura con fc > fc_abono
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

    # =========================
    # 4) FEATURES por proveedor
    # FEATURES por proveedor (flags a nivel proveedor, mapeados a cada fila)
    if not have_keys:
        hay_deud = hay_acre = hay_deud_ant = hay_acre_ant = hay_z6 = hay_z6_acre = hay_kg_deud = hay_pago = todo_abonos_rec = pd.Series(False, index=df.index)
    else:
        part = df.loc[mask_partidas, keys + ["ImpteML", "Antigüedad", "antig"] + (["Clase"] if "Clase" in df.columns else [])].copy()
        grp = part.groupby(keys, dropna=False)

        hay_deud_grp     = grp["ImpteML"].apply(lambda s: (s > 0).any())
        hay_acre_grp     = grp["ImpteML"].apply(lambda s: (s < 0).any())
        hay_deud_ant_grp = grp.apply(lambda g: ((g["ImpteML"] > 0) & (g["Antigüedad"] > 31)).any())
        hay_acre_ant_grp = grp.apply(lambda g: ((g["ImpteML"] < 0) & (g["Antigüedad"] > g['antig'])).any())

        if "Clase" in part.columns:
            hay_z6_acre_grp = grp.apply(lambda g: ((g["ImpteML"] < 0) & (g["Clase"].astype(str).eq("Z6"))).any())
            hay_z6_grp      = grp.apply(lambda g: (g["Clase"].astype(str).eq("Z6")).any())  # <- Z6 CUALQUIERA
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

        # Mapeo a filas
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

    
    # =========================
    # 5) SOLICITUDES a nivel proveedor (TOTAL)
    # =========================
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

   

    # NUEVO: aunque el saldo total sea acreedor, si hay deudoras con incidencia, debe pedirse explicación
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

    # Si saldado => no solicitud
    mask_saldado = mask_total & df["Análisis"].eq("Ok saldado")

    # 1) Si está saldado y NO hay nada que revisar => sin solicitud
    mask_saldado_sin_revision = mask_saldado & (~hay_deud) & (~hay_z6)
    df.loc[mask_saldado_sin_revision, "Solicitud"] = pd.NA

    # 2) Si está saldado pero HAY deudoras o Z6
    mask_saldado_con_revision = mask_saldado & (hay_deud | hay_z6)

    # Si ya existía solicitud, prefijar (sin pisar)
    mask_prefijo = mask_saldado_con_revision & df["Solicitud"].notna()
    df.loc[mask_prefijo, "Solicitud"] = (
        "Saldo total saldado; no obstante, existen partidas a revisar. "
        + df.loc[mask_prefijo, "Solicitud"].astype(str)
    )

    # Si está vacía y hay Z6, sí generamos solicitud por Z6 (opcional pero útil)
    m_saldado_z6 = mask_saldado_con_revision & df["Solicitud"].isna() & hay_z6
    df.loc[m_saldado_z6, "Solicitud"] = (
        "Saldo total saldado; no obstante, existen partidas con clase Z6 a revisar. "
        "Solicitar soporte y confirmar tratamiento/compensación."
    )

    # Si ya existía solicitud, solo prefijamos el contexto (sin pisar lo anterior)
    mask_prefijo = mask_saldado_con_revision & df["Solicitud"].notna()
    df.loc[mask_prefijo, "Solicitud"] = (
        "Saldo total saldado; no obstante, existen partidas a revisar. "
        + df.loc[mask_prefijo, "Solicitud"].astype(str)
    )

    # Limpieza final

    return df

def anticipos_proveedores(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # 1) Normalizar columnas ------------------------------------------------------------------------------------------------------------
    keys_full = ["Fecha Clave", "Sociedad", "Cuenta", "Nombre1"]   # para grouping/report
    keys_prov = ["Fecha Clave", "Sociedad", "Cuenta"]             # para traer TODAS las operaciones del proveedor (más robusto)

    cols_fecha_all = ["Fecha Clave", "Fe_contab", "Venc_neto", "Fecha_doc", "Fecha_pago", "Registrado"]
    for c in cols_fecha_all:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce", dayfirst=True).dt.normalize()

    for c in ["Antigüedad", "Demora", "ImpteML", "antig"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # Si no existe _is_total, asumimos todo partida
    if "_is_total" not in df.columns:
        df["_is_total"] = 0

    # 2) Procuradores ------------------------------------------------------------------------------------------------------------
    palabras_procurador = ["procurador", "pleito", "judicial", "abogado", "demanda", "litigio", "juzgado"]
    patron_proc = re.compile("|".join(map(re.escape, palabras_procurador)), flags=re.IGNORECASE)

    # 3) Identificar proveedores con anticipo/retención ------------------------------------------------------------------------------
    mask_total = df["_is_total"].eq(1)
    mask_partida = df["_is_total"].eq(0)

    # Asegurar columnas
    for colname in ["LibrMay", "Texto"]:
        if colname not in df.columns:
            df[colname] = pd.NA

    lm = df["LibrMay"].astype(str).str.strip()

    # Anticipos:
    mask_lm_anticipo = mask_partida & lm.eq("40700001")

    # Retenciones:
    mask_lm_retencion = mask_partida & lm.eq("40010001")

    # Partidas relevantes (solo para detectar proveedores objetivo)
    df_part_relevante = df.loc[ mask_lm_anticipo | mask_lm_retencion].copy()

    print(f"{len(df.loc[mask_lm_anticipo])} partidas de anticipos a proveedores")
    print(f"{len(df.loc[mask_lm_retencion])} partidas de retenciones en garantía")

    # Proveedores objetivo (clave robusta sin Nombre1)
    proveedores_obj = df_part_relevante[keys_prov].drop_duplicates()

    # AQUÍ está el cambio: traemos TODAS las operaciones (partidas + total) de esos proveedores
    df2 = df.merge(proveedores_obj, on=keys_prov, how="inner")

    # Orden
    df2 = df2.sort_values(by=["Fecha Clave", "Sociedad", "Cuenta"], ascending=[True, True, True],
                          na_position="last", kind="mergesort").reset_index(drop=True)

    mask_total2 = df2["_is_total"].eq(1)
    mask_partida2 = df2["_is_total"].eq(0)

    # 4) Inicialización columnas salida ------------------------------------------------------------------------------------------------------------
    df2["Etiqueta"] = pd.NA
    df2["Análisis"] = pd.NA
    df2["Solicitud"] = pd.NA

    # 5) Señales objetivables ------------------------------------------------------------------------------------------------------------
    # (Evita romper si no existen)
    if "Venc_neto" in df2.columns and "Fecha Clave" in df2.columns:
        mask_vencido = df2["Venc_neto"].notna() & df2["Fecha Clave"].notna() & (df2["Venc_neto"] < df2["Fecha Clave"])
    else:
        mask_vencido = pd.Series(False, index=df2.index)

    if "Fecha_pago" in df2.columns:
        mask_sin_pago = df2["Fecha_pago"].isna()
    else:
        mask_sin_pago = pd.Series(False, index=df2.index)

    lm2 = df2["LibrMay"].astype(str).str.strip()
    bp2 = df2["BP"].astype(str).str.strip()

    # IMPORTANTE: solo clasificamos como anticipo/retención en partidas, no en totales
    is_retencion = mask_partida2 & lm2.eq("40010001")
    is_anticipo = mask_partida2 & (~lm2.eq("40010001")) & (bp2.eq("A") | lm2.eq("40700001"))

    txt2 = df2["Texto"].astype(str).fillna("").str.strip()
    sin_texto2 = txt2.eq("") | txt2.str.lower().eq("nan")
    procurador2 = txt2.str.contains(patron_proc, na=False)

    # 6) Casuística a nivel partida ------------------------------------------------------------------------------------------------------------

    df2.loc[is_anticipo & df2["Etiqueta"].isna(), "Etiqueta"] = "Anticipos a proveedores"
    df2.loc[is_retencion & df2["Etiqueta"].isna(), "Etiqueta"] = "Retenciones en Garantía"

    # 6.A Anticipo pagado (fallback, SOLO si aún no hay análisis)
    anticipo_pagado = is_anticipo & df2["Fecha_pago"].notna() if "Fecha_pago" in df2.columns else pd.Series(False, index=df2.index)
    df2.loc[anticipo_pagado & df2["Análisis"].isna(), "Análisis"] = "Anticipo pagado"
    df2.loc[anticipo_pagado & df2["Solicitud"].isna(), "Solicitud"] =  "Aportar evidencia del pago y documentación soporte del anticipo"

    # 6.1 Anticipos - procuradores (prioridad alta)
    m_proc = is_anticipo & procurador2
    df2.loc[m_proc, "Análisis"] = "Fondos a procuradores (anticipo)"
    df2.loc[m_proc, "Solicitud"] =  "Revisar: el texto sugiere fondos a procuradores/caso judicial. Solicitar soporte y estado del expediente y evidencia de autorización."
    
    # 6.2 Anticipos - vencidos según vencimiento SAP
    m_venc = is_anticipo & mask_vencido
    df2.loc[m_venc & df2["Análisis"].isna(), "Análisis"] = "Anticipo fuera de plazo (según vencimiento SAP)"
    df2.loc[m_venc & df2["Solicitud"].isna(), "Solicitud"] = "Revisar: vencimiento en SAP anterior a la Fecha del informe. Confirmar que el anticipo sigue en plazo según contrato/pedido y que el bien/servicio continúa pendiente de recibir. Aportar contrato/pedido, autorización del pago y soporte de seguimiento. "

    # 6.3 Anticipos - trazabilidad insuficiente
    m_traza = is_anticipo & sin_texto2
    df2.loc[m_traza & df2["Análisis"].isna(), "Análisis"] = "Anticipo con trazabilidad insuficiente"
    df2.loc[m_traza & df2["Solicitud"].isna(), "Solicitud"] = "Revisar: anticipo sin descripción suficiente en el extracto. Solicitar contrato/pedido, objeto del anticipo,evidencia de autorización y confirmación de bienes/servicios pendientes de recibir (con soporte)."

    # 6.4 Anticipos - OK (último fallback)
    m_ok_anticipo = is_anticipo & df2["Análisis"].isna()
    df2.loc[m_ok_anticipo, "Análisis"] = "Anticipo (sin indicador objetivo de incidencia en SAP)"
    df2.loc[m_ok_anticipo & df2["Solicitud"].isna(), "Solicitud"] =  "Sin indicador objetivo de incidencia en SAP. Requiere verificación documental (contrato/pedido, autorización, bien/servicio pendiente) y plan/fecha de compensación/regularización."

    # 6.5 Retenciones - siempre consultar
    m_ret = is_retencion
    df2.loc[m_ret, "Análisis"] = "Retención en garantía (obra / disputa)"
    df2.loc[m_ret & df2["Solicitud"].isna(), "Solicitud"] = "Solicitar a Administración: confirmar obra en curso o disputa, % retenido, condiciones de liberación, fecha estimada de finalización/recepción y soporte documental (contrato, certificaciones/actas, comunicaciones)."

    # 7) Selección final columnas --------------------------------------------------------------------------------------
    columnas = ["Fecha Clave", "UE", "Sociedad", "BP", "LibrMay", "Cuenta", "Nombre1", "N_doc", "Clase", "Texto",  "Fe_contab", "Fecha_doc", "Venc_neto", "Factura", "Fecha_pago", "ImpteML", "ML", "Antigüedad", "Demora", "Etiqueta", "Análisis", "Solicitud", "_is_total"]

    df_out = df2[[c for c in columnas if c in df2.columns]].copy()

    cols_fecha_out = ["Fecha Clave", "Fe_contab", "Venc_neto", "Fecha_doc", "Fecha_pago"]
    for c in cols_fecha_out:
        if c in df_out.columns:
            df_out[c] = pd.to_datetime(df_out[c], errors="coerce").dt.date

    return df_out


def excel(df: pd.DataFrame, ruta: str) -> str:

    orden_cols= ["Fecha Clave","UE","Sociedad","Cuenta","Nombre1","Asignacion","N_doc","Registrado","Ej_mes","Fe_contab", "Venc_neto", "Fecha_doc","Fecha_pago","Antigüedad", "Texto", "Clase","ImpteML","ML","Casuística","Etiqueta","Análisis","Solicitud","Demora","BP","CPag","Referencia","Factura","antig","_is_total",]

    def _safe_str_series(s: pd.Series) -> pd.Series:
        return (s.astype("string")
                .fillna("")
                .str.replace(r"\s+", " ", regex=True)
                .str.strip())

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

    # 2) Hoja Solicitud: incluir TODAS las filas de las cuentas que tengan alguna solicitud
    mask_sol = df_cas["Solicitud"].notna() & _safe_str_series(df_cas["Solicitud"]).ne("")

    # claves a nivel proveedor (y por informe)
    keys_sol = ["Fecha Clave", "UE", "Sociedad", "Cuenta", "Nombre1"]

    proveedores_con_sol = df_cas.loc[mask_sol, keys_sol].drop_duplicates()

    df_sol = df_cas.merge(proveedores_con_sol, on=keys_sol, how="inner")

    # (Opcional pero recomendable) asegurar también en df_sol
    for c in cols_fecha_all:
        if c in df_sol.columns:
            df_sol[c] = pd.to_datetime(df_sol[c], errors="coerce").dt.date

    ancho_columnas = {
        "Fecha Clave":14,"UE":15, "Sociedad":8, "Cuenta":10, "Nombre1":23, "N_doc":12, "Registrado":12,
        "Ej_mes":10, "Fe_contab":12, "Venc_neto":12, "Fecha_doc":12, "Antigüedad":8,
        "Texto":35, "Clase":8, "ImpteML":10, "ML":5,"Demora":8, 
        'Referencia':12, 'Factura':12, 'BP':8, 'CPag':8, "Fecha_pago":12,
         "Casuística":18,"Análisis":35, "Solicitud":55, 'antig': 8, '_is_total':5 } #"Demora":10,

    os.makedirs(os.path.dirname(ruta) or ".", exist_ok=True)

    def escalar_dict_anchos(widths: dict, scale: float, min_width: float = 4.0) -> dict:
 
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

        # Aplicar altura filas (desde 1 para incluir cabecera si quieres)
        for r in range(1, max_row + 1):
            ws.row_dimensions[r].height = row_h

        # Aplicar fuente a celdas (si solo quieres "Analisis" y "Solicitud", aplica allí)
        for row in ws.iter_rows(min_row=1, max_row=max_row, min_col=1, max_col=max_col):
            for cell in row:
                # OJO: esto sobrescribe tamaño de fuente previo.
                # Si luego pintas filas (TOTAL en negrita), la negrita seguirá si la reasignas después.
                cell.font = Font(
                    name=cell.font.name,
                    bold=cell.font.bold,
                    italic=cell.font.italic,
                    underline=cell.font.underline,
                    color=cell.font.color,
                    size=font_size
                )

        # 4) Zoom opcional (esto NO cambia tamaños reales, solo la vista)
        if zoom is not None:
            ws.sheet_view.zoomScale = zoom

    def aplicar_estilos(ws):

        # ---------------------------
        # 1) Mapear nombres de columnas a índices
        headers = [cell.value for cell in ws[1]]
        col = {h: i + 1 for i, h in enumerate(headers) if h is not None}

        # Columnas necesarias
        c_is_total = col.get("_is_total")
        c_analisis = col.get("Análisis")
        c_casu     = col.get("Casuística")
        c_clase    = col.get("Clase")
        c_impte    = col.get("ImpteML")
        c_antigued = col.get("Antigüedad")

        # Si faltan columnas críticas, salimos sin romper
        if c_is_total is None or c_analisis is None:
            return

        max_row = ws.max_row
        max_col = ws.max_column

        # -----------------------------
        # 2) Definir estilos
        fill_gris   = PatternFill("solid", fgColor="E6E6E6")
        fill_azul   = PatternFill("solid", fgColor="D9E8FF")  # azul suave
        fill_naranja= PatternFill("solid", fgColor="FFD9B3")  # naranja suave

        font_roja   = Font(color="9C0006")  # rojo oscuro legible
        font_bold   = Font(bold=True)

        # -----------------------------
        # 3) Columna "Análisis" azul (todas las filas con datos)
        for r in range(2, max_row + 1):
            ws.cell(row=r, column=c_analisis).fill = fill_azul

        # -----------------------------
        # 4) Regla: Fila TOTAL gris (y opcional negrita)
        for r in range(2, max_row + 1):
            v_total = ws.cell(row=r, column=c_is_total).value
            is_total = str(v_total).strip() == "1"

            if is_total:
                for c in range(1, max_col + 1):
                    cell = ws.cell(row=r, column=c)
                    cell.fill = fill_gris
                    cell.font = font_bold

                # Importante: aunque pintemos la fila, mantenemos la columna Análisis azul?
                # Tu requisito dice "toda la fila total gris", así que gris manda.
                continue

            # -----------------------------
            # 5) Reglas por tipo (solo NO-TOTAL)
            analisis_txt = str(ws.cell(row=r, column=c_analisis).value or "").strip().lower()
            casu_txt     = str(ws.cell(row=r, column=c_casu).value or "").strip().lower() if c_casu else ""
            clase_txt    = str(ws.cell(row=r, column=c_clase).value or "").strip().upper() if c_clase else ""

            # Helper para pintar una celda en naranja + fuente roja
            def pintar_alerta(row, col_idx):
                if col_idx is None:
                    return
                cell = ws.cell(row=row, column=col_idx)
                cell.fill = fill_naranja
                # Si la celda ya tenía formato especial, lo sobreescribimos a rojo (prioridad alerta)
                cell.font = font_roja

            # ---- (A) Z6: Clase e Importe naranja + letras rojas
            if clase_txt == "Z6" or "revisar z6" in analisis_txt:
                pintar_alerta(r, c_clase)
                pintar_alerta(r, c_impte)
                # Z6 es muy prioritario; no necesitamos seguir evaluando más reglas
                continue

            # ---- (B) Acreedora antigua: Antigüedad e Importe
            # Puede venir en Casuística o en Análisis
            if "acreedora antigua" in analisis_txt or casu_txt == "acreedora antigua":
                pintar_alerta(r, c_antigued)
                pintar_alerta(r, c_impte)
                continue

            # ---- (C) Deudora antigua: Antigüedad e Importe
            if "deudora antigua" in analisis_txt:
                pintar_alerta(r, c_antigued)
                pintar_alerta(r, c_impte)
                continue

            # ---- (D) Deudora general: solo Importe naranja + letras rojas
            if casu_txt == "deudora":
                pintar_alerta(r, c_impte)
                continue

    def aplicar_estilos_anticipos(ws, total_row_height=None):
    

        # 1) Mapear columnas
        headers = [cell.value for cell in ws[1]]
        col = {h: i + 1 for i, h in enumerate(headers) if h is not None}

        c_is_total = col.get("_is_total")
        c_analisis = col.get("Análisis")
        c_etiqueta = col.get("Etiqueta")
        c_texto    = col.get("Texto")
        c_impte    = col.get("ImpteML")
        c_antigued = col.get("Antigüedad")
        c_venc     = col.get("Venc_neto")

        # Si falta lo mínimo, salimos
        if c_is_total is None:
            return

        max_row = ws.max_row
        max_col = ws.max_column

        # 2) Estilos
        fill_gris    = PatternFill("solid", fgColor="E6E6E6")
        fill_azul    = PatternFill("solid", fgColor="D9E8FF")  # azul suave
        fill_naranja = PatternFill("solid", fgColor="FFD9B3")  # naranja suave

        font_roja = Font(color="9C0006")   # rojo oscuro legible
        font_bold = Font(bold=True)

        align_center = Alignment(vertical="center", wrap_text=False)

        # 3) Columna "Análisis" azul (si existe)
        if c_analisis is not None:
            for r in range(2, max_row + 1):
                ws.cell(row=r, column=c_analisis).fill = fill_azul

        # 4) Reglas fila a fila
        for r in range(2, max_row + 1):

            # TOTAL
            v_total = ws.cell(row=r, column=c_is_total).value
            is_total = str(v_total).strip() == "1"
            if is_total:
                if total_row_height is not None:
                    ws.row_dimensions[r].height = total_row_height

                for c in range(1, max_col + 1):
                    cell = ws.cell(row=r, column=c)
                    cell.fill = fill_gris
                    cell.font = Font(
                        name=cell.font.name,
                        size=cell.font.size,
                        bold=True,
                        italic=cell.font.italic,
                        underline=cell.font.underline,
                        color=cell.font.color
                    )
                    cell.alignment = align_center
                continue

    with pd.ExcelWriter(ruta, engine="openpyxl") as writer:
        df_og.to_excel(writer, sheet_name="Original", index=False)
        df_cas.to_excel(writer, sheet_name="Analisis", index=False)
        df_sol.to_excel(writer, sheet_name="Solicitud", index=False)
        df_ant.to_excel(writer, sheet_name="Anticipos", index=False)

        wsO = writer.sheets["Original"]
        wsA = writer.sheets["Analisis"]
        wsS = writer.sheets["Solicitud"]
        wsAP = writer.sheets["Anticipos"]

        # -------------------------
        # Formatos de fecha (por hoja)
        aplicar_formato_fecha(wsO, [c for c in cols_fecha_all if c in df_og.columns])

        # OJO: wsA tiene df_cas, no df_proc
        aplicar_formato_fecha(wsA, [c for c in cols_fecha_all if c in df_cas.columns])
        aplicar_formato_fecha(wsAP, [c for c in cols_fecha_all if c in df_ant.columns])

        cols_fecha_sol = ["Fecha Clave", "Fe_contab", "Fecha_pago", "Registrado"]
        aplicar_formato_fecha(wsS, [c for c in cols_fecha_sol if c in df_sol.columns])

        # -------------------------
        # Anchos (usar df que corresponde a cada hoja)
        aplicar_anchos(wsO, df_og,  ancho_columnas, default_width=15)
        aplicar_anchos(wsA, df_cas, ancho_columnas, default_width=15)
        aplicar_anchos(wsS, df_sol, ancho_columnas, default_width=15)
        aplicar_anchos(wsAP, df_ant, ancho_columnas, default_width=15)

              # -------------------------
        # Estilos
        aplicar_estilos(wsA)
        aplicar_estilos(wsS)
    
        aplicar_estilos_anticipos(wsAP, total_row_height=None)


        # -------------------------
        # Escala proporcional (ANTES de estilos, para que estilos manden)
        scale = 0.85
        aplicar_escala_hoja(wsA, df_cas, ancho_columnas, scale=scale, zoom=90)
        aplicar_escala_hoja(wsS, df_sol, ancho_columnas, scale=scale, zoom=90)
        aplicar_escala_hoja(wsAP, df_ant, ancho_columnas, scale=scale, zoom=90)
        aplicar_escala_hoja(wsO, df_og, ancho_columnas, scale=scale, zoom=90)


        # -------------------------
        # Freeze panes y filtros
        for ws in [wsO, wsA, wsS, wsAP]:
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions


def build_fbl1n_fact(req) -> pd.DataFrame:
    sociedades = resolve_sociedades(req.hotel, req.sociedades)
    fact_all = []

    for soc in sociedades:
        df_tmp = call_fbl1n_soap(req.variante, req.clase, req.status, req.fecha_low, req.fecha_high, soc)
        df_fact = map_to_fact_pagos(df_tmp, req.fecha_high)
        fact_all.append(df_fact)

    if not fact_all:
        return pd.DataFrame()

    return pd.concat(fact_all, ignore_index=True)

def run_analitica(df_fact: pd.DataFrame, req):
    df_proc = preprocess(df_fact)

    df_cas = None
    if req.analitica.casuistica:
        df_cas = casuistica(df_proc)

    df_ant = None
    if req.analitica.anticipos:
        df_ant = anticipos_proveedores(df_proc)

    return df_proc, df_cas, df_ant

def generate_excel(df_fact: pd.DataFrame, req, out_dir: str) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    target_name = f"FBL1N_{req.hotel or 'SOC'}_{req.fecha_high}_{ts}.xlsx".replace(" ", "_")
    path = os.path.join(out_dir, target_name)
    excel(df_fact, path)  # tu función excel(df, ruta) devuelve ruta/str; la usamos tal cual
    return path
