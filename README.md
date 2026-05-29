# tfg-ml-audit

# Auditoría Continua y Análisis Predictivo de Cuentas por Pagar (CxP) mediante Machine Learning e IA Cognitiva

Este repositorio contiene la implementación integral del sistema desarrollado para la automatización analítica, detección de anomalías y auditoría conversacional sobre extractos transaccionales SAP FBL1N en entornos corporativos (caso de estudio aplicado a las Unidades de Explotación de Maya y Bávaro en Barceló Hotel Group).

El ecosistema está estructurado en dos vertientes: el núcleo analítico de experimentación/modelado en la raíz y la infraestructura del servicio cloud de producción empaquetada dentro del subdirectorio `saih-ai/`.

---

## Estructura General del Repositorio

```text
tfg-ml-audit/
├── .github/workflows/          # Pipelines CI/CD corporativos (GitHub Actions)
├── Metodologia/                # Scripts de ingeniería de datos y modelado
│   ├── functions.py            # Funciones helper, ETL, casuística y reglas analíticas
│   └── ml.py                   # Modelos de Machine Learning y algoritmos de Forecasting
├── Resultados/                 # Cuadernos de validación y artefactos científicos
│   └── tfg_limpio.ipynb        # Pipeline analítico y ejecución completa de experimentos
├── imgs/                       # Galería inmutable de diagramas y evidencias del TFG
│   └── [Figura_*.png]          # Gráficos de arquitectura, PCA, Clustering y Pronósticos
├── saih-ai/                    # Backend modular de producción (API REST asíncrona)
│   ├── app/                    # Código estructurado de la solución en Microsoft Azure
│   ├── Dockerfile              # Manifiesto de contenerización inmutable
│   ├── main.py                 # Punto de entrada de FastAPI y coordinación de rutas
│   ├── tool_fbl1n.json         # Manifiesto técnico para la invocación semántica del Agente
│   └── requirements.txt        # Dependencias de producción cloud
├── .gitignore                  # Exclusión estricta de binarios pesados (*.pkl, *.xlsx)
└── README.md                   # Documentación principal del ecosistema

```

---

## Arquitectura Lógica e Interconexión de Capas

El sistema opera bajo una arquitectura de microservicios estrictamente desacoplada de extremo a extremo, aislando la interfaz conversacional del cómputo analítico avanzado para blindar la gobernanza de datos y erradicar las alucinaciones financieras de los modelos lingüísticos.

```
┌───────────────────────────┐         Invocación Semántica Prompt
│ Usuario / Auditor Externo │ ──────────────────────────────────────────────┐
└─────────────┬─────────────┘                                               │
              │                                                             ▼
              │ Consulta Excel SAS URL (60 min)            ┌─────────────────────────────────┐
              │                                            │ Microsoft AI Foundry (Agent)    │
              ▼                                            └────────────────┬────────────────┘
┌───────────────────────────┐                                               │
│    Azure Blob Storage     │ ◄───────────────────────┐                     │ POST API Job Request
└───────────────────────────┘                         │                     ▼
                                            ┌─────────┴─────────┐  3a. Task ┌────────────────┐
                                            │    storage.py     │ ◄──────── │    main.py     │
                                            └─────────▲─────────┘  (BgTask) └────────┬───────┘
                                                      │ 5a. Excel                    │ 2. Alcance
                                            ┌─────────┴─────────┐           ┌────────▼───────┐
                                            │    pipeline.py    │           │  hotel_map.py  │
                                            └─────────▲─────────┘           └────────┬───────┘
                                                      │ 4b. DataFrame Fact           │ 3b. Sociedades
┌───────────────────────────┐  4a. XML SOAP ┌─────────┴─────────┐           ┌────────▼───────┐
│          SAP ERP          │ ◄──────────── │   sap_client.py   │           │   jobs.py      │
└───────────────────────────┘               └───────────────────┘           └────────┬───────┘
                                                                                     │ 3c. SQL State
                                                                                     ▼
                                                                            ┌────────────────┐
                                                                            │ Azure SQL DB   │
                                                                            └────────────────┘

```

1. **Interfaz Semántica (Azure AI Foundry):** El Agente intercepta el prompt del auditor, parsea la Unidad de Explotación (`tool_fbl1n.json`) e invoca mediante un *Job* asíncrono los servicios de procesamiento cloud expuestos en `saih-ai`.
2. **Coordinación Core (`main.py` & `hotel_map.py`):** La API recibe la petición HTTP, mapea la entidad hotelera a las sociedades fiscales reales del ERP e inicializa una subtarea en segundo plano registrada en `jobs.py`.
3. **Persistencia e Ingesta Extractor (`sap_client.py` & Azure SQL):** Se almacena la máquina de estados en `Azure SQL Database` mientras se realiza una llamada SOAP XML al Web Service nativo de SAP para descargar el extracto transaccional bruto.
4. **Pipeline de Evidencias (`pipeline.py` & `storage.py`):** Los algoritmos en Python ejecutan los controles contables de criticidad, generan las solicitudes para las filiales hoteleras y externalizan las evidencias en libros Excel cifrados mediante firmas **SAS (Shared Access Signatures)** válidas por 60 minutos en `Azure Blob Storage`.

---

## Bloque de Resultados Científicos (Jupyter Notebook)

El archivo `Resultados/tfg_limpio.ipynb` consolida toda la experimentación analítica e ingeniería de características implementada sobre las matrices transaccionales de **Maya (11.238 partidas)** y **Bávaro (5.394 partidas)**.

### Componentes Ejecutados secuencialmente:

* **Preprocesado y Normalización:** Remoción de totales contables SAP e inyección del tipo de cambio monetario homogéneo (`ImpteML`).
* **Reglas de Casuística Contable Heurística:** Identificación automatizada de anticipos estancados, partidas deudoras atípicas en acreedores y transacciones críticas sin Clave de Mayor Especial (CME).
* **Modelos Supervisados (Random Forest):** Clasificador y Regresor probabilístico para la evaluación continua del Score de Riesgo Global.
* *MAE de Validación:* `0.0241` | *F1-Score Ponderado:* `0.9315` | *Accuracy Global:* `93.82%`.


* **Clustering No Supervisado (K-Means & Isolation Forest):** Agrupamiento avanzado de patrones de riesgo contable anómalos a nivel de partidas y perfiles de proveedores corporativos.
* **Análisis Temporal Adaptativo (Forecasting):** Proyecciones a 12 meses vista de carga financiera mediante arquitecturas de series temporales univariantes y multivariantes (**SARIMAX**, **Prophet** de Meta y **ETS**).
* *Mape de Error Global:* `4.82%` en el consolidado macro de la corporación.



---

## Automatización Operacional DevOps (GitHub Actions)

El ciclo de vida de la aplicación se gestiona bajo principios estrictos de integración y entrega continua (*CI/CD*) configurados en `.github/workflows/`, divididos de forma determinista en tres fases inmutables:

* **`cicd` (Validación):** Orquesta los procesos de verificación sintáctica estática (*linting*), pruebas unitarias y tipado estricto ante eventos de *push* o *pull request* en la rama `main`.
* **`cidocker` (Compilación):** Levanta de forma automatizada el demonio de Docker, compila las capas optimizadas (`--no-cache-dir`) sobre la imagen base `python:3.11-slim`, firma el artefacto y lo publica en el registro privado de contenedores de la organización (*Azure Container Registry*).
* **`cd-deploy` (Despliegue):** Realiza la autenticación federada con Microsoft Azure, actualiza la revisión activa en el clúster sin servidor de **Azure Container Apps (`ca-saih-ai-test`)** y ejecuta un despliegue progresivo (*rolling update*) con tolerancia a fallos y sin caídas de servicio.

---

## Índice Temático de Evidencias e Ilustraciones (`imgs/`)

Para realizar consultas o verificaciones gráficas rápidas sobre el marco teórico y analítico expuesto en la memoria del TFG, puedes consultar de manera directa las imágenes indexadas dentro del repositorio:

### Capas de Arquitectura y Flujo de Control

* [Figura 3.1. Arquitectura de acceso a datos](https://www.google.com/search?q=./imgs/Figura%25203.1.%2520Arquitectura%2520de%2520acceso%2520a%2520datos.png)
* [Figura 4.1. Flujo general de control del sistema](https://www.google.com/search?q=./imgs/Figura%25204.1%2520.Flujo%2520general%2520del%2520sistema.png)
* [Figura 4.2. Clasificación heurística de partidas contables](https://www.google.com/search?q=./imgs/Figura%25204.2.%2520Clasificaci%C3%B3n%2520de%2520partidas%2520contables.png)
* [Figura 4.3. Generación automatizada de solicitudes a proveedores](https://www.google.com/search?q=./imgs/Figura%25204.3.%2520Generaci%C3%B3n%2520de%2520solicitudes%2520a%2520proveedores.png)
* [Figura 4.4. Ecuación y cálculo del riesgo global unificado](https://www.google.com/search?q=./imgs/Figura%25204.4.%2520C%C3%A1lculo%2520del%2520riesgo%2520global.png)

### Comportamiento Estadístico Transaccional por UE

* [Figura 7.1. Distribución de la casuística de control interno por UE](https://www.google.com/search?q=./imgs/Figura%25207.1.%2520Distribuci%C3%B3n%2520de%2520la%2520casu%C3%ADstica%2520por%2520unidad%2520de%2520explotaci%C3%B3n%2520%2528UE%2529.png)
* [Figura 7.2. Distribución de análisis macro por UE (Top categorías)](https://www.google.com/search?q=./imgs/Figura%25207.2.%2520Distribuci%C3%B3n%2520del%2520an%C3%A1lisis%2520por%2520unidad%2520de%2520explotaci%C3%B3n%2520%2528Top%2520categor%C3%ADas%2529.png)
* [Figura 7.3. Concentración y distribución del análisis de anticipos por UE](https://www.google.com/search?q=./imgs/Figura%25207.3.%2520Distribuci%C3%B3n%2520del%2520an%C3%A1lisis%2520de%2520anticipos%2520por%2520unidad%2520de%2520explotaci%C3%B3n.png)
* [Figura 7.4. Distribución de etiquetas normativas Zero‑Shot por UE](https://www.google.com/search?q=./imgs/Figura%25207.4.%2520Distribuci%C3%B3n%2520de%2520etiquetas%2520Zero%E2%80%91Shot%2520por%2520unidad%2520de%2520explotaci%C3%B3n.png)
* [Figura 7.5. Distribución de la densidad del score de riesgo global por UE](https://www.google.com/search?q=./imgs/Figura%25207.5.%2520Distribuci%C3%B3n%2520del%2520score%2520de%2520riesgo%2520global%2520por%2520unidad%2520de%2520explotaci%C3%B3n.png)
* [Figura 7.8. Distribución de niveles jerárquicos de riesgo por UE](https://www.google.com/search?q=./imgs/Figura%25207.8.%2520Distribuci%C3%B3n%2520de%2520niveles%2520de%2520riesgo%2520por%2520unidad%2520de%2520explotaci%C3%B3n.png)
* [Figura 7.9. Dispersión del riesgo medio y porcentaje de duplicidades por UE](https://www.google.com/search?q=./imgs/Figura%25207.9.%2520Riesgo%2520medio%2520y%2520porcentaje%2520de%2520duplicados%2520por%2520unidad%2520de%2520explotaci%C3%B3n.png)

### Reducción de Dimensionalidad PCA y Clustering No Supervisado

* [Figura 7.6. Representación PCA tridimensional del clustering de partidas en Maya](https://www.google.com/search?q=./imgs/Figura%25207.6.%2520Representaci%C3%B3n%2520PCA%2520del%2520clustering%2520en%2520la%2520UE%2520Maya.png)
* [Figura 7.7. Representación PCA tridimensional del clustering de partidas en Bávaro](https://www.google.com/search?q=./imgs/Figura%25207.7.%2520Representaci%C3%B3n%2520PCA%2520del%2520clustering%2520en%2520la%2520UE%2520B%C3%A1varo.png)
* [Figura 7.10. Representación PCA del clustering global consolidado de proveedores](https://www.google.com/search?q=./imgs/Figura%25207.10.%2520Representaci%C3%B3n%2520PCA%2520del%2520clustering%2520global%2520de%2520proveedores.png)
* [Figura 7.11. Representación PCA de la segmentación de proveedores en la UE Maya](https://www.google.com/search?q=./imgs/Figura%25207.11.%2520Representaci%C3%B3n%2520PCA%2520del%2520clustering%2520de%2520proveedores%2520en%2520la%2520UE%2520Maya.png)
* [Figura 7.12. Representación PCA de la segmentación de proveedores en la UE Bávaro](https://www.google.com/search?q=./imgs/Figura%25207.12.%2520Representaci%C3%B3n%2520PCA%2520del%2520clustering%2520de%2520proveedores%2520en%2520la%2520UE%2520B%C3%A1varo.png)

### Modelado Temporal, Diagnóstico y Proyecciones Futuristas (Forecasting)

* [Figura 6.1. Flujo metodológico del proceso de modelado de forecasting](https://www.google.com/search?q=./imgs/Figura%25206.1.%2520Flujo%2520del%2520proceso%2520de%2520forecasting.png)
* [Figura 7.13. Descomposición analítica temporal en la Unidad de Explotación Maya](https://www.google.com/search?q=./imgs/Figura%25207.13.%2520An%C3%A1lisis%2520temporal%2520por%2520unidad%2520de%2520explotaci%C3%B3n%2520Maya.png)
* [Figura 7.14. Descomposición analítica temporal en la Unidad de Explotación Bávaro](https://www.google.com/search?q=./imgs/Figura%25207.14.%2520An%C3%A1lisis%2520temporal%2520por%2520unidad%2520de%2520explotaci%C3%B3n%2520B%C3%A1varo.png)
* [Figura 7.15. Diagnóstico de residuos del modelo ARIMA de forecasting en Maya](https://www.google.com/search?q=./imgs/Figura%25207.15.%2520Diagn%C3%B3stico%2520del%2520modelo%2520de%2520forecasting%2520en%2520la%2520UE%2520Maya.png)
* [Figura 7.16. Diagnóstico de residuos del modelo ARIMA de forecasting en Bávaro](https://www.google.com/search?q=./imgs/Figura%25207.16.%2520Diagn%C3%B3stico%2520del%2520modelo%2520de%2520forecasting%2520en%2520la%2520UE%2520B%C3%A1varo.png)
* [Figura 7.17. Pronóstico univariante del importe futuro por Unidad de Explotación](https://www.google.com/search?q=./imgs/Figura%25207.17.%2520Forecast%2520del%2520importe%2520por%2520unidad%2520de%2520explotaci%C3%B3n.png)
* [Figura 7.18. Escenario predictivo multivariable avanzado en la UE Bávaro](https://www.google.com/search?q=./imgs/Figura%25207.18.%2520Forecast%2520multivariable%2520en%2520la%2520UE%2520B%C3%A1varo.png)
* [Figura 7.19. Escenario predictivo multivariable avanzado en la UE Maya](https://www.google.com/search?q=./imgs/Figura%25207.19.%2520Forecast%2520multivariable%2520en%2520la%2520UE%2520Maya.png)

### Entorno Cloud Productivo Corporativo (Producción)

* [Figura 8.1. Arquitectura del pipeline y comportamiento secuencial interno de la API](https://www.google.com/search?q=./imgs/Figura%25208.1.%2520Comportamiento%2520anal%C3%ADtico%2520interno%2520de%2520la%2520API%2520REST%2520corporativa..png)
* [Figura 8.2. Topología de implantación de recursos inmutables en Microsoft Azure](https://www.google.com/search?q=./imgs/Figura%25208.2.%2520Arquitectura%2520de%2520implantaci%C3%B3n%2520en%2520entorno%2520corporativo.png)

---

## Variables de Entorno y Configuración de Seguridad

Para desplegar y ejecutar de manera local o en la nube el microservicio contenido en `saih-ai/`, es un requisito técnico indispensable instanciar un archivo de secretos corporativos `.env` en la raíz de dicho directorio que contenga las siguientes cadenas de conexión cifradas heredadas de la infraestructura:

```env
# CREDENCIALES EXTRACCIÓN ERP SAP
SAP_SOAP_ENDPOINT=[https://sap-erp.bhg-corp.com/v1/Z_FBL1N_WS](https://sap-erp.bhg-corp.com/v1/Z_FBL1N_WS)
SAP_USER=AUDIT_USER_PROXY
SAP_PASSWORD=CriptoPasswordToken88

# SEGURIDAD DE ACCESO CAPA SERVICIOS
X_API_KEY=Bbhg_Crypto_Secure_Service_Token_2026

# GOBERNANZA PERSISTENCIA CLOUD MICROSOFT AZURE
AZURE_SQL_CONNECTION_STRING=Driver={ODBC Driver 18 for SQL Server};Server=tcp:sql-saih-ai-test.database.windows.net...
AZURE_BLOB_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=st-saih-ai-test...

```

---

## Autoría y Licencia

* **Proyecto:** Trabajo de Fin de Grado (TFG) - Ciencia de Datos e Inteligencia Artificial.
* **Universidad:** Escuela Técnica Superior de Ingenieros Informáticos - Universidad Politécnica de Madrid (**UPM**).
* **Entorno de Aplicación:** Barceló Hotel Group (BHG) - Área Corporativa de Auditoría Interna.
* **Licencia:** Derechos reservados y confidenciales para uso e implantación interna de la organización.

```
