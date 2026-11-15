"""
AGENTE 3: Agente Cotizador, Costos de Proveedores, Logística Aysén (9%), Utilidad (20%) y PDF (PricingAndQuoteAgent)
Responsabilidades:
1. Tomar el BOQ completo emitido por el Agente 2 (Solution Engineer).
2. Salir a cotizar a la Base de Datos de Lista de Precios de Proveedores de Delta (delta_price_catalog.json).
3. Calcular:
   - Costo Neto de Equipos y Ferretería Eléctrica
   - Logística y Flete a la Región de Aysén y Obra = 9% sobre el costo de los equipos
   - Instalación (Subcontrato de Mano de Obra)
   - Aplicar un 20% de utilidad sobre los Equipos, sobre la Logística y Transporte, y sobre la Instalación
   - Obtener el Precio Final Neto para el Cliente (+ IVA 19%)
4. Calcular escenarios de financiamiento de largo plazo Alza Dédalo ($0 pie a 10, 15, 20 y 25 años).
5. Generar la propuesta final de cotización en formato PDF lista para ser auditada por el Agente 4.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from app.pdf_generator import generate_proposal_pdf
from app.state import (
    DedaloTermOption,
    DeltaAgentGraphState,
    EngineeringProposalBOQ,
    LeadExpediente,
    PricedBOQItem,
    PricingQuoteResult,
)

UF_VALUE_CLP = 41199.0
DEDALO_MONTHLY_RATE = 0.00524596  # (1 + 0.0648)**(1/12) - 1
DEDALO_UF_FACTORS = {
    10: {"months": 120, "uf_factor": 1.130994},
    15: {"months": 180, "uf_factor": 1.183189},
    20: {"months": 240, "uf_factor": 1.236830},
    25: {"months": 300, "uf_factor": 1.269626},
}


def load_delta_price_catalog(catalog_path: str | None = None) -> Dict[str, Any]:
    path = (
        Path(catalog_path)
        if catalog_path
        else Path(__file__).resolve().parent.parent.parent / "data" / "delta_price_catalog.json"
    )
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _compute_dedalo_monthly_uf(principal_uf: float, monthly_rate: float, months: int) -> float:
    if months <= 0 or principal_uf <= 0:
        return 0.0
    factor = (monthly_rate * ((1.0 + monthly_rate) ** months)) / (((1.0 + monthly_rate) ** months) - 1.0)
    return principal_uf * factor


class PricingAndQuoteAgent:
    """
    Tercer Agente: Especialista en Costos de Proveedores Delta, Logística Aysén (9%),
    Utilidad (20%) y Emisión de Propuesta en PDF.
    """

    def __init__(self, catalog_path: str | None = None) -> None:
        self.catalog_data = load_delta_price_catalog(catalog_path)
        self.items_db: Dict[str, Dict[str, Any]] = self.catalog_data.get("items", {})
        meta = self.catalog_data.get("metadata", {})
        self.logistics_rate = float(meta.get("logistics_aysen_rate_on_equipment", 0.09))
        self.utility_rate = float(meta.get("utility_margin_rate", 0.20))
        self.iva_rate = float(meta.get("iva_rate", 0.19))

    def quote_boq_and_generate_pdf(self, state: DeltaAgentGraphState) -> DeltaAgentGraphState:
        expediente: LeadExpediente = state["expediente"]
        boq: EngineeringProposalBOQ = state["engineering_boq"]
        audit_trail = list(state.get("audit_trail", []))
        iteration = int(state.get("iteration_count") or 0)
        fault_mode = state.get("force_fault_injection")

        # Si venimos de una corrección del Agente 4 (Inspector Técnico), limpiamos cualquier falla inyectada
        if iteration > 0 and state.get("inspector_report") and not state["inspector_report"].approved:
            fault_mode = None
            state["force_fault_injection"] = None

        priced_items: List[PricedBOQItem] = []
        costo_equipos_y_ferreteria = 0
        costo_instalacion_subcontrato = 0

        for boq_item in boq.boq_items:
            db_entry = self.items_db.get(boq_item.sku)
            if not db_entry:
                # Fallback seguro si algún SKU nuevo no estuviera en el JSON
                unit_cost = 45000
                supplier_name = "Proveedor Homologado Delta Aysén"
            else:
                unit_cost = int(
                    db_entry.get("unit_cost_net_clp")
                    or db_entry.get("costo_unitario_neto_clp")
                    or 45000
                )
                supplier_name = str(
                    db_entry.get("supplier")
                    or db_entry.get("proveedor")
                    or "Proveedor Consolidado Delta"
                )

            # Inyección de falla opcional para prueba negativa del Agente 4 (Inspector Técnico)
            if fault_mode == "zero_price_item" and boq_item.sku == boq.panel_sku:
                unit_cost = 0

            subtotal_cost = unit_cost * boq_item.quantity
            client_unit_price = int(round(unit_cost * (1.0 + self.utility_rate)))
            client_subtotal_price = int(round(subtotal_cost * (1.0 + self.utility_rate)))

            if boq_item.category in ("EQUIPAMIENTO", "FERRETERIA_Y_PROTECCIONES"):
                costo_equipos_y_ferreteria += subtotal_cost
            else:
                costo_instalacion_subcontrato += subtotal_cost

            priced_items.append(
                PricedBOQItem(
                    sku=boq_item.sku,
                    family=boq_item.family,
                    category=boq_item.category,
                    description=boq_item.description,
                    supplier=supplier_name,
                    unit=boq_item.unit,
                    quantity=boq_item.quantity,
                    unit_cost_net_clp=unit_cost,
                    subtotal_cost_net_clp=subtotal_cost,
                    client_unit_price_net_clp=client_unit_price,
                    client_subtotal_net_clp=client_subtotal_price,
                )
            )

        # 1. Cálculo de Logística y Flete a la Región de Aysén y Obra (9% sobre costo de equipos)
        if fault_mode == "wrong_logistics_rate":
            costo_logistica_aysen = int(round(costo_equipos_y_ferreteria * 0.02))  # Falla deliberada (2% en vez de 9%)
        else:
            costo_logistica_aysen = int(round(costo_equipos_y_ferreteria * self.logistics_rate))

        # 2. Aplicación del 20% de Utilidad sobre las 3 partidas (Equipos, Logística e Instalación)
        utilidad_equipos = int(round(costo_equipos_y_ferreteria * self.utility_rate))
        venta_equipos_neto = costo_equipos_y_ferreteria + utilidad_equipos

        utilidad_logistica = int(round(costo_logistica_aysen * self.utility_rate))
        venta_logistica_neto = costo_logistica_aysen + utilidad_logistica

        utilidad_instalacion = int(round(costo_instalacion_subcontrato * self.utility_rate))
        venta_instalacion_neto = costo_instalacion_subcontrato + utilidad_instalacion

        # 3. Totales consolidados
        costo_total_interno_neto = (
            costo_equipos_y_ferreteria + costo_logistica_aysen + costo_instalacion_subcontrato
        )
        utilidad_total_delta_neto = utilidad_equipos + utilidad_logistica + utilidad_instalacion
        precio_final_neto_cliente = venta_equipos_neto + venta_logistica_neto + venta_instalacion_neto
        iva_19_clp = int(round(precio_final_neto_cliente * self.iva_rate))
        precio_final_bruto_cliente = precio_final_neto_cliente + iva_19_clp
        precio_final_uf = round(precio_final_bruto_cliente / UF_VALUE_CLP, 2)

        # 4. Ahorro proyectado y Simulación Financiera Alza Dédalo ($0 pie, 10 a 25 años, 4 meses de gracia)
        bill_before = max(35000, expediente.consumo_mensual_clp)
        savings_ratio = min(0.85, max(0.70, boq.coverage_pct / 100.0))
        monthly_savings_clp = int(round(bill_before * savings_ratio))
        bill_after = max(0, bill_before - monthly_savings_clp)
        annual_savings_clp = monthly_savings_clp * 12
        simple_payback = round(precio_final_bruto_cliente / max(1.0, float(annual_savings_clp)), 1)

        dedalo_options: Dict[str, DedaloTermOption] = {}
        for term_years, cfg in DEDALO_UF_FACTORS.items():
            months = int(cfg["months"])
            uf_factor = float(cfg["uf_factor"])
            total_financed_uf = round(precio_final_uf * uf_factor, 2)
            fee_uf = round(_compute_dedalo_monthly_uf(total_financed_uf, DEDALO_MONTHLY_RATE, months), 3)
            fee_clp = int(round(fee_uf * UF_VALUE_CLP))
            new_total_outflow = bill_after + fee_clp
            net_pocket_savings = bill_before - new_total_outflow
            net_savings_pct = round((net_pocket_savings / float(bill_before)) * 100.0, 1)

            dedalo_options[str(term_years)] = DedaloTermOption(
                term_years=term_years,
                months=months,
                down_payment_clp=0,
                grace_months=4,
                total_financed_uf=total_financed_uf,
                monthly_fee_uf=fee_uf,
                monthly_fee_clp=fee_clp,
                bill_before_clp=bill_before,
                bill_after_clp=bill_after,
                new_total_monthly_outflow_clp=new_total_outflow,
                net_monthly_pocket_savings_clp=net_pocket_savings,
                net_savings_pct=net_savings_pct,
                is_cashflow_positive_day1=net_pocket_savings > 0,
            )

        quote_result = PricingQuoteResult(
            lead_ref=expediente.lead_ref,
            currency="CLP",
            uf_value_clp=UF_VALUE_CLP,
            logistics_rate=self.logistics_rate,
            utility_margin_rate=self.utility_rate,
            iva_rate=self.iva_rate,
            costo_equipos_y_ferreteria_neto_clp=costo_equipos_y_ferreteria,
            costo_logistica_aysen_9_pct_clp=costo_logistica_aysen,
            costo_instalacion_subcontrato_neto_clp=costo_instalacion_subcontrato,
            costo_total_interno_neto_clp=costo_total_interno_neto,
            utilidad_equipos_20_clp=utilidad_equipos,
            utilidad_logistica_20_clp=utilidad_logistica,
            utilidad_instalacion_20_clp=utilidad_instalacion,
            utilidad_total_delta_neto_clp=utilidad_total_delta_neto,
            venta_equipos_neto_clp=venta_equipos_neto,
            venta_logistica_neto_clp=venta_logistica_neto,
            venta_instalacion_neto_clp=venta_instalacion_neto,
            precio_final_neto_cliente_clp=precio_final_neto_cliente,
            iva_19_pct_clp=iva_19_clp,
            precio_final_bruto_cliente_clp=precio_final_bruto_cliente,
            precio_final_uf=precio_final_uf,
            monthly_bill_before_clp=bill_before,
            monthly_bill_after_clp=bill_after,
            monthly_solar_savings_clp=monthly_savings_clp,
            annual_solar_savings_clp=annual_savings_clp,
            simple_payback_years=simple_payback,
            dedalo_options=dedalo_options,
            priced_items=priced_items,
        )

        # 5. Generar el PDF de Propuesta Técnica y Económica Preliminar No Vinculante
        inject_pdf_defect = fault_mode == "missing_non_binding_disclaimer"
        pdf_filename, pdf_path, pdf_size, pdf_b64 = generate_proposal_pdf(
            expediente=expediente,
            boq=boq,
            quote=quote_result,
            inject_pdf_defect=inject_pdf_defect,
        )
        quote_result.pdf_filename = pdf_filename
        quote_result.pdf_path = pdf_path
        quote_result.pdf_size_bytes = pdf_size
        quote_result.pdf_base64 = pdf_b64

        audit_trail.append(
            f"[Agente 3 - Cotizador] Cotización calculada para {expediente.lead_ref}: "
            f"CostoEquipos=${costo_equipos_y_ferreteria:,}, LogísticaAysén(9%)=${costo_logistica_aysen:,}, "
            f"CostoInstalación=${costo_instalacion_subcontrato:,} -> Utilidad(20%)=${utilidad_total_delta_neto:,} -> "
            f"PrecioFinalNetoCliente=${precio_final_neto_cliente:,} (+IVA=${precio_final_bruto_cliente:,}). PDF='{pdf_filename}' ({pdf_size} bytes)."
        )
        state["pricing_quote"] = quote_result
        state["audit_trail"] = audit_trail
        return state
