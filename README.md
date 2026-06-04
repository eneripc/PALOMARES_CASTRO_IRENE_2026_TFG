# Auditoría Continua y Análisis Predictivo de Cuentas por Pagar (CxP) mediante IA

Este repositorio contiene la implementación integral del sistema desarrollado para la automatización analítica, detección estadística de anomalías y auditoría conversacional sobre extractos transaccionales SAP `FBL1N` en entornos corporativos de alta descentralización (caso de estudio aplicado a las Unidades de Explotación de Maya y Bávaro en Barceló Hotel Group).

El ecosistema de software está estructurado de forma desacoplada en dos grandes vertientes: el núcleo analítico de experimentación, modelado y validación en la raíz de la solución, y la infraestructura del servicio *cloud* de producción empaquetada y contenerizada dentro del subdirectorio especializado `saih-ai/`.

---

## Estructura General del Repositorio

Aquí tienes el archivo README.md completo en texto plano (Markdown). He limpiado por completo los comentarios con # del árbol de directorios para que la estructura sea puramente visual, limpia y mucho más fácil de leer, manteniendo todas las correcciones formales requeridas para tu entrega:

Markdown
# Auditoría Continua y Análisis Predictivo de Cuentas por Pagar (CxP) mediante IA

Este repositorio contiene la implementación integral del sistema desarrollado para la automatización analítica, detección estadística de anomalías y auditoría conversacional sobre extractos transaccionales SAP `FBL1N` en entornos corporativos de alta descentralización (caso de estudio aplicado a las Unidades de Explotación de Maya y Bávaro en Barceló Hotel Group).

El ecosistema de software está estructurado de forma desacoplada en dos grandes vertientes: el núcleo analítico de experimentación, modelado y validación en la raíz de la solución, y la infraestructura del servicio *cloud* de producción empaquetada y contenerizada dentro del subdirectorio especializado `saih-ai/`.

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

El sistema opera mediante una separación estricta de responsabilidades entre el entorno de investigación experimental de ciencia de datos y el ecosistema web productivo *serverless*:

```
┌─────────────────────────────────┐
│       CxP_analisis.ipynb        │ ◄── (Cuaderno orquestador interactivo del TFG)
└────────────────┬────────────────┘
                 │
                 ▼ Invocación de módulos locales
┌─────────────────────────────────┐
│      src/data_pipeline.py       │ ◄── (Extracción SAP, Limpieza Transaccional y Reglas Heurísticas)
└────────────────┬────────────────┘
                 │
                 ▼ Inyección de características estructuradas (Feature Engineering)
┌─────────────────────────────────┐
│       src/ml_pipeline.py        │ ◄── (Zero-Shot NLP, Ensambles Random Forest y Series Temporales)
└────────────────┬────────────────┘
                 │
                 ▼ Escritura de artefactos binarios de control e informes
┌─────────────────────────────────┐
│            outputs/             │ ◄── (Libros Excel multi-página formateados para el Auditor)
└─────────────────────────────────┘

```

1. **`CxP_analisis.ipynb`**: Actúa como el entorno de desarrollo y orquestación interactiva para la validación científica del *pipeline*. Permite al científico de datos ejecutar de forma secuencial los experimentos visuales invocando los módulos residentes en `src/`.
2. **`src/data_pipeline.py`**: Asume de forma centralizada las tareas de ingeniería de datos. Se encarga de mitigar el ruido estructural de los extractos transaccionales de SAP, normalizar variables cualitativas, formatear campos temporales (`NaT`) y evaluar de forma heurística las reglas de negocio agregadas para anticipos, retenciones de obra y duplicados.
3. **`src/ml_pipeline.py`**: Consolida la capa de inteligencia artificial híbrida y modelos estadísticos. Aplica vectorizaciones TF-IDF con n-gramas para clasificaciones semánticas *Zero-Shot*, entrena el algoritmo *Isolation Forest* para el aislamiento de anomalías masivas y despliega la estrategia multivariante combinada con *Random Forest* para el *forecasting* de riesgo estacional.
4. **`outputs/`**: Almacena de forma persistente los entregables del sistema en formato de hojas de cálculo Excel multi-página de alta visibilidad, aislando los proveedores críticos y las partidas que requieren intervenciones de auditoría sustantiva inmediata.

---

## Capa de Producción, Despliegue e Interoperabilidad (`saih-ai/`)

El subdirectorio `saih-ai/` alberga el código fuente listo para producción del sistema inteligente. El *backend* está diseñado como una API REST asíncrona implementada con **FastAPI** que delega subtareas complejas mediante identificadores unívocos (`job_id`), siguiendo las buenas prácticas de arquitectura de microservicios distribuidos para la mitigación de latencias HTTP.

Para consultar el manual técnico de implantación, configuración de contenedores mediante el `Dockerfile`, orquestación de llamadas y herramientas (*function calling*) en **Azure AI Foundry**, gestión perimetral *Zero Trust*, secretos en `Key Vault` y despliegue automatizado por *pipelines* en **Azure Container Apps**, consulte de manera directa el archivo especializado [saih-ai/README.md](https://www.google.com/search?q=./saih-ai/README.md).

---

## Índice Temático de Evidencias e Ilustraciones (`imgs/`)

Para realizar consultas rápidas o verificaciones gráficas sobre el marco teórico, el modelo dimensional y el flujo analítico expuesto en la memoria impresa de este Trabajo de Fin de Grado, puedes acceder a los diagramas arquitectónicos indexados en la carpeta `imgs/`. Estos recursos ilustran de forma visual la interconexión de componentes *cloud*, árboles de decisión algorítmicos y mapas de dispersión bidimensionales resultantes de la reducción de dimensionalidad con PCA.

---

## Autoría y Licencia

* **Proyecto:** Trabajo de Fin de Grado (TFG) - Grado en Ciencia de Datos e Inteligencia Artificial.
* **Universidad:** Escuela Técnica Superior de Ingeniería de Sistemas Informáticos (**ETSISI**) - Universidad Politécnica de Madrid (**UPM**).
* **Entorno de Aplicación de Campo:** Barceló Hotel Group (BHG) - Dirección Corporativa de Auditoría Interna.
* **Tutoría Académica:** Dr. Alejandro Martín.
* **Licencia:** Derechos estrictamente reservados y de carácter altamente confidencial para el uso, explotación e implantación exclusiva interna de la organización.

```
