"""
Orquestador Multi-Agente basado en LangGraph (StateGraph) para Ingeniería Delta Aysén.
Conecta los 4 Agentes Especializados con bucle automático de aseguramiento de calidad (QA):
  1. commercial_intake    (Agente 1: Agente Comercial — Levantamiento + Gate Financiamiento $0 Pie)
  2. solution_engineer    (Agente 2: Solution Engineer — Pre-Ingeniería Conceptual + BOQ + Ferretería)
  3. pricing_quote        (Agente 3: Agente Cotizador — Lista Precios Delta + 9% Flete Aysén + 20% Utilidad + PDF)
  4. technical_inspector  (Agente 4: Inspector Técnico QA — Checklist de Verificación y Racionalidad)
     |-- Si RECHAZA -> regresa a 'solution_engineer' o 'pricing_quote' para auto-corrección
     +-- Si APRUEBA -> avanza a 'commercial_present'
  5. commercial_present   (Agente 1: Agente Comercial — Presenta Cotización PDF al Cliente + Agenda en Calendar)
"""
from __future__ import annotations

from typing import Any, Dict, Literal

from langgraph.graph import END, StateGraph

from app.agents.commercial_agent import CommercialAgent
from app.agents.inspector_agent import TechnicalInspectorAgent
from app.agents.pricing_agent import PricingAndQuoteAgent
from app.agents.solution_engineer_agent import SolutionEngineerAgent
from app.calendar_service import get_available_slots
from app.state import DeltaAgentGraphState


def _route_after_inspection(
    state: DeltaAgentGraphState,
) -> Literal["solution_engineer", "pricing_quote", "commercial_present"]:
    report = state.get("inspector_report")
    iteration = int(state.get("iteration_count") or 0)
    max_iter = int(state.get("max_iterations") or 3)

    if report and report.approved:
        return "commercial_present"

    if iteration >= max_iter:
        return "commercial_present"

    if report and report.target_agent_for_fix == "pricing_quote":
        return "pricing_quote"

    return "solution_engineer"


def build_delta_multiagent_graph():
    """Construye y compila el StateGraph de LangGraph con los 4 agentes de Ingeniería Delta."""
    commercial = CommercialAgent()
    engineer = SolutionEngineerAgent()
    pricer = PricingAndQuoteAgent()
    inspector = TechnicalInspectorAgent()

    workflow = StateGraph(DeltaAgentGraphState)

    workflow.add_node("commercial_intake", commercial.intake_and_qualify)
    workflow.add_node("solution_engineer", engineer.design_system_and_boq)
    workflow.add_node("pricing_quote", pricer.quote_boq_and_generate_pdf)
    workflow.add_node("technical_inspector", inspector.inspect_and_verify)
    workflow.add_node("commercial_present", commercial.present_validated_proposal)

    workflow.set_entry_point("commercial_intake")
    workflow.add_edge("commercial_intake", "solution_engineer")
    workflow.add_edge("solution_engineer", "pricing_quote")
    workflow.add_edge("pricing_quote", "technical_inspector")

    workflow.add_conditional_edges(
        "technical_inspector",
        _route_after_inspection,
        {
            "solution_engineer": "solution_engineer",
            "pricing_quote": "pricing_quote",
            "commercial_present": "commercial_present",
        },
    )
    workflow.add_edge("commercial_present", END)

    return workflow.compile()


def run_delta_quote_pipeline(
    raw_input: Dict[str, Any],
    force_fault_injection: str | None = None,
    max_iterations: int = 3,
) -> DeltaAgentGraphState:
    """
    Ejecuta el flujo completo de los 4 agentes sobre el payload del cliente y retorna el estado final.
    """
    graph = build_delta_multiagent_graph()
    slots = get_available_slots(max_slots=3)
    initial_state: DeltaAgentGraphState = {
        "raw_input": raw_input,
        "available_calendar_slots": slots,
        "iteration_count": 0,
        "max_iterations": max_iterations,
        "audit_trail": [],
        "force_fault_injection": force_fault_injection,
    }
    final_state: DeltaAgentGraphState = graph.invoke(initial_state)
    return final_state
