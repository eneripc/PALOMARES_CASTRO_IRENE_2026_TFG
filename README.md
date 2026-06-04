# Auditoría Continua y Análisis Predictivo de Cuentas por Pagar (CxP) medianteIA

Este repositorio contiene la implementación integral del sistema desarrollado para la automatización analítica, detección de anomalías y auditoría conversacional sobre extractos transaccionales SAP FBL1N en entornos corporativos (caso de estudio aplicado a las Unidades de Explotación de Maya y Bávaro en Barceló Hotel Group).

El ecosistema está estructurado en dos vertientes: el núcleo analítico de experimentación/modelado en la raíz y la infraestructura del servicio cloud de producción empaquetada dentro del subdirectorio `saih-ai/`.

---

## Estructura General del Repositorio

```text
tfg-ml-audit/
├── .github/workflows/           
│           
├── src/                         
│   ├── data_pipeline.py         
│   ├── ml_pipeline.py          
│   ├── CxP_analisis.ipynb      
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

Para realizar consultas o verificaciones gráficas rápidas sobre el marco teórico y analítico expuesto en la memoria del TFG, puedes consultar de manera directa las imágenes indexadas dentro del repositorio en la carpeta imgs/

---

## Autoría y Licencia

* **Proyecto:** Trabajo de Fin de Grado (TFG) - Ciencia de Datos e Inteligencia Artificial.
* **Universidad:** Escuela Técnica Superior de Ingenieros Informáticos - Universidad Politécnica de Madrid (**UPM**).
* **Entorno de Aplicación:** Barceló Hotel Group (BHG) - Área Corporativa de Auditoría Interna.
* **Licencia:** Derechos reservados y confidenciales para uso e implantación interna de la organización.
