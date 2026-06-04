# tfg-ml-audit

# Auditoría Continua y Análisis Predictivo de Cuentas por Pagar (CxP) mediante Machine Learning e IA Cognitiva

Este repositorio contiene la implementación integral del sistema desarrollado para la automatización analítica, detección de anomalías y auditoría conversacional sobre extractos transaccionales SAP FBL1N en entornos corporativos (caso de estudio aplicado a las Unidades de Explotación de Maya y Bávaro en Barceló Hotel Group).

El ecosistema está estructurado en dos vertientes: el núcleo analítico de experimentación/modelado en la raíz y la infraestructura del servicio cloud de producción empaquetada dentro del subdirectorio `saih-ai/`.

---

## Estructura General del Repositorio

```text
tfg-ml-audit/
├── .github/workflows/          # Pipelines CI/CD corporativos (GitHub Actions)
│           
├── src/                        # Scripts de ingeniería de datos y modelado
│   ├── data_pipeline.py        # Funciones helper, ETL, casuística y reglas analíticas
│   ├── ml_pipeline.py          # Modelos de Machine Learning y algoritmos de Forecasting
│   ├── CxP_analisis.ipynb      # Pipeline analítico y ejecución completa de experimentos
│   └── README.md
│                 
├── outputs/
│   ├── Excel_Maya.xlsx          
│   ├── Excel_Bavaro.xlsx                        
│   ├── ML_Maya.xlsx            
│   └── ML_Bavaro.xlsx          
│
├── imgs/                       
│   └── [Figura_*.png]           
│
├── saih-ai/                     
│   ├── app/                     
│   ├── Dockerfile               
│   ├── main.py                  
│   ├── tool_fbl1n.json          
│   └── requirements.txt         
│
├── .gitignore                   
└── README.md                    

```
---
## Flujo Lógico de Cómputo Inter-Componente
El sistema opera mediante una separación estricta de responsabilidades entre el entorno de investigación experimental y el ecosistema web productivo:

```
┌─────────────────────────────────┐
│     CxP_analisis.ipynb          │ ◄── (Cuaderno orquestador interactivo del TFG)
└────────────────┬────────────────┘
                 │
                 ▼ Invocación de módulos locales
┌─────────────────────────────────┐
│       src/data_pipeline.py      │ ◄── (Extracción SAP, Limpieza Transaccional y Reglas Heurísticas)
└────────────────┬────────────────┘
                 │
                 ▼ Inyección de características estructuradas
┌─────────────────────────────────┐
│   src/ml_pipeline.py            │ ◄── (Zero-Shot NLP, Ensambles Random Forest y Series Temporales)
└────────────────┬────────────────┘
                 │
                 ▼ Escritura de artefactos binarios de control
┌─────────────────────────────────┐
│            outputs/             │ ◄── (Libros Excel multi-página formateados para el Auditor)
└─────────────────────────────────┘

```

1. CxP_analisis.ipynb: Actúa como el orquestador interactivo para la validación científica. Ejecuta secuencialmente las celdas invocando a los scripts de la carpeta src/.

2. src/data_pipeline.py: Asume las tareas de ingeniería de datos. Limpia el ruido del extracto SAP, normaliza monedas, aplica etiquetas semánticas y evalúa los controles de anticipos o facturas duplicadas.

3. src/ml_pipeline.py: Consolida los modelos predictivos y series temporales. Entrena el ensamble supervisado (Random Forest) para computar el Score de Riesgo Global, ejecuta el aislamiento estadístico (Isolation Forest) y proyecta las tendencias futuras (SARIMAX / Prophet).

4. outputs/: Almacena los resultados del pipeline en un libro Excel multi-página formateado, aislando los casos candidatos a auditoría sustantiva.

Para consultar las guías técnicas de despliegue cloud en la infraestructura de Microsoft Azure, uvicorn y contenerización Docker del Agente conversacional, acceda de forma directa al saih-ai/README.md.
---

## Índice Temático de Evidencias e Ilustraciones (`imgs/`)

Para realizar consultas o verificaciones gráficas rápidas sobre el marco teórico y analítico expuesto en la memoria del TFG, puedes consultar de manera directa las imágenes indexadas dentro del repositorio:

* [Figura 3.1. Arquitectura de acceso a datos](https://www.google.com/search?q=./imgs/Figura%25203.1.%2520Arquitectura%2520de%2520acceso%2520a%2520datos.png)
* [Figura 4.1. Flujo general de control del sistema](https://www.google.com/search?q=./imgs/Figura%25204.1%2520.Flujo%2520general%2520del%2520sistema.png)
* [Figura 4.2. Clasificación heurística de partidas contables](https://www.google.com/search?q=./imgs/Figura%25204.2.%2520Clasificaci%C3%B3n%2520de%2520partidas%2520contables.png)
* [Figura 4.3. Generación automatizada de solicitudes a proveedores](https://www.google.com/search?q=./imgs/Figura%25204.3.%2520Generaci%C3%B3n%2520de%2520solicitudes%2520a%2520proveedores.png)
* [Figura 4.4. Ecuación y cálculo del riesgo global unificado](https://www.google.com/search?q=./imgs/Figura%25204.4.%2520C%C3%A1lculo%2520del%2520riesgo%2520global.png)

* [Figura 7.1. Distribución de la casuística de control interno por UE](https://www.google.com/search?q=./imgs/Figura%25207.1.%2520Distribuci%C3%B3n%2520de%2520la%2520casu%C3%ADstica%2520por%2520unidad%2520de%2520explotaci%C3%B3n%2520%2528UE%2529.png)
* [Figura 7.2. Distribución de análisis macro por UE (Top categorías)](https://www.google.com/search?q=./imgs/Figura%25207.2.%2520Distribuci%C3%B3n%2520del%2520an%C3%A1lisis%2520por%2520unidad%2520de%2520explotaci%C3%B3n%2520%2528Top%2520categor%C3%ADas%2529.png)
* [Figura 7.3. Concentración y distribución del análisis de anticipos por UE](https://www.google.com/search?q=./imgs/Figura%25207.3.%2520Distribuci%C3%B3n%2520del%2520an%C3%A1lisis%2520de%2520anticipos%2520por%2520unidad%2520de%2520explotaci%C3%B3n.png)
* [Figura 7.4. Distribución de etiquetas normativas Zero‑Shot por UE](https://www.google.com/search?q=./imgs/Figura%25207.4.%2520Distribuci%C3%B3n%2520de%2520etiquetas%2520Zero%E2%80%91Shot%2520por%2520unidad%2520de%2520explotaci%C3%B3n.png)
* [Figura 7.5. Distribución de la densidad del score de riesgo global por UE](https://www.google.com/search?q=./imgs/Figura%25207.5.%2520Distribuci%C3%B3n%2520del%2520score%2520de%2520riesgo%2520global%2520por%2520unidad%2520de%2520explotaci%C3%B3n.png)
* [Figura 7.8. Distribución de niveles jerárquicos de riesgo por UE](https://www.google.com/search?q=./imgs/Figura%25207.8.%2520Distribuci%C3%B3n%2520de%2520niveles%2520de%2520riesgo%2520por%2520unidad%2520de%2520explotaci%C3%B3n.png)
* [Figura 7.9. Dispersión del riesgo medio y porcentaje de duplicidades por UE](https://www.google.com/search?q=./imgs/Figura%25207.9.%2520Riesgo%2520medio%2520y%2520porcentaje%2520de%2520duplicados%2520por%2520unidad%2520de%2520explotaci%C3%B3n.png)


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


* [Figura 8.1. Arquitectura del pipeline y comportamiento secuencial interno de la API](https://www.google.com/search?q=./imgs/Figura%25208.1.%2520Comportamiento%2520anal%C3%ADtico%2520interno%2520de%2520la%2520API%2520REST%2520corporativa..png)
* [Figura 8.2. Topología de implantación de recursos inmutables en Microsoft Azure](https://www.google.com/search?q=./imgs/Figura%25208.2.%2520Arquitectura%2520de%2520implantaci%C3%B3n%2520en%2520entorno%2520corporativo.png)

---

## Autoría y Licencia

* **Proyecto:** Trabajo de Fin de Grado (TFG) - Ciencia de Datos e Inteligencia Artificial.
* **Universidad:** Escuela Técnica Superior de Ingenieros Informáticos - Universidad Politécnica de Madrid (**UPM**).
* **Entorno de Aplicación:** Barceló Hotel Group (BHG) - Área Corporativa de Auditoría Interna.
* **Licencia:** Derechos reservados y confidenciales para uso e implantación interna de la organización.
