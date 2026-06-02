# SAIH‑AI

## Descripción

SAIH‑AI es una aplicación basada en FastAPI orientada a la automatización del análisis de cuentas por pagar a partir de extractos SAP FBL1N.

El sistema permite ejecutar pipelines de análisis, detectar incidencias financieras y generar solicitudes de auditoría de forma automática, siguiendo un enfoque modular y escalable que facilita la incorporación de nuevos tipos de informes.

---

##  Arquitectura del proyecto

El proyecto sigue una arquitectura modular basada en la separación de responsabilidades, facilitando la reutilización, mantenibilidad y escalabilidad del sistema.

###  Estructura del repositorio

```

.github/
│   ├── workflows/
│   │   ├── cd-deploy.yml
│   │   ├── ci-docker.yml
│   │   ├── cicd.yml
│
app/
│
├── core/
│   ├── __init__.py
│   ├── config.py
│   ├── auth.py
│
├── infrastructure/
│   ├── __init__.py
│   ├── sap\_client.py
│   ├── storage.py
│
├── shared/
│   ├── __init__.py
│   ├── models.py
│   ├── jobs.py
│   ├── hotel\_map.py
│
├── reports/  
│   ├── cxp/
│   │   ├── **init**.py
│   │   ├── main\_cxp.py
│   │   ├── pipeline\_cxp.py
│   │
│   ├── */                          
│   │   ├── __init__.py
│   │   ├── main_*.py
│   │   ├── pipeline_*.py
│
├── main.py  
│
.gitignore
Dockerfile
requirements.txt
README.md
VERSION

````

---

## Principios de diseño

- **Separación de responsabilidades**:
  - `core`: lógica transversal (configuración, autenticación)
  - `infrastructure`: acceso a sistemas externos (SAP, almacenamiento)
  - `shared`: componentes reutilizables entre informes
  - `reports`: lógica específica por tipo de análisis

- **Escalabilidad**:
  Cada informe se implementa como un módulo independiente dentro de `reports/`, permitiendo añadir nuevos análisis sin afectar al resto del sistema.

- **Reutilización**:
  Componentes como la conexión a SAP o el almacenamiento en Azure se centralizan para evitar duplicidad de código.

- **Desacoplamiento**:
  La lógica de negocio (pipeline) está separada de los endpoints (API), facilitando pruebas, mantenimiento y evolución del sistema.

---

## Ejecución del proyecto

### Ejecución local

```bash
uvicorn app.main:app --reload
````

***

### Ejecución con Docker

```bash
docker build -t saih-ai .
docker run -p 8080:8080 saih-ai
```

***

## API

La aplicación expone endpoints REST mediante FastAPI.

Documentación interactiva disponible en:

```
/docs
```

***

## Informes disponibles

Actualmente el sistema incluye los siguientes informes:

* **CXP (Accounts Payable)** → `app/reports/cxp`

Cada informe define:

* `main_*.py` → endpoints de la API
* `pipeline_*.py` → lógica de procesamiento y análisis

***

##  Integraciones

* **SAP**  
  `app/infrastructure/sap_client.py`  
  Gestión de extracción de datos (FBL1N)

* **Azure Blob Storage**  
  `app/infrastructure/storage.py`  
  Almacenamiento de resultados (Excel y outputs)

***

## Dependencias

Instalar dependencias:

```bash
pip install -r requirements.txt
```

***

## Configuración

El sistema utiliza variables de entorno para:

* credenciales SAP
* conexión a Azure
* claves de API

Se recomienda utilizar un archivo `.env` en desarrollo.

***

## Uso con agentes (Foundry)

El backend está diseñado para ser consumido por agentes de IA (por ejemplo, Microsoft Foundry), mediante endpoints asíncronos que permiten:

* iniciar análisis
* consultar estado del proceso
* obtener resultados finales

Este enfoque permite desacoplar:

* procesamiento de datos (API)
* interacción conversacional (agente)

***

## Versionado

La versión del servicio se gestiona mediante el archivo:

```
VERSION
```

***

## Licencia

Uso interno 
