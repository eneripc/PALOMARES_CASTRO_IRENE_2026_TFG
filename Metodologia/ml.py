import pandas as pd 
from typing import Dict
import numpy as np
import os
import seaborn as sns
import matplotlib.pyplot as plt
from sklearn.preprocessing import StandardScaler, RobustScaler
from sklearn.ensemble import IsolationForest, RandomForestRegressor, RandomForestClassifier
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.metrics import silhouette_score, mean_absolute_error, r2_score, f1_score, confusion_matrix, mean_squared_error
from sklearn.decomposition import PCA
import joblib
from sklearn.model_selection import GridSearchCV, RandomizedSearchCV, train_test_split
from treeinterpreter import treeinterpreter as ti
from prophet import Prophet
from statsmodels.tsa.statespace.sarimax import SARIMAX
import pmdarima as pm
import matplotlib.dates as mdates
import warnings
from urllib3.exceptions import InsecureRequestWarning
warnings.filterwarnings("ignore", category=InsecureRequestWarning)
from statsmodels.tsa.stattools import adfuller
from statsmodels.graphics.tsaplots import plot_acf, plot_pacf
from statsmodels.tsa.holtwinters import ExponentialSmoothing
import contextlib, io
import math
from openpyxl.utils import get_column_letter


from functions import preprocess, casuistica, anticipos_proveedores

def propagar_solicitud_proveedor(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()

    if "_is_total" not in d.columns:
        # si no hay totales no se puede propagar
        d["REQ_DOC"] = 0
        d["Solicitud_prov"] = ""
        return d

    keys = [k for k in ["Fecha Clave", "Sociedad", "Cuenta"] if k in d.columns]
    if not keys:
        d["REQ_DOC"] = 0
        d["Solicitud_prov"] = ""
        return d

    tot = d[d["_is_total"].eq(1)].copy()
    tot["Solicitud"] = tot.get("Solicitud", pd.Series("", index=tot.index)).astype(str).fillna("").str.strip()

    sol_map = tot.set_index(keys)["Solicitud"]
    idx = pd.MultiIndex.from_frame(d[keys])

    d["Solicitud_prov"] = idx.map(sol_map).fillna("")
    d["REQ_DOC"] = (d["Solicitud_prov"].astype(str).str.strip() != "").astype(int)

    return d

def case_score(df):
    df = df.copy()
    df = preprocess(df)
    d = casuistica(df)
    cas = d["Casuística"].astype(str).fillna("").str.strip().str.lower()
    ana = d["Análisis"].astype(str).fillna("").str.strip().str.lower()

    # 1) Score base por Casuística
    base_map = {
        "acreedora antigua": 0.75,
        "z6 finiquitos/reembolsos": 0.65,
        "deudora": 0.45,
        "acreedora": 0.35,
        # si tienes más etiquetas, añádelas aquí
    }

    d["CASE_SCORE"] = cas.map(base_map).fillna(0.0)

    # 2) Overrides por Análisis (prioridad)
    # - Incidencia: mínimo 0.85
    # - Revisar: mínimo 0.60
    is_incidencia = ana.str.contains("incidencia", na=False)
    is_revisar    = ana.str.contains("revisar", na=False)

    d.loc[is_revisar, "CASE_SCORE"] = np.maximum(d.loc[is_revisar, "CASE_SCORE"], 0.60)
    d.loc[is_incidencia, "CASE_SCORE"] = np.maximum(d.loc[is_incidencia, "CASE_SCORE"], 0.85)

    # (Opcional) Si quieres castigar "saldo total deudor" en filas total:
    d.loc[(d.get("_is_total",0)==1) & ana.str.contains("saldo total deudor"), "CASE_SCORE"] = 0.70

    # 3) Normalizar 0..1
    d["CASE_SCORE"] = pd.to_numeric(d["CASE_SCORE"], errors="coerce").fillna(0).clip(0, 1)
    df.drop(columns = ['_is_total'], inplace = True)
    return d

# PREPROCESAMIENTO -----------------------------------------------------------------------------------------------------------------------------------------

def zero_shot(df):
    # clasificacion textual del tipo de riesgo de la partida
    df = df.copy()

    CAMPOS_TEXTO = ["Texto", "Clase", "Referencia",  "N_doc", "Solicitud"]
    CAMPOS_CTX = ["Sociedad","UE","Cuenta","CPag","Demora","Fecha_doc","Registrado","ImpteML"]

    # Etiquetas de RIESGO 
    risk_labels = [
        "Pago duplicado o similar",
        "Texto o referencia ambigua",
        "Urgencia inusual",
        "Fecha fuera de periodo",
        "Términos de pago atípicos",
        "Proveedor sensible",
        "Posible fraccionamiento de pagos",
        "Cambio de forma de pago",
        "Cumple normalidad"
    ]

    # Descripciones adicionales para ampliar los prompts de hipotesi
    risk_desc = {
        "Pago duplicado o similar": "posible duplicado, repetido, doble, mismo importe y fecha, referencia parecida",
        "Texto o referencia ambigua": "texto genérico, poco claro, descripción no informativa",
        "Urgencia inusual": "urgente, prioridad alta, pagar hoy, emergencia",
        "Fecha fuera de periodo": "fecha no coincide, fuera de ciclo, fuera de periodo esperado",
        "Términos de pago atípicos": "condiciones inusuales, CPag extraño, plazos no habituales",
        "Proveedor sensible": "proveedor de riesgo, histórico conflictivo",
        "Posible fraccionamiento de pagos": "varios pagos pequeños para evitar control, dividir facturas",
        "Cambio de forma de pago": "cambio o nuevo CPag",
        "Cumple normalidad": "operación normal, sin señales de riesgo"
    }

    def build_row_text(row):
        # texto principal para Construir texto por fila
        t = " ".join(
            str(row[c]) for c in CAMPOS_TEXTO
            if c in df.columns and pd.notna(row[c])
        )

        # contexto
        ctx = " ".join(
            f"{c}={row[c]}" for c in CAMPOS_CTX
            if c in df.columns and pd.notna(row[c])
        )

        return (t + " " + ctx).strip()

    df["Texto_zs"] = df.apply(build_row_text, axis=1).fillna("")

    # Crea un prompt por etiqueta
    prompts = [
        f"Este texto trata sobre {lbl}. {risk_desc[lbl]}"
        for lbl in risk_labels
    ]

    #  Ajustar vectorizador sobre textos + prompts
    corpus = df["Texto_zs"].tolist() + prompts
    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3,5))
    X = vec.fit_transform(corpus)

    n = len(df)
    X_text = X[:n]      # facturas
    X_labels = X[n:]    # prompts

    sims = cosine_similarity(X_text, X_labels) # similaridad coseno
    max_idx = sims.argmax(axis=1)
    # asignar etiqueta y score
    df["zs_label"] = [risk_labels[i] for i in max_idx]
    df["zs_score"] = [float(sims[i, max_idx[i]]) for i in range(n)]

    df.drop(columns = ['Texto_zs'], inplace = True)

    return df

# ML NO SUPERVISADO -----------------------------------------------------------------------------------------------------------------------------------------
def detectar_duplicados(df, importe_tol=1, dias_tol=3, sim_tol=0.70):
    # posibles duplicados en partidas segun el importe, rango de fecha y similitud textual
    df_out = df.copy() # dataframe destino
    df_work = df.copy() #dataframe temporal para transformaciones y calculos intermedios

    df_work["ImpteML"]    = pd.to_numeric(df_work["ImpteML"], errors="coerce").fillna(0)
    df_work["Fecha_doc"] = pd.to_datetime(df_work["Fecha_doc"], errors="coerce")
    df_work["Registrado"] = pd.to_datetime(df_work["Registrado"], errors="coerce")

    cols_texto = [c for c in ["Texto", "Referencia", "Análisis","Solicitud"] if c in df_work.columns] # columnas de texto

    def safe_join(row): # combinacion de las columnas de texto
        return " ".join("" if pd.isna(v) else str(v) for v in row).strip()

    df_work["texto_dup"] = df_work[cols_texto].apply(safe_join, axis=1)

    df_out["Duplicado_score"] = 0.0
    df_out["Duplicado"] = 0

    # vectorizacion del texto con TF-IDF
    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3,5))
    X = vec.fit_transform(df_work["texto_dup"])

    # Iterar por proveedor en la misma UE (comparaciones solo dentro del mismo grupo)
    for (ue, prov), grp in df_work.groupby(["UE","Cuenta"], sort=False):

        n = len(grp)
        if n < 2:  #Si solo hay 1 factura, no hay con qué comparar → saltamos
            continue

        idx_grp = grp.index.to_numpy()
        imp = grp["ImpteML"].to_numpy()
        fechas = grp["Fecha_doc"].to_numpy()
        fechas_reg = grp["Registrado"].to_numpy()

        # Ordenar por importe para usar una ventana que limita comparaciones por tolerancia de importes
        args = np.argsort(imp)
        idx_sorted = idx_grp[args] #ordenar indices importes y fechas segun ese orden
        imp_sorted = imp[args]
        fecha_sorted = fechas[args]
        reg_sorted = fechas_reg[args]

        X_sub = X[args]   # Extraer la sub-matriz TF-IDF en el orden de idx_sorted

    
        # TWO POINTERS
        left = 0
        for right in range(n):
            while imp_sorted[right] - imp_sorted[left] > importe_tol:
                left += 1  # Mover left mientras la diferencia de importe exceda la tolerancia
            if right - left == 0:
                continue

            for k in range(left, right): #Comparamos 'right' con cada candidato 'k' dentro de tolerancia de importe
                f_r = fecha_sorted[right]
                f_k = fecha_sorted[k]

                # Fechas válidas
                if pd.isna(f_r) or pd.isna(f_k):
                    continue

                # DIFERENCIA DE FECHAS
                diff_dias = abs(f_r - f_k) / np.timedelta64(1, "D")
                if diff_dias > dias_tol:  #Si la diferencia en días excede la tolerancia, no son candidatos → saltamos
                    continue

                # SIMILITUD TEXTUAL
                sim = cosine_similarity(X_sub[right], X_sub[k])[0,0]
                if sim >= sim_tol:
                    i = idx_sorted[right]
                    j = idx_sorted[k]

                    df_out.at[i, "Duplicado_score"] = max(df_out.at[i, "Duplicado_score"], float(sim))
                    df_out.at[j, "Duplicado_score"] = max(df_out.at[j, "Duplicado_score"], float(sim))

                # DETECCIÓN EXTRA: REFERENCIAS CASI IGUALES (edit distance 1-3)
                ref_r = str(grp.loc[idx_sorted[right], "Referencia"])
                ref_k = str(grp.loc[idx_sorted[k], "Referencia"])

                if ref_r and ref_k:
                    if ref_r[:5] == ref_k[:5]:  # prefijo igual
                        df_out.loc[[idx_sorted[right], idx_sorted[k]], "Duplicado_score"] = \
                            np.maximum(df_out.loc[[idx_sorted[right], idx_sorted[k]], "Duplicado_score"], 0.75)


    df_out["Duplicado"] = (df_out["Duplicado_score"] >= sim_tol).astype(int)

    return df_out

def anomalias_isolation(df):

    # Variables necesarias
    features = ["ImpteML", "Demora", "Antigüedad", "zs_score", "Casuística", "Duplicado"]

    # Garantizar que existen todas las columnas
    for c in features:
        if c not in df.columns:
            df[c] = 0

    # Asegurar tipo numérico y valores nulos
    df[features] = df[features].apply(pd.to_numeric, errors="coerce").fillna(0)

    # Escalado + Isolation Forest
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(df[features])

    iso = IsolationForest(contamination=0.05, random_state=42)
    df["Outlier"] = (iso.fit_predict(X_scaled) == -1).astype(int)
    df["Outlier_score"] = iso.decision_function(X_scaled)

    def robust_z(s):
        med = np.median(s)
        mad = np.median(np.abs(s - med))
        mad = mad if mad > 0 else 1e-6
        return (s - med) / (1.4826 * mad)

    # Usamos z-scores para generar razones, no para crear columnas
    Z = {col: robust_z(df[col]) for col in features}

    def build_reasons(idx, top_k=3):
        vals = {col: abs(Z[col][idx]) for col in features}
        top = sorted(vals.items(), key=lambda x: x[1], reverse=True)[:top_k]
        reasons = []
        for col, _ in top:
            direction = "alto" if Z[col][idx] > 0 else "bajo"
            reasons.append(f"{col} muy {direction} (z={Z[col][idx]:.2f})")
        return reasons

    # Crear columnas vacías con las razones
    df["reason1"] = ""
    df["reason2"] = ""
    df["reason3"] = ""

    # Guardar razones para outliers
    out_idx = df[df["Outlier"] == 1].index
    for i in out_idx:
        rs = build_reasons(i)
        for j, r in enumerate(rs):
            df.at[i, f"reason{j+1}"] = r

    return df

def riesgo_global(df):
  
    df = df.copy()

    # 0) Asegurar tipos datetime para poder restar fechas
    for c in ["Registrado", "Fecha_doc"]:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce")

    # 1) Delta fecha doc (solo valores tardíos: registrado - fecha_doc > 0)
    if "Registrado" in df.columns and "Fecha_doc" in df.columns:
        df["Delta_fecha_doc"] = (df["Registrado"] - df["Fecha_doc"]).dt.days
        df["Delta_fecha_doc"] = pd.to_numeric(df["Delta_fecha_doc"], errors="coerce").fillna(0)
        df["Delta_fecha_doc_pos"] = df["Delta_fecha_doc"].clip(lower=0)
    else:
        df["Delta_fecha_doc"] = 0
        df["Delta_fecha_doc_pos"] = 0

    # 2) Asegurar columnas necesarias
    needed = ["zs_score", "CASE_SCORE", "Outlier_score", "Duplicado_score",
              "Demora", "Antigüedad", "ImpteML", "Delta_fecha_doc_pos"]
    for col in needed:
        if col not in df.columns:
            df[col] = 0

    # 3) Normalización de importe (abs y min-max)
    df["ImpteML"] = pd.to_numeric(df["ImpteML"], errors="coerce").fillna(0)
    abs_vals = df["ImpteML"].abs()
    df["IMP_NORM"] = (abs_vals - abs_vals.min()) / (abs_vals.max() - abs_vals.min() + 1e-9)

    def normalize_series(s):
        s = pd.to_numeric(s, errors="coerce").fillna(0)
        return (s - s.min()) / (s.max() - s.min() + 1e-9)

    df["NORM_DEMORA"] = normalize_series(df["Demora"])
    df["NORM_ANTIG"]  = normalize_series(df["Antigüedad"])
    df["NORM_DUP"]    = normalize_series(df["Duplicado_score"])
    df["NORM_OUT"]    = normalize_series(df["Outlier_score"])
    df["NORM_DELTA"]  = normalize_series(df["Delta_fecha_doc_pos"])  # <-- nuevo

    # 4) Riesgo global (ajusta pesos si quieres)
    df["Riesgo"] = (
        0.25 * df["zs_score"] +
        0.20 * df["NORM_DUP"] +
        0.15 * df["NORM_OUT"] +
        0.10 * df["CASE_SCORE"] +
        0.07 * df["NORM_DELTA"] +
        0.05 * df["NORM_DEMORA"] +
        0.05 * df["NORM_ANTIG"] +
        0.03 * df["IMP_NORM"]
    ).round(4)

    # 5) Limpieza columnas auxiliares
    df.drop(columns=["IMP_NORM","NORM_DEMORA","NORM_ANTIG","NORM_DUP","NORM_OUT","NORM_DELTA","Delta_fecha_doc_pos"],
            inplace=True, errors="ignore")

    return df

def global_stats(df):  
    # características globales
    df = df.copy()

    stats = {
        "total_facturas": len(df),

        # Riesgo
        "facturas_riesgo_alto": (df["Riesgo_final"] > 0.60).sum(),
        "pct_riesgo_alto": float((df["Riesgo_final"] > 0.60).mean()),
        "riesgo_medio_global": float(df["Riesgo_final"].mean()),
        "riesgo_p95_global": float(df["Riesgo_final"].quantile(0.95)),

        # Importe ponderado por riesgo
        "importe_riesgo_total": float((df["ImpteML"].abs() * df["Riesgo_final"]).sum()),
        "riesgo_ponderado_global": float(
            (df["ImpteML"].abs() * df["Riesgo_final"]).sum() /
            (df["ImpteML"].abs().sum() + 1e-9)
        ),

        # Duplicados
        "duplicados_total": int(df["Duplicado"].sum()),
        "pct_duplicados": float(df["Duplicado"].mean()),

        # Anomalías IF
        "anomalias_total": int(df["Outlier"].sum()),
        "pct_anomalias": float(df["Outlier"].mean()),
    }

    return pd.DataFrame([stats])

def cluster_kmeans(df):

    variables =  ["ImpteML", "Demora", "Antigüedad","zs_score", "Duplicado_score","Outlier_score", "Riesgo", "Delta_fecha_doc"]
    d = df.copy()

    # Asegurar numéricas
    for col in variables:
        d[col] = pd.to_numeric(d[col], errors="coerce").fillna(0)

    # Clipping 1%-99% --> reduce el impacto de outliers extremos
    for col in variables:
        q1, q99 = d[col].quantile(0.01), d[col].quantile(0.99)
        d[col] = d[col].clip(q1, q99)

    # Escalado robusto
    scaler = RobustScaler()
    Xs = scaler.fit_transform(d[variables])

    n = len(d)

    # Selección del mejor k usando Silhoutte Score
    ks = [k for k in [3,4,5] if k <= n]
    best_k = ks[0]
    best_score = -1

    for k in ks:
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = km.fit_predict(Xs)
        n_labels = len(set(labels))

        if 1 < n_labels < n:# silhouette solo si 1 < num_labels < n_samples
            try:
                score = silhouette_score(Xs, labels)
                if score > best_score:
                    best_score = score
                    best_k = k
            except:
                pass

    # Entrenar modelo final con mejor k
    km = KMeans(n_clusters=best_k, random_state=42, n_init=10)
    labels = km.fit_predict(Xs)
    d["Cluster"] = labels

    # Reduccion dimensionalidad con PCA a 2 componentes para visualización
    pca = PCA(n_components=2, random_state=42)
    coords = pca.fit_transform(Xs)
    d["PC1"], d["PC2"] = coords[:,0], coords[:,1]

    # Estadísticas descriptivas por cluster
    stats = (
        d.groupby("Cluster")[variables]
        .agg(["mean", "median", "std"])
        .round(3)
    )

    return d, stats

# ML SUPERVISADO-------------------------------------------------------------------------------------------------------------------------------------------

def rf_regressor(df, model_path="models/meta_rf.pkl"):

    # Normalizar importe escala 0-1
    df["ImpteML"] = pd.to_numeric(df["ImpteML"], errors="coerce").fillna(0)
    abs_vals = df["ImpteML"].abs()
    df["IMP_NORM"] = (abs_vals - abs_vals.min()) / (abs_vals.max() - abs_vals.min() + 1e-9)
    
    # variables explicativas del modelo
    FEATURES = ["zs_score", "CASE_SCORE", "Outlier", "Outlier_score","Duplicado_score", "IMP_NORM","CASE_SCORE","Duplicado", "Demora", "Antigüedad", "ImpteML" ]

    d = df.copy()
    for c in FEATURES:
        d[c] = pd.to_numeric(d[c], errors="coerce").fillna(0)

    X = d[FEATURES]
    y = pd.to_numeric(d["Riesgo"], errors="coerce").fillna(0)

    # cargar o entrenar modelo, si ya existe
    if os.path.exists(model_path):
        model = joblib.load(model_path)
    else:
        model = RandomForestRegressor(
            n_estimators=300,
            max_depth=None,
            max_features="sqrt",
            random_state=42,
            n_jobs=-1
        ).fit(X, y)
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        joblib.dump(model, model_path)

    # prediccion y combinacion con riesgo base

    df["Riesgo_rf"] = model.predict(X)
    df["Riesgo_final"] = 0.40 * df["Riesgo"] + 0.60 * df["Riesgo_rf"] # Riesgo final como combinación ponderada

    return df, model

def rf_classifier(df, model_path="models/class_rf.pkl"):

    df["ImpteML"] = pd.to_numeric(df["ImpteML"], errors="coerce").fillna(0)
    abs_vals = df["ImpteML"].abs()
    df["IMP_NORM"] = (abs_vals - abs_vals.min()) / (abs_vals.max() - abs_vals.min() + 1e-9)
    

    FEATURES = ["zs_score", "CASE_SCORE", "Outlier", "Outlier_score","Duplicado_score", "IMP_NORM", "CASE_SCORE", "Duplicado", "Demora", "Antigüedad", "ImpteML" ]

    d = df.copy()
    for c in FEATURES:
        d[c] = pd.to_numeric(d[c], errors="coerce").fillna(0)

    X = d[FEATURES]

    # Construcción de la variable objetivo (clases)
    base = pd.to_numeric(d["Riesgo_final"], errors="coerce").fillna(0)
    d["Riesgo_clase"] = pd.cut(
        base,
        bins=[-0.01, 0.25, 0.51, 1.01],
        labels=[0, 1, 2],
        include_lowest=True
    ).astype(int)

    y = d["Riesgo_clase"]

    # cargar o entrenar el modelo
    if os.path.exists(model_path):
        model = joblib.load(model_path)
    else:
        model = RandomForestClassifier(
            class_weight="balanced",
            random_state=42,
            n_jobs=-1
        ).fit(X, y)
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        joblib.dump(model, model_path)

    # prediccion y etiquetas finales
    df["Riesgo_clase_rf"] = model.predict(X)
    df["Riesgo_clase_rf"] = df["Riesgo_clase_rf"].map({
        0: "Bajo",
        1: "Medio",
        2: "Alto"
    })

    df.drop(columns=['IMP_NORM'],inplace= True)

    return df, model

# ANALISIS POR UE Y PROVEEDOR ----------------------------------------------------------------------------------------------------------------------------

def proveedor_kpis(df):

    df = df.copy()

    # Convertir a numérico las columnas relevantes
    numeric_cols = [
        "ImpteML","Riesgo_final","Duplicado","Outlier",
        "Demora","Antigüedad","Delta_fecha_doc","zs_score"]

    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    
    # Índice de concentración HHI por UE --> detecta dependencia de un proveedor respecto a UEs
    def calc_hhi(x):
        p = x / x.sum()
        return (p**2).sum()
    
    # kpis agregados por proveedor (cuenta)
    kpis = df.groupby("Cuenta").apply(lambda g: pd.Series({
        
        # --- Volumen ---
        "n_facturas": len(g),
        "importe_total": g["ImpteML"].sum(),
        "importe_medio": g["ImpteML"].mean(),
        "coef_variacion_importe": g["ImpteML"].std() / (g["ImpteML"].mean() + 1e-9),

        # --- Riesgo ---
        "riesgo_medio": g["Riesgo_final"].mean(),
        "riesgo_p95": g["Riesgo_final"].quantile(0.95),
        "pct_riesgo_alto": (g["Riesgo_final"] > 0.60).mean(),
        "riesgo_ponderado": (g["ImpteML"].abs()*g["Riesgo_final"]).sum() / (g["ImpteML"].abs().sum()+1e-9),

        # --- Duplicados / fraccionamiento ---
        "n_duplicados": g["Duplicado"].sum(),
        "pct_duplicados": g["Duplicado"].mean(),

        # --- Anomalías ---
        "n_anomalias": g["Outlier"].sum(),
        "pct_anomalias": g["Outlier"].mean(),

        # --- Ciclo documental y de pago ---
        "mora_media": g["Demora"].mean(),
        "mora_p95": g["Demora"].quantile(0.95),
        "pct_pago_tarde": (g["Demora"] > 0).mean(),
        "pct_pago_anticipado": (g["Demora"] < 0).mean(),

        "antiguedad_media": g["Antigüedad"].mean(),
        "delta_doc_media": g["Delta_fecha_doc"].mean(),
        "pct_registros_tarde": (g["Delta_fecha_doc"] > 0).mean(),

        # --- Semántica / Zero-shot ---
        "zs_score_medio": g["zs_score"].mean(),

        # --- Concentración (si un mismo proveedor factura a varias UEs) ---
        "hhi_por_ue": calc_hhi(g.groupby("UE")["ImpteML"].sum()),

    })).reset_index()

    return kpis

def analisis_UE(df, importe_tol=5, dias_tol=3,sim_tol=0.72):

    res = {}
    d = df.copy()
    d["UE"] = d["UE"].astype(str)

    try:
        res["KPIS_UE"] = (
            d.groupby("UE")
             .agg(
                n_facturas=("ImpteML","size"),
                importe_total=("ImpteML","sum"),
                importe_medio=("ImpteML","mean"),

                riesgo_medio=("Riesgo_final","mean"),
                riesgo_p95=("Riesgo_final", lambda x: x.quantile(0.95)),
                pct_riesgo_alto=("Riesgo_final", lambda x: (x > 0.60).mean()),

                mora_media=("Demora","mean"),
                pct_pago_tarde=("Demora", lambda x: (x > 0).mean()),
                pct_pago_anticipado=("Demora", lambda x: (x < 0).mean()),

                antig_media=("Antigüedad","mean"),
                delta_doc_media=("Delta_fecha_doc","mean"),
                pct_registros_tarde=("Delta_fecha_doc", lambda x: (x > 0).mean()),

                duplicados=("Duplicado","sum"),
                pct_duplicados=("Duplicado","mean"),
                anomalias=("Outlier","sum"),
                pct_anomalias=("Outlier","mean"),

                n_proveedores=("Nombre1", lambda x: x.nunique()),
                proveedor_mayor_gasto=("Nombre1", lambda x: x.value_counts().idxmax()),
             )
             .reset_index()
        )
    except Exception as e:
        print("[KPIS_UE]", e)
        res["KPIS_UE"] = pd.DataFrame()

    try:
        d["zs_label"] = d["zs_label"].astype(str).fillna("Sin_etiqueta")
        res["zs_ue"] = (
            d.groupby(["UE","zs_label"])
             .size()
             .reset_index(name="count")
             .pivot(index="UE", columns="zs_label", values="count")
             .fillna(0)
        )
    except Exception as e:
        print("[ZS_UE]", e)
        res["zs_ue"] = pd.DataFrame()

    try: # Mismo proveedor + importe similar + fecha cercana + texto
        d2 = d.copy()
        d2["ImpteML"] = pd.to_numeric(d2["ImpteML"], errors="coerce").fillna(0)
        d2["Fecha_doc"] = pd.to_datetime(d2["Fecha_doc"], errors="coerce")

        cols_texto = [c for c in ["Texto","Referencia","Solicitud"] if c in d2.columns]
        d2["texto_dup"] = d2[cols_texto].astype(str).apply(lambda r: " ".join(r), axis=1)

        duplicados = []

        for cuenta, g in d2.groupby("Cuenta"): # comparar dentro de cada proveedor

            ues = g["UE"].unique()
            if len(ues) < 2:
                continue

            vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3,5))
            X = vec.fit_transform(g["texto_dup"])

            for ue1 in ues: # compara entre ues donde aparece el proveedor
                for ue2 in ues:
                    if ue1 >= ue2:
                        continue

                    g1 = g[g["UE"] == ue1].sort_values("ImpteML")
                    g2 = g[g["UE"] == ue2].sort_values("ImpteML")

                    i = j = 0
                    imp1 = g1["ImpteML"].values
                    imp2 = g2["ImpteML"].values

                    while i < len(imp1) and j < len(imp2):

                        diff = imp1[i] - imp2[j]

                        if abs(diff) <= importe_tol:

                            f1 = g1.iloc[i]["Fecha_doc"]
                            f2 = g2.iloc[j]["Fecha_doc"]

                            if pd.notna(f1) and pd.notna(f2):
                                if abs((f1 - f2).days) <= dias_tol:

                                    idx1 = g1.index[i]
                                    idx2 = g2.index[j]

                                    sim = cosine_similarity(
                                        X[g.index.get_loc(idx1)],
                                        X[g.index.get_loc(idx2)]
                                    )[0,0]

                                    if sim >= sim_tol:
                                        duplicados.append({
                                            "UE_1": ue1,
                                            "UE_2": ue2,
                                            "Cuenta": cuenta,
                                            "Impte_1": imp1[i],
                                            "Impte_2": imp2[j],
                                            "Fecha_1": f1,
                                            "Fecha_2": f2,
                                            "similaridad_texto": float(sim),
                                            "Texto_1": g1.iloc[i]["texto_dup"],
                                            "Texto_2": g2.iloc[j]["texto_dup"],
                                        })

                            i += 1
                            j += 1

                        elif diff < 0:
                            i += 1
                        else:
                            j += 1

        res["Duplicados_UE"] = pd.DataFrame(duplicados)

    except Exception as e:
        print("[Duplicados_UE]", e)
        res["Duplicados_UE"] = pd.DataFrame()

    resumen = {}
    try: resumen["UE_mayor_riesgo"] = d.groupby("UE")["Riesgo_final"].mean().idxmax()
    except: resumen["UE_mayor_riesgo"] = None

    try: resumen["UE_mas_anomalias"] = d.groupby("UE")["Outlier"].sum().idxmax()
    except: resumen["UE_mas_anomalias"] = None

    try: resumen["UE_mas_duplicados"] = d.groupby("UE")["Duplicado"].sum().idxmax()
    except: resumen["UE_mas_duplicados"] = None

    try: resumen["UE_mas_mora"] = d.groupby("UE")["Demora"].mean().idxmax()
    except: resumen["UE_mas_mora"] = None

    try: resumen["UE_mas_antiguedad"] = d.groupby("UE")["Antigüedad"].mean().idxmax()
    except: resumen["UE_mas_antiguedad"] = None

    res["Resumen"] = resumen

    return res

def clustering_proveedores(df):

    def cluster_por_proveedor(tabla):
        """
        Aplica KMeans sobre KPIs de proveedores,
        seleccionando automáticamente el número óptimo de clusters (K)
        mediante silhouette score.
        """

        # Variables relevantes para clustering
        vars_clust = [
            "n_facturas",
            "importe_total",
            "importe_medio",
            "coef_variacion_importe",
            "riesgo_medio",
            "riesgo_p95",
            "pct_riesgo_alto",
            "mora_media",
            "pct_pago_tarde",
            "pct_pago_anticipado",
            "antiguedad_media",
            "delta_doc_media",
            "pct_registros_tarde",
            "n_duplicados",
            "pct_duplicados",
            "n_anomalias",
            "pct_anomalias",
            "zs_score_medio",
            "hhi_por_ue"
        ]

        # Normalización
        X = tabla[vars_clust].fillna(0)
        X_scaled = StandardScaler().fit_transform(X)

        n = len(tabla)

        # Fallback: muy pocos proveedores
        if n < 3:
            tabla["Cluster_proveedor"] = 0
            stats = tabla.groupby("Cluster_proveedor")[vars_clust].mean()
            return tabla, stats

        # Selección automática de K con silhouette score
        possible_k = range(3, min(7, n))  # 2 a 6 clusters (o menos si hay pocos datos)
        best_k = None
        best_score = -1

        for k in possible_k:
            try:
                km = KMeans(n_clusters=k, random_state=42, n_init=10)
                labels = km.fit_predict(X_scaled)

                # silhouette solo válido si hay >1 cluster
                if len(set(labels)) > 1:
                    score = silhouette_score(X_scaled, labels)
                    if score > best_score:
                        best_score = score
                        best_k = k
            except Exception:
                continue

        # Si silhouette falla, usar fallback
        if best_k is None:
            best_k = 2

        # Entrenamiento final con K óptimo
        kmeans = KMeans(n_clusters=best_k, random_state=42, n_init=10)
        tabla["Cluster_proveedor"] = kmeans.fit_predict(X_scaled)

        # Estadísticas por cluster
        stats = tabla.groupby("Cluster_proveedor")[vars_clust].mean()

        return tabla, stats

    # Clustering GLOBAL
    kpis_global = proveedor_kpis(df)
    df_global_cluster, stats_global = cluster_por_proveedor(kpis_global)

    results = {
        "GLOBAL": {
            "df": df_global_cluster,
            "stats": stats_global
        }
    }

    # Clustering por UE
    if "UE" in df.columns:
        for ue in df["UE"].dropna().unique():

            df_ue = df[df["UE"] == ue]

            kpis_ue = proveedor_kpis(df_ue)

            # No clusterizar si hay muy pocos proveedores
            if len(kpis_ue) < 3:
                results[ue] = {
                    "df": kpis_ue,
                    "stats": pd.DataFrame()
                }
                continue

            df_ue_cluster, stats_ue = cluster_por_proveedor(kpis_ue)

            results[ue] = {
                "df": df_ue_cluster,
                "stats": stats_ue
            }

    return results

def pca_clustering_proveedores(tabla, titulo="PCA"):
    
    vars_clust = [
        "n_facturas",
        "importe_total",
        "importe_medio",
        "coef_variacion_importe",
        "riesgo_medio",
        "riesgo_p95",
        "pct_riesgo_alto",
        "mora_media",
        "pct_pago_tarde",
        "pct_pago_anticipado",
        "antiguedad_media",
        "delta_doc_media",
        "pct_registros_tarde",
        "n_duplicados",
        "pct_duplicados",
        "n_anomalias",
        "pct_anomalias",
        "zs_score_medio",
        "hhi_por_ue"
    ]
    
    # Normalización
    X = tabla[vars_clust].fillna(0)
    X_scaled = StandardScaler().fit_transform(X)
    
    # PCA a 2 componentes
    pca = PCA(n_components=2)
    components = pca.fit_transform(X_scaled)
    
    # Construir dataframe PCA
    df_pca = pd.DataFrame({
        "PC1": components[:, 0],
        "PC2": components[:, 1],
        "Cluster": tabla["Cluster_proveedor"]
    })
    
    # Plot
    plt.figure(figsize=(10, 7))
    for cluster in df_pca["Cluster"].unique():
        sub = df_pca[df_pca["Cluster"] == cluster]
        plt.scatter(sub["PC1"], sub["PC2"], label=f"Cluster {cluster}", s=70)

    plt.title(titulo)
    plt.xlabel("PC1")
    plt.ylabel("PC2")
    plt.legend()
    plt.grid(True)
    plt.show()

# EXPORTACIÓN ---------------------------------------------------------------------------------------------------------------------------------------------

def flatten_df(df):
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = ['_'.join(map(str, col)).strip() for col in df.columns]
    return df

def run_pipeline(df): #path
    #df = pd.read_csv(path)
    df = preprocess(df)

    df_casos = casuistica(df)
    df_anticipos = anticipos_proveedores(df)
    df = propagar_solicitud_proveedor(df_casos)
    df = case_score(df)
        
    df["Saldo_total_proveedor"] = df.groupby(["UE", "Cuenta"])["ImpteML"].transform("sum") # donde _is_total = 1 total provedor
    df["Num_partidas_proveedor"] = df.groupby(["UE", "Cuenta"])["ImpteML"].transform("count") # donde _is_total = 0 partidas indiv

    df = zero_shot(df)
    df_zs= df[['UE','Sociedad', 'Cuenta','Clase','ImpteML', 'Demora', 'Fecha_pago', 'Fe_contab', 'Casuística', 'Solicitud','zs_label','zs_score']]
    
    df = detectar_duplicados(df)

    df_dup= df[df['Duplicado']==1]
    df_dup = df_dup[['UE', 'Sociedad','Cuenta','Clase','ImpteML', 'Demora', 'Fecha_pago', 'Fe_contab', 'Casuística', 'Solicitud','Duplicado']]

    df= anomalias_isolation(df)
    df_if = df[df['Outlier']==1]
    df_if = df_if[['UE','Sociedad', 'Cuenta','Clase','ImpteML', 'Demora', 'Fecha_pago', 'Fe_contab','Casuística', 'Solicitud','zs_score','Duplicado','Outlier','reason1','reason2','reason3']]

    df = riesgo_global(df)
    df_rg = df[['UE','Sociedad', 'Cuenta',"zs_score", 'Casuística', "Outlier_score", "Duplicado_score", "Demora", "Antigüedad","Delta_fecha_doc", "ImpteML", 'Riesgo']]


    df, stats_cluster = cluster_kmeans(df)
    df_cluster = df[['UE', 'Sociedad','Cuenta',"ImpteML", "Demora", "Antigüedad","zs_score", "Duplicado_score","Outlier_score",'Casuística', "Delta_fecha_doc", "ImpteML", "Riesgo","Cluster", "PC1", "PC2"]]

    df, model_reg = rf_regressor(df)
    df_rf=df[['UE','Sociedad', 'Cuenta',"zs_score",'Casuística', "Outlier", "Duplicado", "Demora", "Antigüedad", "ImpteML", 'Riesgo', 'Riesgo_rf', 'Riesgo_final' ]]

    df, model_cls = rf_classifier(df)
    df_cls=df[['UE','Sociedad', 'Cuenta',"zs_score", 'Casuística', "Outlier", "Duplicado", "Demora", "Antigüedad", "ImpteML", 'Riesgo', 'Riesgo_rf', 'Riesgo_final', 'Riesgo_clase_rf' ]]

    stats_global = global_stats(df)

    proveedores_kpis = proveedor_kpis(df)
    analisis_ue = analisis_UE(df)
    clust_proveedores = clustering_proveedores(df)

    return df, df_casos,df_anticipos, df_zs, df_dup, df_if, df_rg, df_cluster, stats_cluster, df_rf, df_cls, stats_global, proveedores_kpis, analisis_ue, clust_proveedores

def excel_ml(df: pd.DataFrame, output_path: str) -> str:
    # -----------------------------
    # 1) Preparar rutas
    # -----------------------------
    base = os.path.splitext(os.path.basename(output_path))[0]
    out_folder = os.path.join(os.getcwd(), f"audit_{base}")
    os.makedirs(out_folder, exist_ok=True)
    final_path = os.path.join(out_folder, os.path.basename(output_path))

    # -----------------------------
    # 2) Ejecutar pipeline
    # -----------------------------
    (df_final, df_casos, df_anticipos, df_zs, df_dup, df_if, df_rg,
     df_cluster, stats_cluster, df_rf, df_cls, stats_global,
     proveedores_kpis, analisis_ue, clust_proveedores) = run_pipeline(df)

    # KPIs proveedores por UE (útil para hoja larga)
    kpis_proveedor_por_ue = {
        ue: proveedor_kpis(df_final[df_final["UE"] == ue])
        for ue in df_final["UE"].dropna().unique()
    }
    kpis_proveedor_df = (
        pd.concat(kpis_proveedor_por_ue, names=["UE"])
          .reset_index(level=0)
          .reset_index(drop=True)
    )

    # Componentes analisis UE
    analisis_ue_zs  = analisis_ue.get("zs_ue", pd.DataFrame())
    analisis_ue_dup = analisis_ue.get("Duplicados_UE", pd.DataFrame())
    analisis_ue_res = pd.DataFrame([analisis_ue.get("Resumen", {})])

    # stats clustering proveedores por UE (si existe)
    stats_ue = pd.concat(
        {ue: res["stats"] for ue, res in clust_proveedores.items() if isinstance(res.get("stats", None), pd.DataFrame)},
        names=["UE", "Cluster"]
    ) if isinstance(clust_proveedores, dict) else pd.DataFrame()

    stats_ue_ = {}
    if not stats_ue.empty:
        for ue in stats_ue.index.get_level_values("UE").unique():
            try:
                stats_ue_[ue] = flatten_df(stats_ue.xs(ue, level="UE").reset_index())
            except Exception:
                stats_ue_[ue] = pd.DataFrame()

    # Forecast
    metricas_dict, df_predicciones, df_forecast = forecast_batch(
        df_final, steps_test=6, steps_future=12,
        plot_diagnostico=False, plot_forecast=False
    )

    # -----------------------------
    # Helpers Excel
    # -----------------------------
    def _write_df(writer, sheet, df_, index=False, startrow=0):
        if isinstance(df_, pd.DataFrame) and not df_.empty:
            df_.to_excel(writer, sheet_name=sheet, index=index, startrow=startrow)

    def _autofilter_freeze(ws):
        max_row = ws.max_row
        max_col = ws.max_column
        if max_row >= 1 and max_col >= 1:
            last_col = get_column_letter(max_col)
            ws.auto_filter.ref = f"A1:{last_col}{max_row}"
            ws.freeze_panes = "A2"

    # -----------------------------
    # 3) Excel GLOBAL
    # -----------------------------
    with pd.ExcelWriter(final_path, engine="openpyxl") as writer:

        _write_df(writer, "00_df_final", df_final)
        _write_df(writer, "01_Zero_shot", df_zs)
        _write_df(writer, "02_Duplicados", df_dup)
        _write_df(writer, "03_Anomalias", df_if)
        _write_df(writer, "04_Riesgo", df_rg)
        _write_df(writer, "05_Cluster_partidas", df_cluster)

        _write_df(writer, "05b_Stats_cluster", flatten_df(stats_cluster).reset_index(), index=False)

        _write_df(writer, "06_RF_regressor", df_rf)
        _write_df(writer, "07_RF_classifier", df_cls)
        _write_df(writer, "08_Stats_global", stats_global)

        # KPIs proveedores (global + por UE en la misma hoja)
        sheet = "09_KPIS_Proveedores"
        row = 0
        _write_df(writer, sheet, proveedores_kpis, startrow=row)
        row += (len(proveedores_kpis) + 2) if isinstance(proveedores_kpis, pd.DataFrame) else 2

        ws = writer.sheets.get(sheet, None)
        if ws is not None:
            for ue in kpis_proveedor_df["UE"].dropna().unique():
                df_kpi = kpis_proveedor_df[kpis_proveedor_df["UE"] == ue]
                ws.cell(row + 1, 1).value = f"KPI_PROV_{ue}"
                row += 1
                df_kpi.to_excel(writer, sheet_name=sheet, index=False, startrow=row)
                row += len(df_kpi) + 2

        # Analisis UE (bloques)
        sheet2 = "10_Analisis_UE"
        writer.book.create_sheet(sheet2)
        ws2 = writer.book[sheet2]
        writer.sheets[sheet2] = ws2
        r = 0

        ws2.cell(r+1, 1).value = "Zero_shot UE"
        r += 1
        if isinstance(analisis_ue_zs, pd.DataFrame) and not analisis_ue_zs.empty:
            analisis_ue_zs.to_excel(writer, sheet_name=sheet2, index=True, startrow=r)  # suele venir pivot
            r += len(analisis_ue_zs) + 3

        ws2.cell(r+1, 1).value = "Duplicados UE"
        r += 1
        _write_df(writer, sheet2, analisis_ue_dup, startrow=r)
        r += (len(analisis_ue_dup) + 3) if isinstance(analisis_ue_dup, pd.DataFrame) else 3

        ws2.cell(r+1, 1).value = "Resumen UE"
        r += 1
        _write_df(writer, sheet2, analisis_ue_res, startrow=r)
        r += (len(analisis_ue_res) + 3)

        _write_df(writer, "11_ClustProv_GLOBAL", clust_proveedores["GLOBAL"]["df"])
        _write_df(writer, "11b_Stats_ClustProv", flatten_df(clust_proveedores["GLOBAL"]["stats"]).reset_index(), index=False)

        # Forecast
        if isinstance(df_forecast, pd.DataFrame) and not df_forecast.empty:
            _write_df(writer, "12_FORECAST_ALL", df_forecast)

        # Filtros y congelar cabecera en hojas principales
        for sh in ["00_df_final","01_Zero_shot","02_Duplicados","03_Anomalias","04_Riesgo","06_RF_regressor","07_RF_classifier"]:
            ws_ = writer.sheets.get(sh, None)
            if ws_ is not None:
                _autofilter_freeze(ws_)

    # -----------------------------
    # 4) EXCEL por UE
    # -----------------------------
    for ue in df_final["UE"].dropna().unique():

        ue_folder = os.path.join(out_folder, str(ue))
        os.makedirs(ue_folder, exist_ok=True)
        ue_path = os.path.join(ue_folder, f"{ue}.xlsx")

        # Filtrar datasets por UE cuando aplique
        def f_ue(df_):
            return df_[df_["UE"] == ue] if isinstance(df_, pd.DataFrame) and "UE" in df_.columns else df_

        with pd.ExcelWriter(ue_path, engine="openpyxl") as writer:
            _write_df(writer, "00_df_final", f_ue(df_final))
            _write_df(writer, "01_Zero_shot", f_ue(df_zs))
            _write_df(writer, "02_Duplicados", f_ue(df_dup))
            _write_df(writer, "03_Anomalias", f_ue(df_if))
            _write_df(writer, "04_Riesgo", f_ue(df_rg))
            _write_df(writer, "05_Cluster_partidas", f_ue(df_cluster))
            _write_df(writer, "06_Riesgo_RF", f_ue(df_cls))

            # KPIs proveedor UE
            _write_df(writer, "07_KPIS_Prov_UE", kpis_proveedor_por_ue.get(ue, pd.DataFrame()))

            # KPIs UE (fila)
            kpis_ue_df = analisis_ue.get("KPIS_UE", pd.DataFrame())
            _write_df(writer, "08_KPIS_UE", kpis_ue_df[kpis_ue_df["UE"] == ue] if "UE" in kpis_ue_df.columns else kpis_ue_df)

            # Stats clustering proveedores UE
            _write_df(writer, "09_STATS_UE", stats_ue_.get(ue, pd.DataFrame()))

            # Forecast UE
            if isinstance(df_forecast, pd.DataFrame) and "UE" in df_forecast.columns:
                _write_df(writer, "10_FORECAST_UE", df_forecast[df_forecast["UE"] == ue])

            # filtros
            for sh in ["00_df_final","01_Zero_shot","02_Duplicados","03_Anomalias","04_Riesgo","06_Riesgo_RF"]:
                ws_ = writer.sheets.get(sh, None)
                if ws_ is not None:
                    _autofilter_freeze(ws_)

    return final_path


# SERIES TEMPORALES ----------------------------------------------------------------------------------------------------------------------------------------

def preparar_serie_ts(df, fecha_col, valor_col):
    # prepara una serie temporal en formato (ds,y)
    # seleccioanr columnas de fecha y valor
    ts = df[[fecha_col, valor_col]].copy()
    ts = ts.sort_values(fecha_col) # orden cronologico

    ts["ds"] = pd.to_datetime(ts[fecha_col]) # renombrado para forecasting
    ts["y"]  = ts[valor_col]

    ts = ts.replace([np.inf, -np.inf], np.nan) # limpoar valores infinitos
    ts = ts.dropna(subset=["y"]) # limpiar valores nulos, sin valor

    return ts[["ds", "y"]]

def extremos_anuales(df, fecha_col, valor_col):
    # identifica l mes con el valor max y min de cada año
    # para poder detectar estacionalidad y picos
    df2 = df.copy()
    df2["año"] = df2[fecha_col].dt.year #extarccion del año
    
    resumen = []
    for año, grupo in df2.groupby("año"): #analisis de cada año por separado
        if grupo.empty: 
            continue
        min_fila = grupo.loc[grupo[valor_col].idxmin()]
        max_fila = grupo.loc[grupo[valor_col].idxmax()]
        resumen.append({
            "año": año,
            "min": min_fila[fecha_col].strftime('%m'),
            "max": max_fila[fecha_col].strftime('%m'),
        })
        
    return pd.DataFrame(resumen)

def modelo_ets(ts):
    # modelo ets (holt-winters)
    y = ts.set_index("ds")["y"]
    return ExponentialSmoothing(y, trend="add", seasonal="add", seasonal_periods=12).fit(optimized=True)

def modelo_sarimax_auto(ts):
    # modelo sarimax estandar con estacionalidad
    y = ts["y"]

    # Series cortas → ETS
    if len(ts) < 18:
        return modelo_ets(ts)

    try:
        model = SARIMAX(
            y,
            order=(1,1,1),
            seasonal_order=(1,1,1,12),
            enforce_stationarity=False,
            enforce_invertibility=False
        ).fit(disp=False)
        return model

    except Exception:
        return modelo_ets(ts) # si  falla --> fallback a ets

def modelo_prophet(ts):
    # modelo prophet cone stacionalidad anual, para series largas noe estacioanrias
    m = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=False,
        daily_seasonality=False
    )
    m.fit(ts[["ds", "y"]])
    return m

def evaluar_forecast(train, test, pred_test, pred_future=None, title="", train_tail=12, plot=False):

    real = test["y"].values
    pred_test = np.array(pred_test)

    # metricas de error
    df_eval = pd.DataFrame({
        "MAE": [mean_absolute_error(real, pred_test)],
        "RMSE": [np.sqrt(mean_squared_error(real, pred_test))],
        "MAPE": [np.mean(np.abs((real - pred_test) / (real + 1e-9)))]
    })

    if plot:
        train_tail_df = train.tail(train_tail)

        plt.figure(figsize=(14,5))
        plt.plot(train_tail_df["ds"], train_tail_df["y"], label="Train")
        plt.plot(test["ds"], real, label="Real Test")
        plt.plot(test["ds"], pred_test, "--", label="Pred Test")

    #forecast futuro si existe
        if pred_future is not None:
            future_dates = pd.date_range(
                start=test["ds"].iloc[-1] + pd.offsets.MonthBegin(1),
                periods=len(pred_future),
                freq="MS"
            )
            plt.plot(future_dates, pred_future, "-.", label="Forecast Futuro")

        plt.title(title)
        plt.legend()
        plt.grid()
        plt.show()

    return df_eval

def entrenar_modelo(ts, titulo="Diagnóstico y Selección de Modelo", plot=True):
    # decide el modelo en funcion de la estacionaridad (test adf) y la longitud d ela serie
    diagnostico = {}
    ts = ts.dropna().copy()
    y = ts["y"]
    fechas = ts["ds"]

    # visualizacion inicial de la serie
    if plot:
        plt.figure(figsize=(12,4))
        plt.plot(fechas, y, marker="o")
        plt.title(f"{titulo} - Serie Temporal")
        plt.grid(True)

        ax = plt.gca()
        ax.xaxis.set_major_locator(mdates.MonthLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        plt.xticks(rotation=45)
        plt.show()

    #  Test de estacionaridad ADF 
    adf_stat, pvalue, *_ = adfuller(y)
    estacionaria = pvalue < 0.05

    diagnostico["adf_stat"] = adf_stat
    diagnostico["pvalue"] = pvalue
    diagnostico["estacionaria"] = estacionaria

    # diagnostico acf / pacf
    if plot:
        if len(y) > 10:
            max_lags = min(24, len(y)//2 - 1)

            if max_lags >= 1:
                fig, ax = plt.subplots(1, 2, figsize=(12,4))

                plot_acf(y, lags=max_lags, ax=ax[0])
                ax[0].set_title(f"ACF (lags={max_lags})")

                plot_pacf(y, lags=max_lags, ax=ax[1])
                ax[1].set_title(f"PACF (lags={max_lags})")

                plt.tight_layout()
                plt.show()
        else:
            pass

            # Seleccion automatica del modelo
    if not estacionaria:
        if len(ts) < 24:
            modelo = modelo_ets(ts)
            diagnostico["modelo_seleccionado"] = "ETS"
            diagnostico["razon_modelo"] = "Serie no estacionaria + corta"
            return modelo, diagnostico
        
        modelo = modelo_prophet(ts)
        diagnostico["modelo_seleccionado"] = "Prophet"
        diagnostico["razon_modelo"] = "Serie no estacionaria + larga"
        return modelo, diagnostico


    if len(ts) >= 24:
        modelo = modelo_sarimax_auto(ts)
        diagnostico["modelo_seleccionado"] = "SARIMAX_auto"
        diagnostico["razon_modelo"] = "Serie estacionaria + larga"

        return modelo, diagnostico

    modelo = modelo_ets(ts)
    diagnostico["modelo_seleccionado"] = "ETS"
    diagnostico["razon_modelo"] = "Serie estacionaria + corta"
    return modelo, diagnostico

def pipeline_forecast(df, fecha_col, valor_col,titulo="Forecast Serie",
                      steps_test=6,steps_future=12,
                      plot_diagnostico=True,plot_forecast=True):

    #  Preparar serie temporal con EXÓGENOS (sin NaN)
    ts = preparar_serie_ts(df, fecha_col, valor_col)
    ts = ts.sort_values("ds").copy()

    # Entrenar modelo seleccionado automaticamente
    model, diagnostico = entrenar_modelo(ts, titulo, plot=plot_diagnostico)

    #  Division en train y test
    train = ts[:-steps_test].copy()
    test  = ts[-steps_test:].copy()

    exog_cols = [c for c in ts.columns if c not in ["ds", "y"]]

    # Predicccion sobre el test

    #  PROPHET (con exógenos)
    if isinstance(model, Prophet):

        # Crear DF futuro con historial
        future_test = model.make_future_dataframe(
            periods=steps_test,
            freq="MS",
            include_history=True
        )

        # Añadir exógenos al future_test
        last_exog = ts[exog_cols].iloc[-1]

        for col in exog_cols:
            # Mapear exógenos al índice temporal
            mapped = ts.set_index("ds")[col].reindex(future_test["ds"])
            future_test[col] = mapped.ffill().bfill()
            # Si queda algún NaN, usar último valor real
            future_test[col] = future_test[col].fillna(last_exog[col])

        pred_test = model.predict(future_test)["yhat"].iloc[-steps_test:].values


    #  SARIMAX / ETS 
    else:
        pred_test = model.predict(
            start=len(train),
            end=len(train) + len(test) - 1
        )


    # Evaluación del test
    df_eval = evaluar_forecast(
        train=train,
        test=test,
        pred_test=pred_test,
        pred_future=None,
        title=f"{titulo} - Evaluación",
        plot=False
    )


    # Forecast futuro

    #  SARIMAX con exógenos
    if hasattr(model, "get_forecast"):

        if model.model.exog is not None:

            model_exog = model.model.exog_names
            model_exog = [x for x in model_exog if x != "intercept"]

            last_exog = ts[model_exog].iloc[-1]

            future_exog = pd.DataFrame(
                [last_exog.values] * steps_future,
                columns=model_exog
            )

            pred_future = model.get_forecast(
                steps=steps_future,
                exog=future_exog
            ).predicted_mean.values

        else:
            pred_future = model.get_forecast(steps=steps_future)\
                                .predicted_mean.values


    #  PROPHET con exógenos
    elif isinstance(model, Prophet):

        future_df = model.make_future_dataframe(
            periods=steps_future,
            freq="MS",
            include_history=False
        )

        last_exog = ts[exog_cols].iloc[-1]

        # Añadir exógenos futuros
        for col in exog_cols:
            future_df[col] = last_exog[col]

        future_df[exog_cols] = future_df[exog_cols].fillna(last_exog)
        pred_future = model.predict(future_df)["yhat"].values


    #  ETS fallback
    else:
        pred_future = model.forecast(steps_future)


    #  PLOT opcional
    if plot_forecast:
        evaluar_forecast(
            train=train,
            test=test,
            pred_test=pred_test,
            pred_future=pred_future,
            title=f"{titulo} - Forecast completo",
            plot=True
        )

    return model, df_eval, diagnostico, pred_test, pred_future

def forecast_riesgo_final(df_hist, df_future_vars, steps_future=12):

    feature_cols = ["ImpteML", "n_facturas", "pct_duplicados", "pct_anomalias", "Antigüedad","Demora", "Delta_fecha_doc"]

    # limpieza datos historicos
    df_train = df_hist.dropna(subset=["Riesgo_final"] + feature_cols).copy()

    df_train = df_train.replace([np.inf, -np.inf], np.nan)
    df_train = df_train.dropna(subset=feature_cols + ["Riesgo_final"])

    if df_train.empty or len(df_train) < 3:
        # fallback mínimo
        return np.zeros(steps_future)

    X_train = df_train[feature_cols].astype(float)
    y_train = df_train["Riesgo_final"].astype(float)

    # limpieza variables futuras
    df_future_vars = df_future_vars.copy()
    df_future_vars = df_future_vars.replace([np.inf, -np.inf], np.nan)
    df_future_vars = df_future_vars.fillna(0)

    X_future = df_future_vars[feature_cols].astype(float)

    # random forest regressor
    try:
        modelo_rf = RandomForestRegressor(
            n_estimators=300,
            max_depth=8,
            random_state=42
        )
        modelo_rf.fit(X_train, y_train)
        pred_rf = modelo_rf.predict(X_future)

    except Exception:
        pred_rf = np.ones(steps_future) * y_train.iloc[-1]

    return pred_rf

def pipeline_forecast_general(df,fecha_col,valor_col,titulo="Forecast",
                              steps_test=6,steps_future=12,future_exog_df=None,
                              plot_diagnostico=False,plot_forecast=False):

    # Variables temporales (SARIMA/ETS/Prophet)
    variables_temporales = ["ImpteML", "n_facturas", "pct_duplicados", "pct_anomalias", "Antigüedad", "Demora", "Delta_fecha_doc"]

    #  1) Variables temporales normales → pipeline_forecast
    if valor_col in variables_temporales:
        return pipeline_forecast( df=df,  fecha_col=fecha_col, valor_col=valor_col, titulo=titulo,
                                  steps_test=steps_test, steps_future=steps_future,
                                  plot_diagnostico=plot_diagnostico,  plot_forecast=plot_forecast)
    
    # Riesgo_final → randomforest
    if valor_col == "Riesgo_final":
        pred_future = forecast_riesgo_final( df_hist=df, df_future_vars=future_exog_df, steps_future=steps_future)

        if len(df) >= steps_test:
            pred_test = df["Riesgo_final"].tail(steps_test).values
        else:
            pred_test = np.array([df["Riesgo_final"].iloc[-1]] * steps_test)

        diagnostico = {
            "modelo_seleccionado": "RANDOM_FOREST",
            "razon_modelo": "Variable dependiente, no temporal pura"
        }

        df_eval = pd.DataFrame({
            "MAE": [0],
            "RMSE": [0],
            "MAPE": [0]
        })

        return None, df_eval, diagnostico, pred_test, pred_future

    raise Exception(f"Variable {valor_col} no reconocida en el sistema")

def forecast_batch(df,steps_test=6,steps_future=12,plot_diagnostico=False,plot_forecast=False):
   
    df['Registrado2'] = pd.to_datetime(df['Registrado'], errors='coerce')
    df['periodo'] = df['Registrado2'].dt.to_period('M')
    df['periodo_dt'] = df['periodo'].dt.to_timestamp()
    fecha_col = "periodo_dt"

    df = df.sort_values(fecha_col)

    numeric_cols = ["ImpteML", "Duplicado", "Outlier", "Riesgo_final", "Antigüedad","Demora", "Delta_fecha_doc"]
    df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors="coerce")

    df_res = (
        df.set_index(fecha_col)
            .groupby(["UE", "Cuenta"])
            .resample("MS")
            .agg({
                "ImpteML": "sum",
                "Duplicado": "sum",
                "Outlier": "sum",
                "Riesgo_final": "mean",
                "Antigüedad": "mean",
                "Demora": "mean",
                "Delta_fecha_doc": "mean",
            }).reset_index())


    df_res["n_facturas"] = (
        df.set_index(fecha_col)
        .groupby(["UE", "Cuenta"])
        .resample("MS")
        .size()
        .values
    )


    df_res["pct_duplicados"] = df_res["Duplicado"] / df_res["n_facturas"]
    df_res["pct_anomalias"]  = df_res["Outlier"]   / df_res["n_facturas"]

    df_res["pct_duplicados"].replace([np.inf, -np.inf], 0, inplace=True)
    df_res["pct_anomalias"].replace([np.inf, -np.inf], 0, inplace=True)

    vars_agg = {
        "ImpteML": "sum",
        "n_facturas": "sum",
        "pct_duplicados": "mean",
        "pct_anomalias": "mean",
        "Riesgo_final": "mean",
        "Antigüedad": "mean",
        "Demora": "mean",
        "Delta_fecha_doc": "mean"
    }

    # GLOBAL
    df_region_mes = df_res.groupby("periodo_dt").agg(vars_agg).reset_index()
    df_region_mes["UE"] = "GLOBAL"

    # UE
    df_ue_mes = df_res.groupby(["UE", "periodo_dt"]).agg(vars_agg).reset_index()

    # Salida
    metricas_dict = {}
    df_predicciones = {}
    df_pred_futuras = {}  # para Riesgo_final

    variables_temporales = [
        "ImpteML", "n_facturas",
        "pct_duplicados", "pct_anomalias", "Antigüedad",
        "Demora", "Delta_fecha_doc"
    ]

    # funcion auxixilar para guardar forecasts
    def registrar_forecast(var, nivel, ue, df_hist, pred_test, pred_future):
        # Hist + Futuro juntos
        df_out = df_hist.copy()
        df_out[f"{var}_forecast"] = None

        last_date = df_hist[fecha_col].max()

        future_dates = pd.date_range(
            start=last_date + pd.offsets.MonthBegin(1),
            periods=steps_future,
            freq="MS"
        )

        df_future = pd.DataFrame({
            fecha_col: future_dates,
            "UE": ue,
            f"{var}_forecast": pred_future
        })

        df_out = pd.concat([df_out, df_future], ignore_index=True)

        df_out["nivel"] = nivel
        df_out["UE"] = ue

        df_predicciones.setdefault(var, []).append(df_out)

        # métricas
        metricas_dict.setdefault(var, []).append({
            "nivel": nivel,
            "UE": ue,
            "variable": var,
            "pred_test": pred_test,
            "pred_future": pred_future
        })

    # Forecast variables temporales

    # GLOBAL
    for var in variables_temporales:
        df_sub = df_region_mes.rename(columns={"periodo_dt": fecha_col})
        modelo, eval_m, di, pred_test, pred_future = pipeline_forecast_general(df_sub,fecha_col,var,
            titulo=f"GLOBAL-{var}", steps_test=steps_test,steps_future=steps_future,
            plot_diagnostico=plot_diagnostico, plot_forecast=plot_forecast)

        registrar_forecast(var, "GLOBAL", "GLOBAL", df_sub, pred_test, pred_future)

    # UEs
    for ue in df_ue_mes["UE"].unique():
        df_sub = df_ue_mes[df_ue_mes["UE"] == ue].rename(columns={"periodo_dt": fecha_col})

        for var in variables_temporales:
            modelo, eval_m, di, pred_test, pred_future = pipeline_forecast_general(df_sub,fecha_col,var,
                titulo=f"{ue}-{var}",steps_test=steps_test,steps_future=steps_future,
                plot_diagnostico=plot_diagnostico,plot_forecast=plot_forecast)

            registrar_forecast(var, "UE", ue, df_sub, pred_test, pred_future)

    # unir forecast temporales para crear exogenas futuras
    def unir_predicciones(df_pred):
        dfs = []
        for var, lista in df_pred.items():
            for df_temp in lista:
                col = f"{var}_forecast"
                dfs.append(df_temp[["nivel","UE",fecha_col,col]])
        df_union = pd.concat(dfs, ignore_index=True)
        df_pivot = df_union.pivot_table(
            index=["nivel","UE",fecha_col],
            values=[c for c in df_union.columns if c.endswith("_forecast")],
            aggfunc="mean"
        ).reset_index()
        return df_pivot.sort_values(["nivel","UE",fecha_col])

    df_final = unir_predicciones(df_predicciones)

    # columna del forecast de riesgo final --> Random Forest Regressor

    df_final["Riesgo_final_rf_forecast"] = None

    #  Forecast GLOBAL 
    df_hist_global = df_region_mes.rename(columns={"periodo_dt": fecha_col}).copy()
    df_fut_global = df_final[df_final["UE"] == "GLOBAL"].copy()

    # Renombrar forecasted -> base exógenas
    ren = {
        "ImpteML_forecast": "ImpteML",
        "n_facturas_forecast": "n_facturas",
        "pct_duplicados_forecast": "pct_duplicados",
        "pct_anomalias_forecast": "pct_anomalias",
        "Antigüedad_forecast" : "Antigüedad",
        "Demora_forecast": "Demora",
        "Delta_fecha_doc_forecast": "Delta_fecha_doc"
    }
    df_fut_global = df_fut_global.rename(columns={k: v for k, v in ren.items() if k in df_fut_global.columns})

    # Forecast riesgo RF GLOBAL
    pred_rf_global = forecast_riesgo_final(df_hist_global, df_fut_global, steps_future)

    # Insertar en df_final
    df_final.loc[df_final["UE"] == "GLOBAL", "Riesgo_final_rf_forecast"] = pred_rf_global


    #  Forecast por UE 
    for ue in df_ue_mes["UE"].unique():

        df_hist_ue = df_ue_mes[df_ue_mes["UE"] == ue].rename(columns={"periodo_dt": fecha_col}).copy()
        df_fut_ue = df_final[df_final["UE"] == ue].copy()

        if df_fut_ue.empty:
            continue

        # renombrar forecasted -> exógenas base
        df_fut_ue = df_fut_ue.rename(columns={k: v for k, v in ren.items() if k in df_fut_ue.columns})

        pred_rf_ue = forecast_riesgo_final(df_hist_ue, df_fut_ue, steps_future)

        df_final.loc[df_final["UE"] == ue, "Riesgo_final_rf_forecast"] = pred_rf_ue


    return (metricas_dict,df_predicciones,df_final)

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

def plot_panel_train_test_pred(
    df_predicciones,
    ue="GLOBAL",
    variables=None,
    fecha_col="periodo_dt",
    steps_test=6,
    ncols=3,
    figsize=(18, 8),
    color_train="#1f77b4",   # azul
    color_test="#ff7f0e",    # naranja
    color_pred="#d62728",    # rojo
    lw_real=1.8,
    lw_pred=2.2,
    title=None
):
    """
    Panel multipanel: Train (real), Test (real) y Pred (forecast) para una UE.
    Usa df_predicciones (dict var -> lista de df_out por UE) generado por forecast_batch.
    """

    if variables is None:
        raise ValueError("Debes indicar `variables` (lista).")

    n = len(variables)
    nrows = int(np.ceil(n / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=figsize, sharex=True)
    axes = np.array(axes).reshape(-1)

    for i, var in enumerate(variables):
        ax = axes[i]
        col_fore = f"{var}_forecast"

        # localizar df de esa UE dentro de df_predicciones[var]
        lista = df_predicciones.get(var, [])
        df_ue = None

        for d in lista:
            if "UE" in d.columns and d["UE"].iloc[0] == ue:
                df_ue = d.copy()
                break

        if df_ue is None or df_ue.empty:
            ax.set_title(f"{var} (sin datos para {ue})")
            ax.axis("off")
            continue

        df_ue[fecha_col] = pd.to_datetime(df_ue[fecha_col])
        df_ue = df_ue.sort_values(fecha_col)

        # histórico real y forecast
        df_real = df_ue.dropna(subset=[var]).copy()
        df_pred = df_ue.dropna(subset=[col_fore]).copy()

        # split train/test
        if len(df_real) <= steps_test:
            df_train = df_real
            df_test = df_real.iloc[0:0]
        else:
            df_train = df_real.iloc[:-steps_test]
            df_test = df_real.iloc[-steps_test:]

        # plot train y test
        if not df_train.empty:
            ax.plot(
                df_train[fecha_col], df_train[var],
                color=color_train, linewidth=lw_real, label="Train (real)"
            )

        if not df_test.empty:
            ax.plot(
                df_test[fecha_col], df_test[var],
                color=color_test, linewidth=lw_real, label="Test (real)"
            )

        # plot forecast
        if not df_pred.empty:
            ax.plot(
                df_pred[fecha_col], df_pred[col_fore],
                color=color_pred, linewidth=lw_pred, label="Pred (forecast)"
            )

            ax.axvline(
                df_pred[fecha_col].iloc[0],
                color="k", linestyle="--", linewidth=1.0, alpha=0.5
            )

        ax.set_title(var)
        ax.grid(True, alpha=0.25)

    # apagar ejes sobrantes
    for j in range(i + 1, len(axes)):
        axes[j].axis("off")

    # leyenda global
    handles, labels = axes[0].get_legend_handles_labels()
    #fig.legend(handles, labels, loc="upper center", ncol=3, frameon=False)

    if title is None:
        title = f"Forecast — UE: {ue}"

    fig.suptitle(title, y=1.02, fontsize=14)
    plt.tight_layout()
    plt.show()
