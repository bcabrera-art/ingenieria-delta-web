# Arquitectura Multi-Agente (4 Agentes) — Ingeniería Delta Aysén (`ingenieriadelta.cl`)

Esta carpeta contiene toda la infraestructura de automatización multi-agente que conecta el cotizador web (`index.html`, `assets/js/app.js`, `enviar.php`), **WhatsApp (`+56 9 6741 3329`)**, la **Base de Datos de Precios de Proveedores Delta**, el **CRM** y el **Google Calendar de `bcabrera@ingenieriadelta.cl`**.

---

## 1. Los 4 Agentes Especializados (LangGraph `StateGraph` + FastAPI)

| Orden | Agente | Archivo | Responsabilidad Principal |
|---|---|---|---|
| **1** | **Agente Comercial** (`CommercialAgent`) | `app/agents/commercial_agent.py` | Habla con el cliente, cruza adjuntos (`boleta_pdf` / `foto_generador`), almacena el Expediente Único en el CRM/Embudo, actúa como **puerta de entrada condicional al Financiamiento Largo Plazo Alza Dédalo / Sunplug** (*sí y solo sí* hay interés en $0 pie y cuotas a 10, 15, 20 o 25 años), y una vez aprobada la cotización por el Agente 4 vuelve con el cliente para presentarla y agendar en `bcabrera@ingenieriadelta.cl`. |
| **2** | **Solution Engineer** (`SolutionEngineerAgent`) | `app/agents/solution_engineer_agent.py` | En función del expediente del Agente 1, realiza la pre-ingeniería conceptual, dimensionamiento patagónico y entrega el **BOQ completo (Listado de Materiales)** sin precios: paneles (610W/715W), inversores/MPPT (Huawei / Victron), baterías (Pylontech LiFePO4), protecciones eléctricas AC/DC (termomagnéticos, diferenciales, SPD, fusibles MEGA/gPV, tableros IP65), estructura y ferretería eléctrica, más unidades de instalación. |
| **3** | **Agente Cotizador** (`PricingAndQuoteAgent`) | `app/agents/pricing_agent.py` | Cruza el BOQ con la **Base de Datos de Lista de Precios de Proveedores Delta** (`data/delta_price_catalog.json`), calcula un **9% de logística y flete a la Región de Aysén y obra** sobre el costo de los equipos, aplica un **20% de utilidad** sobre Equipos, sobre Logística y sobre Instalación (subcontrato de mano de obra), obtiene el **Precio Final Neto para el Cliente** y genera el PDF corporativo No Vinculante. |
| **4** | **Inspector Técnico QA** (`TechnicalInspectorAgent`) | `app/agents/inspector_agent.py` | Audita con un **Checklist de 5 categorías** (`CHK-01` a `CHK-05`) el trabajo de los Agentes 1, 2 y 3 (coherencia comercial $\leftrightarrow$ ingeniería, unidades físicas, simetría de fases, ausencia de precios `$0`, exactitud del 9% flete + 20% utilidad y legibilidad del PDF). Si algo falla, devuelve automáticamente la tarea al Agente 2 o 3 para corregirlo antes de liberar el PDF al Agente 1. |

---

## 2. Cómo Ejecutar y Probar Localmente

### A. Ejecutar la Suite de Pruebas Automatizadas (`pytest`)
Desde la raíz del repositorio:
```powershell
python -m pytest automation/delta-solar-engine/tests/test_multiagent_pipeline.py -v
```

### B. Levantar el Servidor Multi-Agente FastAPI Localmente
```powershell
cd automation/delta-solar-engine
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
Documentación interactiva Swagger disponible en: `http://127.0.0.1:8000/docs`

### C. Levantar toda la Pila con Docker Compose (Engine + n8n + Evolution API WhatsApp)
```powershell
cd automation
Copy-Item .env.example .env
docker compose up -d --build
```
- **API Multi-Agente (`delta-solar-engine`)**: `http://localhost:8000`
- **Panel Visual n8n**: `http://localhost:5678` (importar los 2 flujos de `automation/n8n_workflows/`)
- **Evolution API (QR WhatsApp `+56 9 6741 3329`)**: `http://localhost:8080/manager`
