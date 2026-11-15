"""
Servidor Principal FastAPI (delta-solar-engine) — Orquestador de los 4 Agentes de Ingeniería Delta Aysén.
Expone endpoints REST para:
  1. POST /api/v1/leads/ingest        -> Ejecuta el pipeline de 4 agentes (Comercial -> Solution Engineer -> Cotizador -> Inspector QA)
  2. GET  /api/v1/leads/lookup        -> Cruza por teléfono o código #DLT-XXXX para WhatsApp y Timer Proactivo de 2 min
  3. POST /api/v1/leads/handoff       -> Pausa/reactiva el bot ante intervención humana (fromMe: true)
  4. GET  /api/v1/crm/funnel          -> Devuelve el embudo de ventas y expedientes para CRM
  5. GET  /api/v1/catalog/prices      -> Devuelve la lista de precios de proveedores de Delta (delta_price_catalog.json)
  6. GET  /api/v1/calendar/slots      -> Consulta horarios libres reales de 30 min en bcabrera@ingenieriadelta.cl
  7. POST /api/v1/calendar/book       -> Valida y agenda reunión/visita de 30 min en bcabrera@ingenieriadelta.cl
"""
from __future__ import annotations

import base64
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.agents.pricing_agent import load_delta_price_catalog
from app.calendar_service import get_available_slots, validate_requested_slot
from app.catalog_sync import FULL_SUPPLIERS_JSON_PATH, sync_catalog_from_excel
from app.database import DeltaCRMDatabase
from app.graph import run_delta_quote_pipeline
from app.whatsapp_gateway import WhatsAppGateway

app = FastAPI(
    title="Delta Solar Engine — Arquitectura Multi-Agente (4 Agentes)",
    description=(
        "1. Agente Comercial (Levantamiento + Gate Dédalo $0 Pie) -> "
        "2. Solution Engineer (Pre-Ingeniería + BOQ + Ferretería) -> "
        "3. Agente Cotizador (Catálogo Proveedores Delta + 9% Flete Aysén + 20% Utilidad + PDF) -> "
        "4. Inspector Técnico QA (Checklist de Verificación) -> Vuelta al Agente Comercial."
    ),
    version="2.0.0",
)

db = DeltaCRMDatabase()
wa_gateway = WhatsAppGateway()


class LeadIngestRequest(BaseModel):
    lead_ref: Optional[str] = None
    nombre: str = "Cliente Por Confirmar"
    empresa: str = "Particular / Hogar"
    correo: str = ""
    telefono: str = ""
    ubicacion: str = "Coyhaique"
    zona_climatica: Optional[str] = None
    linea: str = "red"
    consumo: Optional[str] = None
    consumo_mensual_clp: Optional[int] = None
    consumo_mensual_kwh: Optional[float] = None
    potencia_generador: Optional[str] = None
    potencia_generador_kva: Optional[float] = None
    fase_generador: Optional[str] = None
    fase_sistema: Optional[str] = None
    tipo: Optional[str] = None
    origen: str = "web_cotizador"
    servicios: List[str] = Field(default_factory=list)
    simulacion: str = ""
    mensaje: str = ""
    incluye_baterias: Optional[bool] = None
    interested_in_zero_down_long_term: Optional[bool] = None
    preferred_term_years: Optional[int] = 25
    rut_titular: Optional[str] = None
    is_property_owner_cbr: Optional[bool] = None
    property_address: Optional[str] = None
    attachments: List[Dict[str, Any]] = Field(default_factory=list)
    send_whatsapp_immediately: bool = False


class HandoffRequest(BaseModel):
    phone: str
    paused: bool = True
    reason: str = "manual_intervention_from_phone"


class CalendarBookingRequest(BaseModel):
    lead_ref: Optional[str] = None
    nombre: str
    correo: str
    telefono: str
    start_iso: str
    modalidad: str = "Reunión Técnica Online (Google Meet 30 min)"
    notas: str = ""


@app.get("/health")
def health_check() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service": "delta-solar-engine-4-agents",
        "calendar_owner": "bcabrera@ingenieriadelta.cl",
    }


@app.post("/api/v1/leads/ingest")
def ingest_and_run_multiagent_pipeline(payload: LeadIngestRequest) -> Dict[str, Any]:
    """
    Ejecuta el flujo completo de los 4 Agentes:
      Agente 1 (Comercial) -> Agente 2 (Solution Engineer BOQ) ->
      Agente 3 (Cotizador + 9% Logística Aysén + 20% Utilidad + PDF) ->
      Agente 4 (Inspector Técnico QA Checklist) -> Agente 1 (Presentación al Cliente).
    """
    final_state = run_delta_quote_pipeline(payload.model_dump())
    saved_record = db.save_pipeline_state(final_state)

    exp = final_state["expediente"]
    quote = final_state["pricing_quote"]
    inspector = final_state["inspector_report"]
    presentation_msg = final_state.get("commercial_presentation_message", "")

    wa_receipt = None
    if payload.send_whatsapp_immediately and inspector.approved and exp.telefono:
        if not db.is_bot_paused(exp.telefono):
            wa_receipt = wa_gateway.send_proposal_message_and_pdf(
                phone=exp.telefono,
                message_text=presentation_msg,
                pdf_filename=quote.pdf_filename,
                pdf_base64=quote.pdf_base64 or "",
            )

    return {
        "ok": True,
        "lead_ref": exp.lead_ref,
        "inspector_approved": inspector.approved,
        "iterations_used": final_state.get("iteration_count", 1),
        "expediente": exp.model_dump(),
        "engineering_boq": final_state["engineering_boq"].model_dump(),
        "pricing_quote": quote.model_dump(exclude={"pdf_base64"}),
        "inspector_report": inspector.model_dump(),
        "commercial_presentation_message": presentation_msg,
        "available_calendar_slots": final_state.get("available_calendar_slots", []),
        "audit_trail": final_state.get("audit_trail", []),
        "whatsapp_delivery": wa_receipt,
        "crm_saved": True,
    }


@app.get("/api/v1/leads/lookup")
def lookup_lead(
    q: str = Query(..., description="Código #DLT-XXXX o teléfono del cliente (+569...)"),
    mark_contacted: bool = Query(False, description="Si es True, marca wa_contacted=1 para cancelar el envío proactivo de 2 min"),
) -> Dict[str, Any]:
    record = db.get_lead_by_ref_or_phone(q)
    if not record:
        return {"found": False, "bot_paused": db.is_bot_paused(q)}

    if mark_contacted:
        db.mark_whatsapp_contacted(record["lead_ref"])
        record["wa_contacted"] = 1

    # Cargar base64 del PDF si existe en disco para que n8n pueda enviarlo de inmediato
    pdf_path = Path(record.get("pdf_path") or "")
    pdf_b64 = base64.b64encode(pdf_path.read_bytes()).decode("ascii") if pdf_path.exists() else None
    record["pdf_base64"] = pdf_b64
    record["found"] = True
    return record


@app.get("/api/v1/proposals/{lead_ref}/pdf")
def download_proposal_pdf(lead_ref: str):
    clean_ref = lead_ref if lead_ref.startswith("#") else f"#{lead_ref}"
    record = db.get_lead_by_ref_or_phone(clean_ref) or db.get_lead_by_ref_or_phone(lead_ref)
    if not record or not record.get("pdf_path"):
        raise HTTPException(status_code=404, detail="Propuesta PDF no encontrada para este expediente.")
    path = Path(record["pdf_path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="Archivo PDF no existe en disco.")
    return FileResponse(str(path), media_type="application/pdf", filename=record["pdf_filename"])


@app.post("/api/v1/leads/handoff")
def update_human_handoff(req: HandoffRequest) -> Dict[str, Any]:
    return db.set_human_handoff(phone=req.phone, paused=req.paused, reason=req.reason)


@app.get("/api/v1/crm/funnel")
def get_crm_funnel(limit: int = 50) -> Dict[str, Any]:
    leads = db.list_leads_funnel(limit=limit)
    return {"count": len(leads), "leads": leads}


@app.get("/api/v1/catalog/prices")
def get_supplier_price_catalog() -> Dict[str, Any]:
    return load_delta_price_catalog()


@app.post("/api/v1/catalog/sync-excel")
def sync_supplier_catalog_from_excel() -> Dict[str, Any]:
    """
    Sincroniza en vivo `delta_price_catalog.json` y `delta_suppliers_consolidated_full.json`
    desde `Consolidado Precios al 08052026.xlsx` (`EMAT - Lista ELITE`, `MacroSolar`,
    `VITEL`, `RBR`) y `rbr_nov26.json`, usando copia temporal segura para funcionar
    incluso si el archivo está abierto en Microsoft Excel.
    """
    return sync_catalog_from_excel()


@app.get("/api/v1/catalog/suppliers-search")
def search_consolidated_suppliers(
    q: str = Query("", description="Texto a buscar en los 1.537+ ítems de EMAT, MacroSolar, VITEL y RBR"),
    supplier: Optional[str] = Query(None, description="Filtrar por pestaña/proveedor"),
    limit: int = Query(30, ge=1, le=200),
) -> Dict[str, Any]:
    import json

    if not FULL_SUPPLIERS_JSON_PATH.exists():
        sync_catalog_from_excel()
    data = json.loads(FULL_SUPPLIERS_JSON_PATH.read_text(encoding="utf-8"))
    catalog_by_supplier = data.get("catalog_by_supplier", {})
    q_low = q.strip().lower()
    results: List[Dict[str, Any]] = []
    for sheet_name, items in catalog_by_supplier.items():
        if supplier and supplier.lower() not in sheet_name.lower():
            continue
        for item in items:
            haystack = f"{item.get('grupo','')} {item.get('marca','')} {item.get('producto','')} {item.get('sku_proveedor','')}".lower()
            if not q_low or q_low in haystack:
                results.append(item)
                if len(results) >= limit:
                    break
        if len(results) >= limit:
            break
    return {
        "query": q,
        "supplier_filter": supplier,
        "count": len(results),
        "total_indexed": data.get("total_items", 0),
        "results": results,
    }


@app.get("/api/v1/calendar/slots")
def list_calendar_slots(max_slots: int = 5) -> Dict[str, Any]:
    slots = get_available_slots(max_slots=max_slots)
    return {
        "calendar_owner": "bcabrera@ingenieriadelta.cl",
        "window_policy": "Lunes a Viernes 09:30 a 18:00 hrs (America/Santiago), anticipación >= 2h, buffer 15m",
        "available_slots": slots,
    }


@app.post("/api/v1/calendar/book")
def book_calendar_meeting(req: CalendarBookingRequest) -> Dict[str, Any]:
    ok, msg, event_data = validate_requested_slot(req.start_iso)
    if not ok or not event_data:
        raise HTTPException(status_code=422, detail=msg)

    return {
        "ok": True,
        "message": msg,
        "booking": {
            **event_data,
            "summary": f"[{req.lead_ref or 'DELTA'}] {req.modalidad} — {req.nombre} (Ingeniería Delta Aysén)",
            "attendees": ["bcabrera@ingenieriadelta.cl", "cdiaz@ingenieriadelta.cl", req.correo],
            "customer_phone": req.telefono,
            "notes": req.notas,
        },
    }
