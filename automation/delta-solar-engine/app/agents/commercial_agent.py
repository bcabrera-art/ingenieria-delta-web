"""
AGENTE 1: Agente Comercial & Calificación Financiera (CommercialAgent)
Responsabilidades:
1. Hablar con el cliente y levantar toda la información técnica y comercial posible para la propuesta.
2. Almacenar y estructurar el Expediente Único del Cliente (para CRM, Embudo y Agentes 2, 3 y 4).
3. Ser la puerta de entrada condicional a la opción de financiamiento de largo plazo Alza Dédalo / Sunplug,
   solicitando mayor información SÍ Y SOLO SÍ hay interés en $0 pie y cuotas a 10, 15, 20 o 25 años.
4. Recibir la cotización en PDF validada por el Agente 4 (Inspector Técnico) y volver con el cliente
   para presentarla e invitarlo a agendar la reunión o visita técnica de 30 minutos en Google Calendar.
"""
from __future__ import annotations

import re
import uuid
from typing import Any, Dict, List, Optional

from app.attachment_analyzer import analyze_attachment
from app.state import (
    DedaloEvaluationInfo,
    DeltaAgentGraphState,
    EngineeringProposalBOQ,
    InspectorAuditReport,
    LeadExpediente,
    PricingQuoteResult,
)

ZONE_TARIFFS_CLP = {
    "aysen": 215,
    "coyhaique": 215,
    "chilechico": 215,
    "loslagos": 198,
}


def normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    if not digits:
        return ""
    if digits.startswith("569") and len(digits) == 11:
        return "+" + digits
    if digits.startswith("9") and len(digits) == 9:
        return "+56" + digits
    if len(digits) == 8:
        return "+569" + digits
    return "+" + digits


def infer_climatic_zone(ubicacion: str) -> str:
    text = (ubicacion or "").lower()
    if any(k in text for k in ["chile chico", "general carrera", "guadal", "cochrane", "ibañez", "ibáñez"]):
        return "chilechico"
    if any(k in text for k in ["aysen", "aysén", "chacabuco", "cisnes", "puyuhuapi", "melinka", "litoral", "mañihuales"]):
        return "aysen"
    if any(k in text for k in ["osorno", "valdivia", "puerto montt", "los lagos", "los rios", "los ríos", "chiloé", "llanquihue"]):
        return "loslagos"
    return "coyhaique"


def parse_clp_amount(raw: Any, default_clp: int = 135000) -> int:
    if isinstance(raw, (int, float)) and raw > 0:
        return int(raw)
    text = str(raw or "")
    # Casos de rangos del formulario web
    text_lower = text.lower()
    if "menos de $70" in text_lower or "menos de 70" in text_lower:
        return 65000
    if "70.000" in text_lower and "150.000" in text_lower:
        return 135000
    if "150.000" in text_lower and "350.000" in text_lower:
        return 240000
    if "más de $350" in text_lower or "mas de $350" in text_lower or "industrial" in text_lower:
        return 480000

    # Buscar montos explícitos en CLP (ej. $137.500 o 135000)
    matches = re.findall(r"\$?\s*(\d{1,3}(?:\.\d{3})+|\d{5,8})", text)
    for m in matches:
        val = int(m.replace(".", ""))
        if 15000 <= val <= 25000000:
            return val
    return default_clp


def detect_interest_in_dedalo_zero_down(raw_input: Dict[str, Any]) -> tuple[bool, int]:
    """
    Determina SÍ Y SOLO SÍ el cliente tiene interés en financiamiento de largo plazo
    con $0 pie y cuotas a 10, 15, 20 o 25 años (Alza Dédalo / Sunplug).
    """
    explicit_flag = raw_input.get("interested_in_zero_down_long_term")
    financing_mode = str(raw_input.get("financing_mode", "")).lower()
    combined_text = " ".join(
        str(raw_input.get(k, ""))
        for k in ("simulacion", "mensaje", "comentarios_cliente", "financing_mode")
    ).lower()

    # Detectar plazo preferido (10, 15, 20 o 25 años)
    term_years = int(raw_input.get("preferred_term_years") or 25)
    term_match = re.search(r"\b(10|15|20|25)\s*a[ñn]os\b", combined_text)
    if term_match:
        term_years = int(term_match.group(1))
    if term_years not in (10, 15, 20, 25):
        term_years = 25

    if explicit_flag is True or financing_mode in ("dedalo", "dedalo_pie_cero", "alza", "pie_cero", "largo_plazo"):
        return True, term_years
    if explicit_flag is False or financing_mode in ("contado", "subsidio_publico"):
        return False, term_years

    # Si en la simulación o mensaje aparece explícitamente Alza Dédalo / $0 pie / cuotas a 10-25 años
    if "contado" in combined_text and "alza dédalo" not in combined_text and "$0 pie" not in combined_text:
        return False, term_years

    dedalo_keywords = [
        "alza dédalo",
        "alza dedalo",
        "$0 pie",
        "pie 0",
        "cero pie",
        "sin pie",
        "sunplug",
        "financiamiento",
        "10 años",
        "15 años",
        "20 años",
        "25 años",
    ]
    if any(kw in combined_text for kw in dedalo_keywords):
        return True, term_years

    return False, term_years


class CommercialAgent:
    """
    Primer Agente: Especialista Comercial de Ingeniería Delta Aysén.
    Levanta el expediente completo del cliente, gestiona la puerta de entrada al
    financiamiento de largo plazo ($0 pie a 10-25 años) y presenta la propuesta final.
    """

    def intake_and_qualify(self, state: DeltaAgentGraphState) -> DeltaAgentGraphState:
        raw = state.get("raw_input", {}) or {}
        audit_trail = list(state.get("audit_trail", []))

        lead_ref = str(raw.get("lead_ref") or f"#DLT-{uuid.uuid4().hex[:5].upper()}")
        nombre = str(raw.get("nombre") or "Cliente Por Confirmar").strip()
        empresa = str(raw.get("empresa") or raw.get("tipo") or "Particular / Hogar").strip()
        correo = str(raw.get("correo") or "").strip()
        telefono = normalize_phone(str(raw.get("telefono") or ""))
        ubicacion = str(raw.get("ubicacion") or "Coyhaique, Región de Aysén").strip()
        zona_climatica = str(raw.get("zona_climatica") or infer_climatic_zone(ubicacion))
        linea = str(raw.get("linea") or "red").strip().lower()
        if linea not in ("red", "aislado", "diesel"):
            linea = "red"

        # 1. Procesar adjuntos si existen (Boleta PDF o Foto de Generador)
        attachment_data: Dict[str, Any] = {}
        for att in raw.get("attachments", []) or []:
            if isinstance(att, dict) and att.get("content_base64"):
                extracted = analyze_attachment(
                    filename=str(att.get("filename", "adjunto")),
                    mime_type=str(att.get("mime_type", "application/octet-stream")),
                    content_base64=str(att.get("content_base64", "")),
                )
                attachment_data.update(extracted)

        # 2. Determinar consumo eléctrico (CLP y kWh/mes) y datos de generador/fases
        tariff_clp = ZONE_TARIFFS_CLP.get(zona_climatica, 215)
        consumo_clp = parse_clp_amount(
            attachment_data.get("monto_total_clp")
            or raw.get("consumo_mensual_clp")
            or raw.get("consumo")
            or raw.get("simulacion"),
            default_clp=135000 if linea == "red" else (280000 if linea == "diesel" else 110000),
        )

        if attachment_data.get("consumo_kwh_mes"):
            consumo_kwh = float(attachment_data["consumo_kwh_mes"])
        elif raw.get("consumo_mensual_kwh"):
            consumo_kwh = float(raw["consumo_mensual_kwh"])
        else:
            consumo_kwh = round(consumo_clp / float(tariff_clp), 1)

        # Potencia de generador y fases
        pot_gen_kva: Optional[float] = None
        raw_gen = attachment_data.get("potencia_kva") or raw.get("potencia_generador_kva") or raw.get("potencia_generador")
        if raw_gen:
            m_kva = re.search(r"(\d+(?:[.,]\d+)?)", str(raw_gen))
            if m_kva:
                pot_gen_kva = float(m_kva.group(1).replace(",", "."))
        elif linea == "diesel":
            pot_gen_kva = 15.0

        raw_fase = str(
            attachment_data.get("fases")
            or raw.get("fase_sistema")
            or raw.get("fase_generador")
            or ""
        ).lower()
        if "trif" in raw_fase or "380" in raw_fase or "400" in raw_fase or "3p" in raw_fase:
            fase_sistema = "Trifásico 380V"
        elif pot_gen_kva and pot_gen_kva >= 15.0 and linea == "diesel" and "monof" not in raw_fase:
            fase_sistema = "Trifásico 380V"
        else:
            fase_sistema = "Monofásico 220V"

        # Perfil del cliente
        empresa_lower = empresa.lower()
        if "industrial" in empresa_lower or (pot_gen_kva and pot_gen_kva >= 20) or consumo_clp >= 400000:
            perfil_cliente = "industrial"
        elif any(k in empresa_lower for k in ["pyme", "comercio", "turismo", "lodge", "agrícola", "agricola", "empresa"]):
            perfil_cliente = "pyme"
        else:
            perfil_cliente = "residencial"

        # Baterías de respaldo
        sim_text = str(raw.get("simulacion") or "").lower()
        incluye_baterias = bool(
            raw.get("incluye_baterias")
            or linea in ("aislado", "diesel")
            or "batería" in sim_text
            or "bateria" in sim_text
            or "lifepo4" in sim_text
            or "híbrido" in sim_text
        )

        # 3. Puerta de Entrada Condicional al Financiamiento Largo Plazo ($0 Pie 10-25 años Alza Dédalo)
        interested_dedalo, preferred_term = detect_interest_in_dedalo_zero_down(raw)
        missing_dedalo_fields: List[str] = []
        rut_titular = raw.get("rut_titular") or None
        is_owner_cbr = raw.get("is_property_owner_cbr")
        prop_address = raw.get("property_address") or (ubicacion if len(ubicacion) > 12 else None)
        distributor = str(attachment_data.get("distribuidora") or raw.get("distributor_company") or "Edelaysen")

        if interested_dedalo:
            financing_mode = "dedalo_pie_cero"
            if not rut_titular:
                missing_dedalo_fields.append("RUT del propietario/titular para pre-evaluación en Alza Dédalo (sunplug.cl)")
            if is_owner_cbr is None:
                missing_dedalo_fields.append("Confirmación de propiedad inscrita en el Conservador de Bienes Raíces (CBR)")
            if not prop_address:
                missing_dedalo_fields.append("Dirección exacta del inmueble y comuna para factibilidad de prenda")

            eval_status = "ready_for_sunplug_evaluation" if not missing_dedalo_fields else "pending_kyc_data"
        else:
            financing_mode = str(raw.get("financing_mode") or ("subsidio_publico" if perfil_cliente == "pyme" else "contado"))
            eval_status = "not_requested"

        dedalo_kyc = DedaloEvaluationInfo(
            interested_in_zero_down_long_term=interested_dedalo,
            preferred_term_years=preferred_term,
            rut_titular=rut_titular,
            is_property_owner_cbr=is_owner_cbr,
            property_address=prop_address,
            distributor_company=distributor,
            evaluation_status=eval_status,
            missing_fields_for_dedalo=missing_dedalo_fields,
        )

        # Verificar preguntas técnicas faltantes para conversación directa por WhatsApp
        missing_tech: List[str] = []
        if not raw.get("linea") and not raw.get("simulacion"):
            missing_tech.append("Definir si el proyecto es Conectado a Red (bajar boleta), Aislado (Off-Grid) o Reemplazo Diésel.")
        if not raw.get("consumo") and not raw.get("consumo_mensual_clp") and not attachment_data:
            missing_tech.append("Indicar gasto mensual aproximado en electricidad ($ CLP o boleta PDF) o potencia del generador (kVA).")

        etapa_embudo = (
            "5. Evaluación Financiamiento Dédalo"
            if interested_dedalo
            else ("2. En Calificación" if missing_tech else "3. En Ingeniería/Cotización")
        )

        expediente = LeadExpediente(
            lead_ref=lead_ref,
            nombre=nombre,
            empresa=empresa,
            correo=correo,
            telefono=telefono,
            ubicacion=ubicacion,
            zona_climatica=zona_climatica,
            linea=linea,
            perfil_cliente=perfil_cliente,
            etapa_embudo=etapa_embudo,
            origen=str(raw.get("origen") or "web_cotizador"),
            consumo_mensual_clp=consumo_clp,
            consumo_mensual_kwh=consumo_kwh,
            potencia_generador_kva=pot_gen_kva,
            fase_sistema=fase_sistema,
            horas_uso_generador_dia=float(raw.get("horas_uso_generador_dia") or (8.0 if linea == "diesel" else 0.0)),
            tipo_cubierta=str(raw.get("tipo_cubierta") or "Techo Zinc Acanalado / Cubierta Austral"),
            incluye_baterias=incluye_baterias,
            capacidad_bateria_solicitada_kwh=float(raw.get("capacidad_bateria_solicitada_kwh") or 0.0),
            climatizacion_addon=str(raw.get("climatizacion_addon") or "none"),
            artefactos_criticos=list(raw.get("artefactos_criticos") or []),
            comentarios_cliente=str(raw.get("mensaje") or raw.get("comentarios_cliente") or ""),
            datos_extraidos_adjunto=attachment_data,
            financing_mode=financing_mode,
            dedalo_kyc=dedalo_kyc,
            is_ready_for_engineering=len(missing_tech) == 0,
            missing_technical_questions=missing_tech,
        )

        audit_trail.append(
            f"[Agente 1 - Comercial] Expediente {lead_ref} estructurado para '{nombre}' ({ubicacion}, línea={linea}, "
            f"fases={fase_sistema}, consumo={consumo_kwh:.1f} kWh/mes, interés_Dédalo_pie_0={interested_dedalo})."
        )

        state["expediente"] = expediente
        state["audit_trail"] = audit_trail
        return state

    def present_validated_proposal(self, state: DeltaAgentGraphState) -> DeltaAgentGraphState:
        """
        Una vez que el Agente 3 generó la cotización + PDF y el Agente 4 (Inspector Técnico)
        aprobó el Checklist QA, el Agente 1 toma la cotización y vuelve con el cliente.
        """
        expediente: LeadExpediente = state["expediente"]
        boq: EngineeringProposalBOQ = state["engineering_boq"]
        quote: PricingQuoteResult = state["pricing_quote"]
        inspector: InspectorAuditReport = state["inspector_report"]
        slots = state.get("available_calendar_slots") or []
        audit_trail = list(state.get("audit_trail", []))

        def fmt_clp(val: int) -> str:
            return "$" + f"{int(round(val)):,}".replace(",", ".")

        lines = [
            f"¡Hola {expediente.nombre}! Te saluda el equipo de *Ingeniería Delta Aysén* ⚡.",
            f"Hemos preparado tu *Propuesta Técnica Preliminar No Vinculante* (Expediente `{expediente.lead_ref}`) para *{expediente.ubicacion}*:",
            "",
            "🔧 *1. Resumen de Pre-Ingeniería y Equipamiento (BOQ)*:",
            f"• *Arquitectura*: {boq.system_title} ({boq.system_phases})",
            f"• *Campo Solar*: {boq.panel_count}x {boq.panel_model} ({boq.total_kwp:.2f} kWp instalados)",
            f"• *Conversión de Potencia*: {boq.inverter_count}x {boq.inverter_model}",
        ]
        if boq.mppt_model and boq.mppt_count > 0:
            lines.append(f"• *Regulación Solar MPPT*: {boq.mppt_count}x {boq.mppt_model}")
        if boq.includes_bess and boq.bess_total_kwh > 0:
            lines.append(f"• *Almacenamiento Litio LiFePO4*: {boq.bess_module_count}x {boq.bess_model} ({boq.bess_total_kwh:.1f} kWh totales)")
        lines.extend([
            f"• *Protecciones y Ferretería SEC*: Incluye tableros AC/DC IP65, interruptores termomagnéticos, diferenciales, descargadores SPD, estructura de aluminio patagónica, puesta a tierra, logística a Aysén e instalación completa.",
            f"• *Generación Anual Estimada*: ~{boq.annual_generation_kwh:,}".replace(",", ".") + " kWh/año",
            "",
            "💰 *2. Valorización del Proyecto Llave en Mano*:",
            f"• *Precio Final Neto Cliente*: *{fmt_clp(quote.precio_final_neto_cliente_clp)} + IVA*",
            f"• *Total Proyecto (IVA incluido)*: {fmt_clp(quote.precio_final_bruto_cliente_clp)} ({quote.precio_final_uf:.1f} UF)",
        ])

        # Si el cliente mostró interés en Financiamiento de Largo Plazo ($0 pie, 10-25 años)
        if expediente.dedalo_kyc.interested_in_zero_down_long_term and quote.dedalo_options:
            pref_key = str(expediente.dedalo_kyc.preferred_term_years)
            opt = quote.dedalo_options.get(pref_key) or quote.dedalo_options.get("25")
            if opt:
                lines.extend([
                    "",
                    f"🏦 *3. Opción Financiamiento Largo Plazo Alza Dédalo ($0 Pie · {opt.term_years} años · 1ª cuota en 4 meses)*:",
                    f"• *Pie Inicial*: $0 CLP (100% financiado)",
                    f"• *Cuota Mensual Estimada ({opt.term_years} años)*: {fmt_clp(opt.monthly_fee_clp)}/mes ({opt.monthly_fee_uf:.2f} UF)",
                    f"• *Ahorro Solar Mensual Estimado*: {fmt_clp(quote.monthly_solar_savings_clp)}/mes",
                ])
            if expediente.dedalo_kyc.missing_fields_for_dedalo:
                lines.append(
                    "📌 *Para pre-evaluar tu crédito $0 pie en plataforma Sunplug/Alza Dédalo (sin costo legal de bolsillo)*, "
                    "solo necesitamos que nos confirmes por aquí: "
                    + "; ".join(expediente.dedalo_kyc.missing_fields_for_dedalo)
                    + "."
                )

        # Invitación a agendar Reunión Técnica de 30 min o Visita en Terreno en bcabrera@ingenieriadelta.cl
        lines.extend([
            "",
            "📎 *Te adjuntamos en este mensaje el PDF oficial con el desglose completo de materiales (BOQ) y condiciones.*",
            "",
            "📅 *¿Agendamos una Reunión Técnica de 30 minutos o Visita en Terreno con Benjamín Cabrera?*",
        ])
        if slots:
            slot_labels = [s.get("label", s.get("start_iso", "")) for s in slots[:3]]
            lines.append("Tengo disponibles estos bloques en el calendario de `bcabrera@ingenieriadelta.cl`:")
            for idx, sl in enumerate(slot_labels, start=1):
                lines.append(f"  {idx}) {sl}")
            lines.append("Coméntame cuál te acomoda más (y tu correo si quieres sumar a alguien más) y te dejo agendado de inmediato.")
        else:
            lines.append(
                "Atendemos de Lunes a Viernes entre 09:30 y 18:00 hrs. ¿Qué día y bloque (mañana o tarde) te acomoda más para reservar tu espacio en `bcabrera@ingenieriadelta.cl`?"
            )

        expediente.etapa_embudo = "4. Propuesta Entregada"
        message = "\n".join(lines)
        state["commercial_presentation_message"] = message
        audit_trail.append(
            f"[Agente 1 - Comercial] Propuesta {expediente.lead_ref} (QA={inspector.approved}) lista para enviar al cliente con PDF '{quote.pdf_filename}'."
        )
        state["audit_trail"] = audit_trail
        return state
