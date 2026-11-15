"""
Estado compartido (Single Source of Truth) para la Arquitectura de 4 Agentes de Ingeniería Delta Aysén.
Utilizado por LangGraph (StateGraph) y la capa de persistencia CRM / SQLite.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict
from pydantic import BaseModel, Field


class DedaloEvaluationInfo(BaseModel):
    """
    Puerta de entrada condicional al financiamiento de largo plazo Alza Dédalo / Sunplug.
    Se activa SÍ Y SOLO SÍ el cliente manifiesta interés en $0 pie y cuotas a 10, 15, 20 o 25 años.
    """
    interested_in_zero_down_long_term: bool = Field(
        default=False,
        description="True sí y solo sí el cliente tiene interés en financiamiento $0 pie a 10, 15, 20 o 25 años."
    )
    preferred_term_years: int = Field(
        default=25,
        description="Plazo preferido de simulación en años: 10, 15, 20 o 25."
    )
    rut_titular: Optional[str] = Field(
        default=None,
        description="RUT del propietario/titular para pre-evaluación comercial en Alza Dédalo / Sunplug."
    )
    is_property_owner_cbr: Optional[bool] = Field(
        default=None,
        description="Confirma si es propietario con dominio vigente en el Conservador de Bienes Raíces (CBR)."
    )
    property_address: Optional[str] = Field(
        default=None,
        description="Dirección exacta o rol del inmueble en la Región de Aysén / Los Lagos."
    )
    distributor_company: Optional[str] = Field(
        default="Edelaysen",
        description="Empresa distribuidora eléctrica (Edelaysen, Saesa, etc.)."
    )
    evaluation_status: str = Field(
        default="not_requested",
        description="not_requested | pending_kyc_data | ready_for_sunplug_evaluation | pre_qualified"
    )
    missing_fields_for_dedalo: List[str] = Field(
        default_factory=list,
        description="Campos adicionales que el Agente Comercial debe solicitar si hay interés en $0 pie."
    )


class LeadExpediente(BaseModel):
    """
    Expediente integral levantado y mantenido por el Agente 1 (Agente Comercial).
    Sirve para el CRM, Embudo de Ventas y como entrada técnica para el Agente 2.
    """
    lead_ref: str = Field(..., description="Código único de expediente, ej. #DLT-8F3A2")
    nombre: str = Field(default="Cliente Por Confirmar")
    empresa: str = Field(default="Particular / Hogar")
    correo: str = Field(default="")
    telefono: str = Field(default="")
    ubicacion: str = Field(default="Coyhaique")
    zona_climatica: str = Field(default="coyhaique", description="aysen | coyhaique | chilechico | loslagos")
    linea: str = Field(default="red", description="red | aislado | diesel")
    perfil_cliente: str = Field(default="residencial", description="residencial | pyme | industrial")
    etapa_embudo: str = Field(
        default="1. Lead Ingresado",
        description="Etapa actual del embudo comercial CRM."
    )
    origen: str = Field(default="web_cotizador")

    # Datos técnicos levantados por el Agente Comercial o extraídos de adjuntos (Boleta / Generador)
    consumo_mensual_clp: int = Field(default=135000, description="Gasto mensual eléctrico o en diésel en CLP")
    consumo_mensual_kwh: float = Field(default=627.9, description="Consumo mensual estimado o leído en kWh/mes")
    potencia_generador_kva: Optional[float] = Field(default=None, description="Potencia del generador en kVA si es línea diesel")
    fase_sistema: str = Field(default="Monofásico 220V", description="Monofásico 220V | Trifásico 380V")
    horas_uso_generador_dia: Optional[float] = Field(default=None)
    tipo_cubierta: str = Field(default="Techo Zinc Acanalado / Cubierta Austral")
    incluye_baterias: bool = Field(default=False)
    capacidad_bateria_solicitada_kwh: float = Field(default=0.0)
    climatizacion_addon: str = Field(default="none", description="none | split | aerotermia")
    artefactos_criticos: List[str] = Field(default_factory=list)
    comentarios_cliente: str = Field(default="")
    datos_extraidos_adjunto: Dict[str, Any] = Field(default_factory=dict)

    # Puerta de entrada condicional a Financiamiento Largo Plazo
    financing_mode: str = Field(
        default="contado",
        description="contado | dedalo_pie_cero | subsidio_publico"
    )
    dedalo_kyc: DedaloEvaluationInfo = Field(default_factory=DedaloEvaluationInfo)

    # Control de calidad comercial
    is_ready_for_engineering: bool = Field(default=True)
    missing_technical_questions: List[str] = Field(default_factory=list)


class BOQItem(BaseModel):
    """Ítem técnico individual dentro del Listado de Materiales (BOQ) emitido por el Agente 2."""
    sku: str
    family: str = Field(
        ...,
        description="PV_MODULES | INVERTERS_CONTROLS | BESS_STORAGE | ELECTRICAL_PROTECTIONS | MOUNTING_AND_BOS | INSTALLATION_LABOR"
    )
    category: str = Field(
        ...,
        description="EQUIPAMIENTO | FERRETERIA_Y_PROTECCIONES | INSTALACION_SUBCONTRATO"
    )
    description: str
    unit: str
    quantity: int
    technical_justification: str


class EngineeringProposalBOQ(BaseModel):
    """
    Propuesta de Pre-Ingeniería Conceptual y BOQ completo generada por el Agente 2 (Solution Engineer).
    """
    lead_ref: str
    system_title: str
    linea: str
    zona_climatica: str
    zone_label: str
    system_phases: str = Field(..., description="Monofásico 220V | Trifásico 380V")
    architecture_summary: str

    # Dimensionamiento Solar
    panel_sku: str
    panel_model: str
    panel_wp: int = Field(..., description="Potencia unitaria del módulo en Wp (ej. 610 o 715)")
    panel_count: int = Field(..., description="Cantidad total de paneles solares")
    total_kwp: float = Field(..., description="Potencia fotovoltaica total instalada en kWp")
    strings_config: str = Field(..., description="Distribución eléctrica de strings en serie/paralelo")
    voc_cold_10c_v: float = Field(..., description="Tensión en vacío por string corregida a -10°C en Vdc")
    recommended_tilt: str

    # Inversores y Reguladores
    inverter_sku: str
    inverter_model: str
    inverter_count: int
    inverter_total_kw: float
    inverter_total_kva: float
    dc_ac_ratio: float
    mppt_sku: Optional[str] = None
    mppt_model: Optional[str] = None
    mppt_count: int = 0
    gx_control_model: Optional[str] = None

    # Baterías LiFePO4
    includes_bess: bool = False
    bess_sku: Optional[str] = None
    bess_model: str = "Sin banco de baterías (On-Grid directo)"
    bess_module_count: int = 0
    bess_total_kwh: float = 0.0

    # Estimaciones Energéticas y Ambientales
    annual_generation_kwh: int
    monthly_generation_avg_kwh: int
    coverage_pct: float
    co2_tons_avoided_year: float
    trees_equivalent: int
    electrical_protection_summary: str
    technical_notes_aysen: List[str] = Field(default_factory=list)

    # Listado Completo de Materiales y Partidas (BOQ)
    boq_items: List[BOQItem] = Field(default_factory=list)


class PricedBOQItem(BaseModel):
    """Ítem del BOQ valorizado con la Base de Datos de Precios de Proveedores Delta (Agente 3)."""
    sku: str
    family: str
    category: str
    description: str
    supplier: str
    unit: str
    quantity: int
    unit_cost_net_clp: int
    subtotal_cost_net_clp: int
    client_unit_price_net_clp: int
    client_subtotal_net_clp: int


class DedaloTermOption(BaseModel):
    """Escenario de financiamiento de largo plazo Alza Dédalo ($0 pie, 4 meses de gracia)."""
    term_years: int
    months: int
    down_payment_clp: int = 0
    grace_months: int = 4
    total_financed_uf: float
    monthly_fee_uf: float
    monthly_fee_clp: int
    bill_before_clp: int
    bill_after_clp: int
    new_total_monthly_outflow_clp: int
    net_monthly_pocket_savings_clp: int
    net_savings_pct: float
    is_cashflow_positive_day1: bool


class PricingQuoteResult(BaseModel):
    """
    Resultado económico, cálculo de logística Aysén (9%), utilidad Delta (20%) y PDF final
    emitido por el Agente 3 (PricingAndQuoteAgent).
    """
    lead_ref: str
    currency: str = "CLP"
    uf_value_clp: float = 41199.0
    logistics_rate: float = 0.09
    utility_margin_rate: float = 0.20
    iva_rate: float = 0.19

    # 1. Costos Netos Internos de Proveedores y Subcontrato (Confidenciales para CRM interno)
    costo_equipos_y_ferreteria_neto_clp: int
    costo_logistica_aysen_9_pct_clp: int
    costo_instalacion_subcontrato_neto_clp: int
    costo_total_interno_neto_clp: int

    # 2. Utilidad del 20% por Partida
    utilidad_equipos_20_clp: int
    utilidad_logistica_20_clp: int
    utilidad_instalacion_20_clp: int
    utilidad_total_delta_neto_clp: int

    # 3. Precios de Venta Netos para el Cliente por Partida
    venta_equipos_neto_clp: int
    venta_logistica_neto_clp: int
    venta_instalacion_neto_clp: int

    # 4. Totales Finales Cliente
    precio_final_neto_cliente_clp: int
    iva_19_pct_clp: int
    precio_final_bruto_cliente_clp: int
    precio_final_uf: float

    # 5. Retorno y Simulación de Financiamiento Dédalo $0 Pie
    monthly_bill_before_clp: int
    monthly_bill_after_clp: int
    monthly_solar_savings_clp: int
    annual_solar_savings_clp: int
    simple_payback_years: float
    dedalo_options: Dict[str, DedaloTermOption] = Field(default_factory=dict)

    # 6. Detalle de Ítems y Documento PDF generado
    priced_items: List[PricedBOQItem] = Field(default_factory=list)
    pdf_filename: str = ""
    pdf_path: str = ""
    pdf_size_bytes: int = 0
    pdf_base64: Optional[str] = None
    client_facing_summary_text: str = ""


class InspectorChecklistItem(BaseModel):
    """Punto individual del Checklist de Auditoría del Agente 4 (Inspector Técnico)."""
    check_id: str
    category: str
    description: str
    passed: bool
    details: str


class InspectorAuditReport(BaseModel):
    """
    Veredicto del Agente 4 (Inspector Técnico QA) tras auditar el trabajo de los Agentes 1, 2 y 3.
    """
    lead_ref: str
    approved: bool
    iteration: int
    target_agent_for_fix: Optional[str] = Field(
        default=None,
        description="None si está aprobado; 'solution_engineer' o 'pricing_quote' si requiere corrección."
    )
    checklist: List[InspectorChecklistItem] = Field(default_factory=list)
    inspector_summary: str
    required_corrections: List[str] = Field(default_factory=list)


class DeltaAgentGraphState(TypedDict, total=False):
    """Estado tipado del Grafo Multi-Agente LangGraph (Agentes 1 -> 2 -> 3 -> 4 -> 1)."""
    raw_input: Dict[str, Any]
    expediente: LeadExpediente
    engineering_boq: EngineeringProposalBOQ
    pricing_quote: PricingQuoteResult
    inspector_report: InspectorAuditReport
    commercial_presentation_message: str
    available_calendar_slots: List[Dict[str, str]]
    iteration_count: int
    max_iterations: int
    audit_trail: List[str]
    force_fault_injection: Optional[str]
