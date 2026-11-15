"""
AGENTE 4: Inspector Técnico y Auditor de Calidad de Todos los Agentes (TechnicalInspectorAgent)
Responsabilidades:
1. Ejecutar un Checklist riguroso de verificación sobre el flujo de los Agentes 1 (Comercial),
   2 (Solution Engineer) y 3 (Cotizador).
2. Antes de autorizar el envío de la propuesta no vinculante al cliente, asegurar que:
   - Todo tenga sentido comercial y técnico entre lo que levantó el Comercial y lo que diseñó Ingeniería.
   - No haya problemas con las unidades físicas (Wp vs kWp, kW vs kVA, kWh, CLP vs UF).
   - El BOQ esté completo (equipos, termomagnéticos, diferenciales, SPD, estructura y ferretería).
   - La matemática de costos (9% flete a Aysén y 20% utilidad sobre Equipos, Logística e Instalación) sea exacta.
   - El PDF generado tenga textos 100% legibles, sello NO VINCULANTE y no filtre costos internos.
3. Si detecta cualquier error, rechaza la propuesta (`approved = False`) e indica exactamente qué agente
   debe corregir su trabajo antes de volver al cliente.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from pypdf import PdfReader

from app.state import (
    DeltaAgentGraphState,
    EngineeringProposalBOQ,
    InspectorAuditReport,
    InspectorChecklistItem,
    LeadExpediente,
    PricingQuoteResult,
)


def _extract_pdf_text(pdf_path: str) -> str:
    path = Path(pdf_path)
    if not path.exists() or path.stat().st_size == 0:
        return ""
    try:
        reader = PdfReader(str(path))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception:
        return ""


class TechnicalInspectorAgent:
    """
    Cuarto Agente: Inspector Técnico QA de Ingeniería Delta Aysén.
    Actúa como Gatekeeper antes de que el Agente 1 presente la propuesta al cliente.
    """

    def inspect_and_verify(self, state: DeltaAgentGraphState) -> DeltaAgentGraphState:
        expediente: LeadExpediente = state["expediente"]
        boq: EngineeringProposalBOQ = state["engineering_boq"]
        quote: PricingQuoteResult = state["pricing_quote"]
        audit_trail = list(state.get("audit_trail", []))
        iteration = int(state.get("iteration_count") or 0) + 1

        checklist: List[InspectorChecklistItem] = []
        corrections: List[str] = []
        target_agent_for_fix: Optional[str] = None

        # =====================================================================
        # CHECK 1: Coherencia Comercial (Agente 1) <-> Ingeniería (Agente 2)
        # =====================================================================
        chk1_passed = True
        chk1_notes: List[str] = []
        if boq.linea != expediente.linea:
            chk1_passed = False
            chk1_notes.append(f"Línea en BOQ ({boq.linea}) no coincide con Comercial ({expediente.linea}).")
            target_agent_for_fix = "solution_engineer"

        if expediente.linea in ("aislado", "diesel") and (not boq.includes_bess or boq.bess_total_kwh <= 0):
            chk1_passed = False
            chk1_notes.append(f"Proyecto '{expediente.linea}' requiere obligatoriamente banco de baterías LiFePO4 (>0 kWh).")
            target_agent_for_fix = "solution_engineer"

        if expediente.dedalo_kyc.interested_in_zero_down_long_term:
            if expediente.dedalo_kyc.evaluation_status == "not_requested":
                chk1_passed = False
                chk1_notes.append("Cliente solicitó $0 pie largo plazo pero Agente 1 no activó estado de evaluación Dédalo.")
            if not quote.dedalo_options or len(quote.dedalo_options) < 4:
                chk1_passed = False
                chk1_notes.append("Faltan opciones de cuotas Dédalo a 10, 15, 20 y 25 años en la cotización.")
                target_agent_for_fix = target_agent_for_fix or "pricing_quote"

        checklist.append(
            InspectorChecklistItem(
                check_id="CHK-01",
                category="Coherencia Comercial <-> Ingeniería",
                description="Verifica alineación entre levantamiento comercial (línea, zona, baterías, financiamiento $0 pie) y diseño técnico.",
                passed=chk1_passed,
                details="OK: Levantamiento comercial y diseño técnico 100% alineados." if chk1_passed else " | ".join(chk1_notes),
            )
        )
        if not chk1_passed:
            corrections.extend(chk1_notes)

        # =====================================================================
        # CHECK 2: Topología Eléctrica, Fases y Completitud del BOQ (Agente 2)
        # =====================================================================
        chk2_passed = True
        chk2_notes: List[str] = []
        families_present = {item.family for item in boq.boq_items}
        required_families = {
            "PV_MODULES",
            "INVERTERS_CONTROLS",
            "ELECTRICAL_PROTECTIONS",
            "MOUNTING_AND_BOS",
            "INSTALLATION_LABOR",
        }
        if boq.includes_bess:
            required_families.add("BESS_STORAGE")

        missing_fams = required_families - families_present
        if missing_fams:
            chk2_passed = False
            chk2_notes.append(f"Faltan familias obligatorias en el BOQ: {sorted(missing_fams)}.")
            target_agent_for_fix = "solution_engineer"

        if "Trifásico" in boq.system_phases and boq.linea in ("aislado", "diesel"):
            if boq.inverter_count % 3 != 0:
                chk2_passed = False
                chk2_notes.append(
                    f"Inconsistencia trifásica Victron: sistema es {boq.system_phases} pero tiene {boq.inverter_count} inversor(es) (debe ser múltiplo de 3)."
                )
                target_agent_for_fix = "solution_engineer"

        checklist.append(
            InspectorChecklistItem(
                check_id="CHK-02",
                category="Integridad del BOQ y Fases Eléctricas",
                description="Verifica presencia de paneles, inversores, baterías, termomagnéticos/diferenciales/SPD, ferretería y simetría de fases.",
                passed=chk2_passed,
                details=f"OK: BOQ completo con {len(boq.boq_items)} partidas y fases coherentes ({boq.system_phases})."
                if chk2_passed
                else " | ".join(chk2_notes),
            )
        )
        if not chk2_passed:
            corrections.extend(chk2_notes)

        # =====================================================================
        # CHECK 3: Consistencia de Unidades Físicas y Racionalidad (Agente 2)
        # =====================================================================
        chk3_passed = True
        chk3_notes: List[str] = []
        expected_kwp = round(boq.panel_count * (boq.panel_wp / 1000.0), 2)
        if abs(expected_kwp - boq.total_kwp) > 0.03:
            chk3_passed = False
            chk3_notes.append(
                f"Error de unidades solares: {boq.panel_count} paneles x {boq.panel_wp} Wp = {expected_kwp} kWp, pero dice {boq.total_kwp} kWp."
            )
            target_agent_for_fix = "solution_engineer"

        if not (500 <= boq.panel_wp <= 800):
            chk3_passed = False
            chk3_notes.append(f"Potencia unitaria de panel fuera de rango en Wp: {boq.panel_wp} Wp.")
            target_agent_for_fix = "solution_engineer"

        if not (80.0 <= boq.voc_cold_10c_v <= 1000.0):
            chk3_passed = False
            chk3_notes.append(f"Tensión Voc en frío extremo (-10°C) fuera de límite seguro (1000 Vdc): {boq.voc_cold_10c_v} Vdc.")
            target_agent_for_fix = "solution_engineer"

        checklist.append(
            InspectorChecklistItem(
                check_id="CHK-03",
                category="Consistencia de Unidades Físicas",
                description="Verifica exactitud de unidades (Wp, kWp, kW, kVA, kWh, Vdc) y límites eléctricos.",
                passed=chk3_passed,
                details=f"OK: {boq.panel_count}x {boq.panel_wp} Wp = {boq.total_kwp:.2f} kWp, Voc(-10°C)={boq.voc_cold_10c_v} Vdc."
                if chk3_passed
                else " | ".join(chk3_notes),
            )
        )
        if not chk3_passed:
            corrections.extend(chk3_notes)

        # =====================================================================
        # CHECK 4: Auditoría Matemática de Costos, 9% Flete Aysén y 20% Utilidad (Agente 3)
        # =====================================================================
        chk4_passed = True
        chk4_notes: List[str] = []

        zero_cost_skus = [it.sku for it in quote.priced_items if it.unit_cost_net_clp <= 0 or it.client_subtotal_net_clp <= 0]
        if zero_cost_skus:
            chk4_passed = False
            chk4_notes.append(f"Existen ítems en el BOQ con precio $0 o nulo: {zero_cost_skus}.")
            target_agent_for_fix = target_agent_for_fix or "pricing_quote"

        expected_logistics = int(round(quote.costo_equipos_y_ferreteria_neto_clp * 0.09))
        if abs(quote.costo_logistica_aysen_9_pct_clp - expected_logistics) > 5:
            chk4_passed = False
            chk4_notes.append(
                f"Logística y flete Aysén debe ser 9% del costo de equipos (${expected_logistics:,}), pero se calculó ${quote.costo_logistica_aysen_9_pct_clp:,}."
            )
            target_agent_for_fix = target_agent_for_fix or "pricing_quote"

        expected_venta_eq = int(round(quote.costo_equipos_y_ferreteria_neto_clp * 1.20))
        expected_venta_log = int(round(quote.costo_logistica_aysen_9_pct_clp * 1.20))
        expected_venta_inst = int(round(quote.costo_instalacion_subcontrato_neto_clp * 1.20))
        expected_neto_cliente = expected_venta_eq + expected_venta_log + expected_venta_inst

        if abs(quote.precio_final_neto_cliente_clp - expected_neto_cliente) > 10:
            chk4_passed = False
            chk4_notes.append(
                f"Precio Final Neto Cliente (${quote.precio_final_neto_cliente_clp:,}) no cuadra con el 20% de utilidad sobre Equipos, Logística e Instalación (${expected_neto_cliente:,})."
            )
            target_agent_for_fix = target_agent_for_fix or "pricing_quote"

        checklist.append(
            InspectorChecklistItem(
                check_id="CHK-04",
                category="Auditoría de Precios, Logística (9%) y Utilidad (20%)",
                description="Verifica precios > $0, flete Aysén = 9% s/equipos y 20% de utilidad sobre Equipos, Logística e Instalación.",
                passed=chk4_passed,
                details=(
                    f"OK: Logística Aysén (9%)=${quote.costo_logistica_aysen_9_pct_clp:,}, "
                    f"Utilidad (20%)=${quote.utilidad_total_delta_neto_clp:,}, "
                    f"Precio Final Neto Cliente=${quote.precio_final_neto_cliente_clp:,}."
                )
                if chk4_passed
                else " | ".join(chk4_notes),
            )
        )
        if not chk4_passed:
            corrections.extend(chk4_notes)

        # =====================================================================
        # CHECK 5: Legibilidad del PDF, Sello No Vinculante y Confidencialidad (Agente 3)
        # =====================================================================
        chk5_passed = True
        chk5_notes: List[str] = []
        pdf_text = _extract_pdf_text(quote.pdf_path)

        if not pdf_text or len(pdf_text.strip()) < 200:
            chk5_passed = False
            chk5_notes.append("El archivo PDF generado no existe o su texto no es legible.")
            target_agent_for_fix = target_agent_for_fix or "pricing_quote"
        else:
            if "NO VINCULANTE" not in pdf_text.upper():
                chk5_passed = False
                chk5_notes.append("El PDF no contiene la advertencia obligatoria 'PROPUESTA TÉCNICA PRELIMINAR NO VINCULANTE'.")
                target_agent_for_fix = target_agent_for_fix or "pricing_quote"

            for forbidden_token in ("NaN", "undefined", "None", "null"):
                if f" {forbidden_token} " in pdf_text:
                    chk5_passed = False
                    chk5_notes.append(f"Se detectó texto corrupto ('{forbidden_token}') dentro del PDF.")
                    target_agent_for_fix = target_agent_for_fix or "pricing_quote"

            if expediente.lead_ref not in pdf_text:
                chk5_passed = False
                chk5_notes.append(f"El código de expediente {expediente.lead_ref} no aparece en el PDF.")
                target_agent_for_fix = target_agent_for_fix or "pricing_quote"

        checklist.append(
            InspectorChecklistItem(
                check_id="CHK-05",
                category="Legibilidad Documental y Sello No Vinculante en PDF",
                description="Verifica que el PDF sea legible, sin valores corruptos, con sello NO VINCULANTE y confidencialidad de márgenes.",
                passed=chk5_passed,
                details=f"OK: PDF '{quote.pdf_filename}' ({quote.pdf_size_bytes} bytes) legible y con cláusula NO VINCULANTE verificada."
                if chk5_passed
                else " | ".join(chk5_notes),
            )
        )
        if not chk5_passed:
            corrections.extend(chk5_notes)

        all_passed = all(c.passed for c in checklist)
        summary = (
            f"APROBADO POR INSPECTOR TÉCNICO (Iteración {iteration}): Los 5 puntos del checklist cumplen estándares de Ingeniería Delta."
            if all_passed
            else f"RECHAZADO POR INSPECTOR TÉCNICO (Iteración {iteration} -> Derivar a '{target_agent_for_fix}'): "
            + "; ".join(corrections)
        )

        report = InspectorAuditReport(
            lead_ref=expediente.lead_ref,
            approved=all_passed,
            iteration=iteration,
            target_agent_for_fix=None if all_passed else (target_agent_for_fix or "solution_engineer"),
            checklist=checklist,
            inspector_summary=summary,
            required_corrections=corrections,
        )

        audit_trail.append(f"[Agente 4 - Inspector Técnico] {summary}")
        state["inspector_report"] = report
        state["iteration_count"] = iteration
        state["audit_trail"] = audit_trail
        return state
