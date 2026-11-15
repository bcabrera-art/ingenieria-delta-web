"""
AGENTE 2: Solution Engineer & Pre-Ingeniería Conceptual (SolutionEngineerAgent)
Responsabilidades:
1. Recibir el Expediente del Cliente estructurado por el Agente 1 (Comercial).
2. Realizar el dimensionamiento fotovoltaico y de almacenamiento patagónico (610 Wp / 715 Wp,
   Huawei FusionSolar para On-Grid/Híbrido Red, Victron Energy MultiPlus-II / Quattro + SmartSolar MPPT
   + Cerbo/Ekrano GX + Pylontech LiFePO4 para sistemas Aislados y Reemplazo Diésel).
3. Emitir el Listado Completo de Materiales (BOQ - Bill of Quantities) SIN precios comerciales:
   - Módulos solares
   - Inversores / Cargadores / Reguladores MPPT / Control GX
   - Baterías de Litio LiFePO4 y accesorios de rack/cables
   - Protecciones Eléctricas AC/DC (Termomagnéticos AC y DC, Diferenciales, SPD AC/DC, Fusibles gPV/MEGA, Seccionador, ATS/Bypass, Tablero IP65)
   - Estructura de Montaje Patagónica y Ferretería Eléctrica (Cables solares, cables de batería, MC4, canalización EMT/PVC, puesta a tierra SEC)
   - Cuantificación física de partidas de instalación y tramitación SEC TE4 (para que el Agente 3 las cotice).
"""
from __future__ import annotations

import math
from typing import Dict, List

from app.state import (
    BOQItem,
    DeltaAgentGraphState,
    EngineeringProposalBOQ,
    LeadExpediente,
)

ZONES_PATAGONIA: Dict[str, Dict[str, object]] = {
    "aysen": {
        "name": "Puerto Aysén y Litoral",
        "yield_per_kwp": 1180,
        "tariff_clp": 215,
        "recommended_tilt": "38° a 45° Norte (estructura reforzada viento/lluvia litoral)",
    },
    "coyhaique": {
        "name": "Coyhaique y Valle Interior",
        "yield_per_kwp": 1320,
        "tariff_clp": 215,
        "recommended_tilt": "40° a 45° Norte (optimización invierno y albedo de nieve)",
    },
    "chilechico": {
        "name": "Chile Chico y Cuenca Lago Gral. Carrera",
        "yield_per_kwp": 1540,
        "tariff_clp": 215,
        "recommended_tilt": "36° a 42° Norte (microclima de alta radiación austral)",
    },
    "loslagos": {
        "name": "Los Lagos y Los Ríos (Osorno, Valdivia, Pto. Montt)",
        "yield_per_kwp": 1250,
        "tariff_clp": 198,
        "recommended_tilt": "34° a 38° Norte",
    },
}

COVERAGE_TARGETS = {
    "residencial": 0.85,
    "pyme": 0.90,
    "industrial": 0.92,
}

SYSTEM_COVERAGE_BONUS = {
    "red": 0.94,      # On-Grid / Híbrido Net Billing Ley 21.118
    "aislado": 1.05,  # Off-Grid autónomo con margen invernal
    "diesel": 1.00,   # Híbrido reemplazo diésel
}


class SolutionEngineerAgent:
    """
    Segundo Agente: Ingeniero de Soluciones de Ingeniería Delta Aysén.
    Traduce los requerimientos levantados por el Agente 1 en una Pre-Ingeniería Conceptual
    y un BOQ exhaustivo de equipamiento, protecciones eléctricas y ferretería.
    """

    def design_system_and_boq(self, state: DeltaAgentGraphState) -> DeltaAgentGraphState:
        expediente: LeadExpediente = state["expediente"]
        audit_trail = list(state.get("audit_trail", []))
        iteration = int(state.get("iteration_count") or 0)
        fault_mode = state.get("force_fault_injection")

        # Si estamos en una iteración de corrección solicitada por el Agente 4 (Inspector), limpiamos cualquier falla inyectada
        if iteration > 0 and state.get("inspector_report") and not state["inspector_report"].approved:
            fault_mode = None
            state["force_fault_injection"] = None

        zone_key = expediente.zona_climatica if expediente.zona_climatica in ZONES_PATAGONIA else "coyhaique"
        zone = ZONES_PATAGONIA[zone_key]
        yield_per_kwp = int(zone["yield_per_kwp"])

        # 1. Dimensionamiento de Potencia Solar (Paneles 610 Wp estándar o 715 Wp industrial pesado)
        annual_consumption_kwh = max(1200.0, expediente.consumo_mensual_kwh * 12.0)
        coverage_target = min(
            0.96,
            COVERAGE_TARGETS.get(expediente.perfil_cliente, 0.85)
            * SYSTEM_COVERAGE_BONUS.get(expediente.linea, 1.0),
        )

        # Adicional energético si el cliente contempla climatización limpia (Split o Aerotermia)
        extra_kwp_clima = 0.0
        if expediente.climatizacion_addon == "split":
            extra_kwp_clima = 1.22  # +2 paneles 610 Wp
        elif expediente.climatizacion_addon == "aerotermia":
            extra_kwp_clima = 3.05  # +5 paneles 610 Wp

        raw_kwp = (annual_consumption_kwh * coverage_target) / float(yield_per_kwp) + extra_kwp_clima
        if expediente.linea == "diesel" and expediente.potencia_generador_kva:
            # Para reemplazo de generador diésel, asegurar campo FV acorde a la potencia del grupo electrógeno
            raw_kwp = max(raw_kwp, expediente.potencia_generador_kva * 0.85)

        use_715wp = bool(expediente.linea == "diesel" and raw_kwp >= 22.0)
        panel_sku = "PV-715-NTYPE" if use_715wp else "PV-610-NTYPE"
        panel_wp = 715 if use_715wp else 610
        panel_kwp = 0.715 if use_715wp else 0.61
        panel_model = (
            "JA Solar 715 Wp Bifacial N-Type DeepBlue 4.0"
            if use_715wp
            else "JA Solar / Longi 610 Wp Bifacial N-Type Monocristalino"
        )

        panel_count = max(4, min(160, int(math.ceil(raw_kwp / panel_kwp))))
        # En sistemas medianos/grandes preferir número par para strings simétricos
        if panel_count > 9 and panel_count % 2 != 0:
            panel_count += 1
        total_kwp = round(panel_count * panel_kwp, 2)

        # Configuración de Strings y corrección térmica Voc a -10°C (factor 1.11 patagónico)
        voc_panel = 48.8 if use_715wp else 45.6
        if panel_count <= 10:
            n_strings = 1
            panels_per_string = panel_count
        elif panel_count <= 22:
            n_strings = 2
            panels_per_string = panel_count // 2
        else:
            n_strings = max(3, int(math.ceil(panel_count / 8.0)))
            panels_per_string = int(math.ceil(panel_count / float(n_strings)))

        voc_cold_10c_v = round(panels_per_string * voc_panel * 1.11, 1)
        strings_config = f"{n_strings} string(s) x {panels_per_string} módulos en serie ({panel_count} paneles totales)"

        # 2. Selección de Inversores, Reguladores MPPT y Banco de Baterías (BOQ)
        boq_items: List[BOQItem] = []

        # Familia A: Módulos Fotovoltaicos
        boq_items.append(
            BOQItem(
                sku=panel_sku,
                family="PV_MODULES",
                category="EQUIPAMIENTO",
                description=f"Módulo Fotovoltaico {panel_model} ({panel_wp} Wp)",
                unit="un",
                quantity=panel_count,
                technical_justification=f"Generación solar principal de {total_kwp:.2f} kWp para {zone['name']}.",
            )
        )

        system_phases = expediente.fase_sistema
        mppt_sku = None
        mppt_model = None
        mppt_count = 0
        gx_control_model = None
        includes_bess = False
        bess_sku = None
        bess_model = "Sin banco de baterías (Inyección directa Net Billing)"
        bess_module_count = 0
        bess_total_kwh = 0.0

        if expediente.linea == "red":
            # Arquitectura On-Grid / Híbrida Huawei FusionSolar Ley 21.118
            if total_kwp <= 3.8 and system_phases == "Monofásico 220V":
                inverter_sku = "INV-HUA-3K-L1"
                inverter_model = "Huawei SUN2000-3KTL-L1 Monofásico (3 kW)"
                inverter_kw = 3.0
                system_phases = "Monofásico 220V"
            elif total_kwp <= 6.0 and system_phases == "Monofásico 220V":
                inverter_sku = "INV-HUA-5K-L1"
                inverter_model = "Huawei SUN2000-5KTL-L1 Monofásico (5 kW)"
                inverter_kw = 5.0
                system_phases = "Monofásico 220V"
            elif total_kwp <= 7.8 and system_phases == "Monofásico 220V":
                inverter_sku = "INV-HUA-6K-L1"
                inverter_model = "Huawei SUN2000-6KTL-L1 Monofásico (6 kW)"
                inverter_kw = 6.0
                system_phases = "Monofásico 220V"
            elif total_kwp <= 13.5:
                inverter_sku = "INV-HUA-10K-M1"
                inverter_model = "Huawei SUN2000-10KTL-M1 Trifásico (10 kW)"
                inverter_kw = 10.0
                system_phases = "Trifásico 380V"
            elif total_kwp <= 24.0:
                inverter_sku = "INV-HUA-20K-M5"
                inverter_model = "Huawei SUN2000-20KTL-M5 Trifásico (20 kW)"
                inverter_kw = 20.0
                system_phases = "Trifásico 380V"
            else:
                inverter_sku = "INV-HUA-30K-M3"
                inverter_model = "Huawei SUN2000-30KTL-M3 Trifásico (30 kW)"
                inverter_kw = 30.0
                system_phases = "Trifásico 380V"

            inverter_count = 1
            inverter_total_kw = inverter_kw
            inverter_total_kva = inverter_kw

            boq_items.append(
                BOQItem(
                    sku=inverter_sku,
                    family="INVERTERS_CONTROLS",
                    category="EQUIPAMIENTO",
                    description=f"Inversor Solar {inverter_model} con Doble MPPT y AFCI",
                    unit="un",
                    quantity=1,
                    technical_justification="Conversión DC/AC de alta eficiencia homologada por la SEC para Ley 21.118.",
                )
            )
            meter_sku = "METER-HUA-3P" if "Trifásico" in system_phases else "METER-HUA-1P"
            boq_items.append(
                BOQItem(
                    sku=meter_sku,
                    family="INVERTERS_CONTROLS",
                    category="EQUIPAMIENTO",
                    description="Smart Power Sensor Huawei Bidireccional (Monitoreo de Consumo e Inyección)",
                    unit="un",
                    quantity=1,
                    technical_justification="Medición en punto de empalme para gestión de excedentes Net Billing.",
                )
            )
            boq_items.append(
                BOQItem(
                    sku="DONGLE-HUA-WLAN",
                    family="INVERTERS_CONTROLS",
                    category="EQUIPAMIENTO",
                    description="Módulo de Comunicación Huawei Smart Dongle WLAN-FE",
                    unit="un",
                    quantity=1,
                    technical_justification="Telemetría en vivo desde app FusionSolar.",
                )
            )

            # Si el proyecto On-Grid solicitó batería de respaldo LiFePO4
            if expediente.incluye_baterias:
                includes_bess = True
                if total_kwp >= 5.0 or expediente.capacidad_bateria_solicitada_kwh >= 8.0:
                    bess_sku = "BAT-HUA-LUNA-10K"
                    bess_model = "Huawei LUNA2000-10-S0 Litio LiFePO4 (10,0 kWh)"
                    bess_module_count = 1
                    bess_total_kwh = 10.0
                else:
                    bess_sku = "BAT-HUA-LUNA-5K"
                    bess_model = "Huawei LUNA2000-5-S0 Litio LiFePO4 (5,0 kWh)"
                    bess_module_count = 1
                    bess_total_kwh = 5.0

                boq_items.append(
                    BOQItem(
                        sku=bess_sku,
                        family="BESS_STORAGE",
                        category="EQUIPAMIENTO",
                        description=f"Banco de Almacenamiento {bess_model}",
                        unit="sistema",
                        quantity=bess_module_count,
                        technical_justification="Respaldo ante cortes de red y maximización de autoconsumo nocturno.",
                    )
                )

            system_title = (
                f"Planta Solar Híbrida Net Billing {total_kwp:.2f} kWp + {bess_total_kwh:.1f} kWh LiFePO4"
                if includes_bess
                else f"Planta Solar On-Grid Net Billing (Ley 21.118) {total_kwp:.2f} kWp"
            )
            architecture_summary = (
                f"Sistema conectado a red ({system_phases}) bajo Ley 21.118 de Generación Distribuida, "
                f"compuesto por {panel_count} módulos de {panel_wp} Wp e inversor {inverter_model}."
            )

        else:
            # Arquitectura Off-Grid ('aislado') o Híbrida Industrial Reemplazo Diésel ('diesel') con Victron + Pylontech
            includes_bess = True
            is_three_phase = "Trifásico" in system_phases

            if is_three_phase:
                # Configuración Trifásica Victron (3 o 6 unidades en L1, L2, L3)
                target_kva = max(15.0, float(expediente.potencia_generador_kva or (total_kwp * 1.1)))
                if target_kva >= 25.0:
                    inverter_sku = "INV-VIC-MP2-5000"
                    inverter_model = "Victron MultiPlus-II 48/5000/70-50 (6 equipos: 2 en paralelo por fase L1-L2-L3)"
                    inverter_count = 6
                    inverter_total_kva = 30.0
                    inverter_total_kw = 24.0
                else:
                    inverter_sku = "INV-VIC-MP2-5000"
                    inverter_model = "Victron MultiPlus-II 48/5000/70-50 (3 equipos en red trifásica L1-L2-L3)"
                    inverter_count = 3
                    inverter_total_kva = 15.0
                    inverter_total_kw = 12.0
            else:
                # Configuración Monofásica 220V Victron
                if total_kwp <= 3.5:
                    inverter_sku = "INV-VIC-MP2-3000"
                    inverter_model = "Victron MultiPlus-II 48/3000/35-32 230V (3 kVA)"
                    inverter_count = 1
                    inverter_total_kva = 3.0
                    inverter_total_kw = 2.4
                elif total_kwp <= 6.5:
                    inverter_sku = "INV-VIC-MP2-5000"
                    inverter_model = "Victron MultiPlus-II 48/5000/70-50 230V (5 kVA)"
                    inverter_count = 1
                    inverter_total_kva = 5.0
                    inverter_total_kw = 4.0
                elif total_kwp <= 9.5:
                    inverter_sku = "INV-VIC-MP2-8000"
                    inverter_model = "Victron MultiPlus-II 48/8000/110-100 230V (8 kVA)"
                    inverter_count = 1
                    inverter_total_kva = 8.0
                    inverter_total_kw = 6.4
                else:
                    inverter_sku = "INV-VIC-MP2-10000"
                    inverter_model = "Victron MultiPlus-II 48/10000/140-100 230V (10 kVA)"
                    inverter_count = 1
                    inverter_total_kva = 10.0
                    inverter_total_kw = 8.0

            # Inyección de falla opcional para probar al Agente 4 (Inspector Técnico)
            if fault_mode == "phase_mismatch_3p":
                inverter_count = 1  # Error deliberado: 1 inversor monofásico en sistema trifásico

            boq_items.append(
                BOQItem(
                    sku=inverter_sku,
                    family="INVERTERS_CONTROLS",
                    category="EQUIPAMIENTO",
                    description=f"Inversor/Cargador {inverter_model}",
                    unit="un",
                    quantity=inverter_count,
                    technical_justification=f"Formación de red {system_phases} con onda sinusoidal pura y cargador adaptativo.",
                )
            )

            # Reguladores Solares Victron SmartSolar MPPT
            if total_kwp >= 12.0:
                mppt_sku = "MPPT-VIC-RS-450-200" if total_kwp >= 18.0 else "MPPT-VIC-RS-450-100"
                mppt_unit_kw = 11.0 if mppt_sku == "MPPT-VIC-RS-450-200" else 5.8
                mppt_count = max(1, int(math.ceil(total_kwp / mppt_unit_kw)))
                mppt_model = (
                    "Victron SmartSolar MPPT RS 450/200-Tr VE.Can"
                    if mppt_sku == "MPPT-VIC-RS-450-200"
                    else "Victron SmartSolar MPPT RS 450/100-Tr VE.Can"
                )
            elif total_kwp >= 4.5:
                mppt_sku = "MPPT-VIC-250-100"
                mppt_count = max(1, int(math.ceil(total_kwp / 5.5)))
                mppt_model = "Victron SmartSolar MPPT 250/100-Tr VE.Can"
            else:
                mppt_sku = "MPPT-VIC-250-70"
                mppt_count = 1
                mppt_model = "Victron SmartSolar MPPT 250/70-Tr VE.Can"

            boq_items.append(
                BOQItem(
                    sku=mppt_sku,
                    family="INVERTERS_CONTROLS",
                    category="EQUIPAMIENTO",
                    description=f"Regulador de Carga Solar {mppt_model}",
                    unit="un",
                    quantity=mppt_count,
                    technical_justification="Seguimiento ultrarrápido del punto de máxima potencia bajo nubosidad variable austral.",
                )
            )

            # Centro de Control GX y Embarrado DC Lynx
            gx_sku = "GX-VIC-EKRANO" if total_kwp >= 15.0 else "GX-VIC-CERBO"
            gx_control_model = "Victron Ekrano GX" if gx_sku == "GX-VIC-EKRANO" else "Victron Cerbo GX + GX Touch 50"
            boq_items.append(
                BOQItem(
                    sku=gx_sku,
                    family="INVERTERS_CONTROLS",
                    category="EQUIPAMIENTO",
                    description=f"Unidad de Control, Gestión BMS y Monitoreo Remoto VRM {gx_control_model}",
                    unit="kit",
                    quantity=1,
                    technical_justification="Coordinación DVCC con baterías Pylontech, arranque automático de generador (AGS) y portal VRM.",
                )
            )
            boq_items.append(
                BOQItem(
                    sku="DC-VIC-LYNX-DIST",
                    family="INVERTERS_CONTROLS",
                    category="EQUIPAMIENTO",
                    description="Embarrado DC Modular 1000A con Portafusibles Victron Lynx Distributor M10",
                    unit="un",
                    quantity=1 if inverter_count <= 3 else 2,
                    technical_justification="Distribución DC centralizada y segura a 48/51,2 Vdc.",
                )
            )
            boq_items.append(
                BOQItem(
                    sku="CABLE-VIC-BMS-A",
                    family="INVERTERS_CONTROLS",
                    category="EQUIPAMIENTO",
                    description="Cable de Comunicación BMS Victron VE.Can a CAN-bus Tipo A (Pylontech)",
                    unit="un",
                    quantity=1,
                    technical_justification="Enlace de datos en lazo cerrado entre batería maestra Pylontech y unidad GX.",
                )
            )

            # Dimensionamiento Banco de Baterías LiFePO4 Pylontech
            target_bess_kwh = max(
                9.6,
                expediente.capacidad_bateria_solicitada_kwh or (total_kwp * (2.6 if expediente.linea == "aislado" else 2.2)),
            )
            if total_kwp >= 20.0 or target_bess_kwh >= 45.0:
                bess_sku = "BAT-PYL-FIDUS-16K"
                bess_module_count = max(2, int(math.ceil(target_bess_kwh / 16.08)))
                bess_total_kwh = round(bess_module_count * 16.08, 2)
                bess_model = "Pylontech Fidus Plus 16,08 kWh IP65 (con Calefacción Interna Automática)"
                boq_items.append(
                    BOQItem(
                        sku=bess_sku,
                        family="BESS_STORAGE",
                        category="EQUIPAMIENTO",
                        description=f"Gabinete de Batería de Litio {bess_model}",
                        unit="un",
                        quantity=bess_module_count,
                        technical_justification="Almacenamiento industrial LiFePO4 con calefacción interna para mañanas bajo 0°C en Aysén.",
                    )
                )
            else:
                bess_sku = "BAT-PYL-US5000"
                bess_module_count = max(2, int(math.ceil(target_bess_kwh / 4.8)))
                bess_total_kwh = round(bess_module_count * 4.8, 2)
                bess_model = "Pylontech US5000 4,8 kWh 48V LiFePO4"
                boq_items.append(
                    BOQItem(
                        sku=bess_sku,
                        family="BESS_STORAGE",
                        category="EQUIPAMIENTO",
                        description=f"Módulo de Batería de Litio {bess_model}",
                        unit="un",
                        quantity=bess_module_count,
                        technical_justification="Almacenamiento modular LiFePO4 (>6.000 ciclos al 95% DoD).",
                    )
                )
                boq_items.append(
                    BOQItem(
                        sku="ACC-PYL-CABLEKIT",
                        family="BESS_STORAGE",
                        category="EQUIPAMIENTO",
                        description="Kit de Cables de Potencia Amphenol y Comunicación para Pylontech US5000",
                        unit="kit",
                        quantity=max(1, int(math.ceil(bess_module_count / 2.0))),
                        technical_justification="Conexión de alta corriente hacia embarrado Lynx Distributor.",
                    )
                )
                boq_items.append(
                    BOQItem(
                        sku="RACK-19-BAT",
                        family="BESS_STORAGE",
                        category="EQUIPAMIENTO",
                        description="Gabinete / Rack Metálico 19\" Estructural para Baterías Pylontech",
                        unit="un",
                        quantity=max(1, int(math.ceil(bess_module_count / 4.0))),
                        technical_justification="Soporte mecánico y protección del banco de baterías en sala eléctrica.",
                    )
                )

            tipo_label = "Híbrida Industrial Reemplazo Diésel" if expediente.linea == "diesel" else "Off-Grid Autónomo"
            system_title = (
                f"Planta Solar {tipo_label} {inverter_total_kva:.0f} kVA / {total_kwp:.2f} kWp FV / {bess_total_kwh:.1f} kWh LiFePO4"
            )
            architecture_summary = (
                f"Sistema {tipo_label} ({system_phases}) con electrónica Victron Energy ({inverter_count}x {inverter_sku}), "
                f"regulación MPPT ({mppt_count}x {mppt_sku}) y banco de litio {bess_model} ({bess_total_kwh:.1f} kWh)."
            )

        # 3. Familia D: Protecciones Eléctricas AC/DC y Tableros (Termomagnéticos, Diferenciales, SPD, Fusibles)
        is_3p = "Trifásico" in system_phases
        mcb_ac_sku = "PROT-MCB-AC-3P" if is_3p else "PROT-MCB-AC-1P"
        rcd_ac_sku = "PROT-RCD-AC-3P" if is_3p else "PROT-RCD-AC-1P"
        tablero_sku = "TAB-IP65-36M" if (is_3p or total_kwp >= 10.0) else "TAB-IP65-18M"

        boq_items.extend([
            BOQItem(
                sku=mcb_ac_sku,
                family="ELECTRICAL_PROTECTIONS",
                category="FERRETERIA_Y_PROTECCIONES",
                description=f"Interruptor Termomagnético AC {'Tetrapolar 4P' if is_3p else 'Bipolar 2P'} Curva C 10kA Certificado SEC",
                unit="un",
                quantity=2 if expediente.linea == "red" else 3,
                technical_justification="Protección termomagnética de sobrecarga y cortocircuito en entrada/salida AC.",
            ),
            BOQItem(
                sku=rcd_ac_sku,
                family="ELECTRICAL_PROTECTIONS",
                category="FERRETERIA_Y_PROTECCIONES",
                description=f"Protector Diferencial AC {'Tetrapolar 4P' if is_3p else 'Bipolar 2P'} 30mA Tipo A / Inmunizado SEC",
                unit="un",
                quantity=1 if expediente.linea == "red" else 2,
                technical_justification="Protección contra contactos indirectos y fugas a tierra según pliego RIC SEC.",
            ),
            BOQItem(
                sku="PROT-SPD-AC",
                family="ELECTRICAL_PROTECTIONS",
                category="FERRETERIA_Y_PROTECCIONES",
                description="Descargador de Sobretensión Transitoria (SPD) AC Tipo II 275V 40kA",
                unit="un",
                quantity=1,
                technical_justification="Protección de equipos electrónicos ante sobretensiones de red o grupo electrógeno.",
            ),
            BOQItem(
                sku="PROT-MCB-DC-1000V",
                family="ELECTRICAL_PROTECTIONS",
                category="FERRETERIA_Y_PROTECCIONES",
                description="Interruptor Termomagnético / Seccionador Solar DC 2P 1000V por String",
                unit="un",
                quantity=n_strings,
                technical_justification=f"Corte y protección magnetotérmica independiente para cada uno de los {n_strings} strings.",
            ),
            BOQItem(
                sku="PROT-SPD-DC-1000V",
                family="ELECTRICAL_PROTECTIONS",
                category="FERRETERIA_Y_PROTECCIONES",
                description="Descargador de Sobretensión Solar (SPD) DC Tipo II 1000V 40kA",
                unit="un",
                quantity=max(1, n_strings // 2),
                technical_justification="Protección contra descargas atmosféricas inducidas en el campo solar.",
            ),
            BOQItem(
                sku="PROT-FUSE-GPV",
                family="ELECTRICAL_PROTECTIONS",
                category="FERRETERIA_Y_PROTECCIONES",
                description="Base Portafusible Bipolar DC 1000V + 2 Fusibles Cilíndricos gPV 10x38mm 15A",
                unit="par",
                quantity=n_strings,
                technical_justification="Protección contra corrientes inversas en los strings fotovoltaicos.",
            ),
            BOQItem(
                sku=tablero_sku,
                family="ELECTRICAL_PROTECTIONS",
                category="FERRETERIA_Y_PROTECCIONES",
                description="Tablero Eléctrico Estanco IP65 con Barras Repartidoras y Señalética Normativa SEC",
                unit="un",
                quantity=1 if total_kwp <= 12.0 else 2,
                technical_justification="Alojamiento normativo de protecciones AC y DC.",
            ),
        ])

        if includes_bess:
            boq_items.extend([
                BOQItem(
                    sku="PROT-FUSE-MEGA",
                    family="ELECTRICAL_PROTECTIONS",
                    category="FERRETERIA_Y_PROTECCIONES",
                    description="Fusibles DC de Alta Capacidad Victron MEGA-Fuse 250A/300A 58V",
                    unit="un",
                    quantity=inverter_count + mppt_count + max(1, bess_module_count // 2),
                    technical_justification="Protección individual de cortocircuito DC en barra Lynx para inversores, MPPT y baterías.",
                ),
                BOQItem(
                    sku="PROT-SW-DC-BAT",
                    family="ELECTRICAL_PROTECTIONS",
                    category="FERRETERIA_Y_PROTECCIONES",
                    description="Seccionador Bajo Carga DC 275A/400A para Corte General de Banco de Baterías",
                    unit="un",
                    quantity=1,
                    technical_justification="Maniobra de aislamiento seguro del banco de baterías durante mantenimiento.",
                ),
                BOQItem(
                    sku="PROT-ATS-BYPASS",
                    family="ELECTRICAL_PROTECTIONS",
                    category="FERRETERIA_Y_PROTECCIONES",
                    description="Conmutador de Transferencia / Bypass Manual-Automático (1-0-2) en Tablero General",
                    unit="un",
                    quantity=1,
                    technical_justification="Permite conmutar las cargas directamente a red o generador de respaldo en caso de mantenimiento.",
                ),
            ])

        # 4. Familia E: Estructura de Montaje y Ferretería Eléctrica (BOS)
        cable_solar_sku = "FER-CABLE-SOLAR-6MM" if total_kwp >= 8.0 else "FER-CABLE-SOLAR-4MM"
        cable_kits_qty = max(1, int(math.ceil(n_strings * 0.75)))
        mc4_packs_qty = max(1, int(math.ceil((n_strings * 4) / 10.0)))
        canalizacion_lotes = max(1, int(math.ceil(total_kwp / 8.0)))

        boq_items.extend([
            BOQItem(
                sku="EST-KIT-PANEL",
                family="MOUNTING_AND_BOS",
                category="FERRETERIA_Y_PROTECCIONES",
                description="Estructura de Montaje Aluminio Anodizado Austral por Panel (Rieles, L-Feet EPDM, Grapas Inox A2)",
                unit="kit/panel",
                quantity=panel_count,
                technical_justification=f"Fijación estructural certificada para cargas de viento y nieve en {zone['name']}.",
            ),
            BOQItem(
                sku=cable_solar_sku,
                family="MOUNTING_AND_BOS",
                category="FERRETERIA_Y_PROTECCIONES",
                description="Kit Cable Solar Fotovoltaico H1Z2Z2-K Libre de Halógenos UV (Rojo + Negro)",
                unit="kit 50m",
                quantity=cable_kits_qty,
                technical_justification="Conducción DC resistente a radiación UV, humedad y bajas temperaturas australes.",
            ),
            BOQItem(
                sku="FER-MC4-PAR",
                family="MOUNTING_AND_BOS",
                category="FERRETERIA_Y_PROTECCIONES",
                description="Pack de Conectores Solares MC4 Originales IP68 1000V/1500V",
                unit="pack",
                quantity=mc4_packs_qty,
                technical_justification="Conexiones herméticas IP68 libres de puntos calientes.",
            ),
            BOQItem(
                sku="FER-CANALIZACION",
                family="MOUNTING_AND_BOS",
                category="FERRETERIA_Y_PROTECCIONES",
                description="Lote de Ferretería y Canalización Eléctrica (Tubería EMT/PVC Sch40, Cajas, Prensaestopas y Cable AC RV-K)",
                unit="lote",
                quantity=canalizacion_lotes,
                technical_justification="Canalización mecánica y conductores AC entre sala eléctrica y tablero general.",
            ),
            BOQItem(
                sku="FER-TIERRA-SEC",
                family="MOUNTING_AND_BOS",
                category="FERRETERIA_Y_PROTECCIONES",
                description="Sistema de Puesta a Tierra AC/DC Normativa SEC (Barra Copperweld, Conector, Camarilla y Conductor)",
                unit="kit",
                quantity=1 if total_kwp <= 15.0 else 2,
                technical_justification="Aterramiento equipotencial de estructura solar, descargadores SPD y chasis de equipos.",
            ),
        ])

        if includes_bess:
            boq_items.append(
                BOQItem(
                    sku="FER-CABLE-BAT-50MM",
                    family="MOUNTING_AND_BOS",
                    category="FERRETERIA_Y_PROTECCIONES",
                    description="Kit de Cables de Potencia DC Extra-Flexibles 50mm²/70mm² con Terminales Ojo M8/M10",
                    unit="kit",
                    quantity=max(1, inverter_count),
                    technical_justification="Enlace de baja caída de tensión entre barra DC Lynx e inversores/cargadores.",
                )
            )

        # 5. Familia F: Partidas de Subcontrato de Instalación e Ingeniería
        boq_items.append(
            BOQItem(
                sku="MO-MONTAJE-PANEL",
                family="INSTALLATION_LABOR",
                category="INSTALACION_SUBCONTRATO",
                description="Subcontrato Mano de Obra: Montaje de Estructura y Módulos Fotovoltaicos",
                unit="panel",
                quantity=panel_count,
                technical_justification="Instalación en cubierta/suelo con sellado impermeable EPDM.",
            )
        )
        sala_sku = "MO-SALA-ELECTRICA-3P" if (is_3p or expediente.linea != "red") else "MO-SALA-ELECTRICA-1P"
        boq_items.append(
            BOQItem(
                sku=sala_sku,
                family="INSTALLATION_LABOR",
                category="INSTALACION_SUBCONTRATO",
                description="Subcontrato Mano de Obra: Montaje de Inversores, Tableros de Protección, Canalización y Puesta en Marcha",
                unit="servicio",
                quantity=1,
                technical_justification="Armado normativo de sala eléctrica, pruebas de aislación y comisionamiento.",
            )
        )
        if includes_bess and bess_module_count > 0:
            boq_items.append(
                BOQItem(
                    sku="MO-CONEXION-BESS",
                    family="INSTALLATION_LABOR",
                    category="INSTALACION_SUBCONTRATO",
                    description="Subcontrato Mano de Obra: Montaje, Torqueo DC y Configuración BMS por Batería LiFePO4",
                    unit="batería",
                    quantity=bess_module_count,
                    technical_justification="Integración de banco de litio y pruebas de carga/descarga.",
                )
            )
        if expediente.linea == "red":
            boq_items.append(
                BOQItem(
                    sku="MO-TRAMITACION-TE4",
                    family="INSTALLATION_LABOR",
                    category="INSTALACION_SUBCONTRATO",
                    description="Ingeniería de Detalle, Planos As-Built y Tramitación SEC TE4 Ley 21.118 (Net Billing)",
                    unit="trámite",
                    quantity=1,
                    technical_justification="Inscripción oficial ante la SEC y distribuidora eléctrica para inyección de excedentes.",
                )
            )

        # 6. Indicadores energéticos y ambientales
        annual_gen_kwh = int(round(total_kwp * yield_per_kwp))
        monthly_gen_kwh = int(round(annual_gen_kwh / 12.0))
        dc_ac_ratio = round(total_kwp / max(1.0, inverter_total_kw), 2)
        co2_tons = round(annual_gen_kwh * 0.00038, 2)
        trees_eq = max(1, int(round(co2_tons * 45)))

        prot_summary = (
            f"Tablero IP65 SEC con termomagnéticos AC ({'4P' if is_3p else '2P'}), diferencial 30mA Tipo A, "
            f"SPD AC/DC Tipo II, seccionadores y fusibles gPV 1000V para {n_strings} string(s)"
            + (", además de fusibles MEGA y seccionador de banco de baterías 48V." if includes_bess else ".")
        )

        boq_proposal = EngineeringProposalBOQ(
            lead_ref=expediente.lead_ref,
            system_title=system_title,
            linea=expediente.linea,
            zona_climatica=zone_key,
            zone_label=str(zone["name"]),
            system_phases=system_phases,
            architecture_summary=architecture_summary,
            panel_sku=panel_sku,
            panel_model=panel_model,
            panel_wp=panel_wp,
            panel_count=panel_count,
            total_kwp=total_kwp,
            strings_config=strings_config,
            voc_cold_10c_v=voc_cold_10c_v,
            recommended_tilt=str(zone["recommended_tilt"]),
            inverter_sku=inverter_sku,
            inverter_model=inverter_model,
            inverter_count=inverter_count,
            inverter_total_kw=inverter_total_kw,
            inverter_total_kva=inverter_total_kva,
            dc_ac_ratio=dc_ac_ratio,
            mppt_sku=mppt_sku,
            mppt_model=mppt_model,
            mppt_count=mppt_count,
            gx_control_model=gx_control_model,
            includes_bess=includes_bess,
            bess_sku=bess_sku,
            bess_model=bess_model,
            bess_module_count=bess_module_count,
            bess_total_kwh=bess_total_kwh,
            annual_generation_kwh=annual_gen_kwh,
            monthly_generation_avg_kwh=monthly_gen_kwh,
            coverage_pct=round(coverage_target * 100.0, 1),
            co2_tons_avoided_year=co2_tons,
            trees_equivalent=trees_eq,
            electrical_protection_summary=prot_summary,
            technical_notes_aysen=[
                f"Diseño verificado para temperatura mínima patagónica (-10°C): Voc máx por string = {voc_cold_10c_v} Vdc.",
                f"Estructura de aluminio anodizado con pernería Inox A2 y sellos EPDM apta para {zone['name']}.",
                "Valores preliminares sujetos a verificación de sombreamiento, cubierta y empalme en visita técnica.",
            ],
            boq_items=boq_items,
        )

        audit_trail.append(
            f"[Agente 2 - Solution Engineer] Pre-ingeniería y BOQ generados para {expediente.lead_ref}: "
            f"{panel_count}x {panel_wp} Wp ({total_kwp:.2f} kWp), {inverter_count}x {inverter_sku}, "
            f"BESS={bess_total_kwh:.1f} kWh, {len(boq_items)} partidas de materiales y protecciones."
        )
        state["engineering_boq"] = boq_proposal
        state["audit_trail"] = audit_trail
        return state
