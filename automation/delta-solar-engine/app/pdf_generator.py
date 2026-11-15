"""
Generador de PDF Corporativo de Propuesta Técnica y Económica Preliminar No Vinculante
para Ingeniería Delta Aysén (Delta Aysén SpA).
Utilizado por el Agente 3 (PricingAndQuoteAgent) y auditado por el Agente 4 (TechnicalInspectorAgent).
"""
from __future__ import annotations

import base64
import datetime
import os
from pathlib import Path
from typing import Tuple

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.state import EngineeringProposalBOQ, LeadExpediente, PricingQuoteResult

# Paleta corporativa Ingeniería Delta Aysén
COLOR_DARK_FOREST = colors.HexColor("#13241B")
COLOR_DELTA_GREEN = colors.HexColor("#2E6F40")
COLOR_MINT_ACCENT = colors.HexColor("#8CD790")
COLOR_LIGHT_BG = colors.HexColor("#F6F4EF")
COLOR_WARNING_BG = colors.HexColor("#FFF8E7")
COLOR_BORDER = colors.HexColor("#CBD5E1")


def _fmt_clp(value: int) -> str:
    return "$" + f"{int(round(value)):,}".replace(",", ".")


def generate_proposal_pdf(
    expediente: LeadExpediente,
    boq: EngineeringProposalBOQ,
    quote: PricingQuoteResult,
    output_dir: str | None = None,
    inject_pdf_defect: bool = False,
) -> Tuple[str, str, int, str]:
    """
    Genera el archivo PDF oficial de la Propuesta Técnica Preliminar No Vinculante.
    Retorna: (pdf_filename, pdf_full_path, pdf_size_bytes, pdf_base64)
    """
    base_dir = Path(output_dir) if output_dir else Path(__file__).resolve().parent.parent / "generated_proposals"
    base_dir.mkdir(parents=True, exist_ok=True)

    clean_ref = expediente.lead_ref.replace("#", "").replace(" ", "_")
    clean_name = "".join(c if c.isalnum() else "_" for c in expediente.nombre)[:25].strip("_") or "Cliente"
    pdf_filename = f"Propuesta_Tecnica_Preliminar_Delta_{clean_ref}_{clean_name}.pdf"
    pdf_path = base_dir / pdf_filename

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title=f"Propuesta Técnica No Vinculante {expediente.lead_ref} - Ingeniería Delta Aysén",
        author="Delta Aysén SpA (Ingeniería Delta)",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "DeltaTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=17,
        textColor= colors.white,
    )
    subtitle_style = ParagraphStyle(
        "DeltaSub",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=COLOR_MINT_ACCENT,
    )
    section_style = ParagraphStyle(
        "DeltaSection",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=COLOR_DARK_FOREST,
        spaceBefore=8,
        spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "DeltaBody",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11.5,
        textColor=colors.HexColor("#1E293B"),
    )
    cell_style = ParagraphStyle(
        "DeltaCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.8,
        leading=10,
        textColor=colors.HexColor("#1E293B"),
    )
    cell_bold_style = ParagraphStyle(
        "DeltaCellBold",
        parent=cell_style,
        fontName="Helvetica-Bold",
    )
    header_cell_style = ParagraphStyle(
        "DeltaHeaderCell",
        parent=cell_bold_style,
        textColor=colors.white,
    )

    story = []
    issue_date = datetime.date.today().strftime("%d/%m/%Y")

    # 1. Encabezado Corporativo + Sello No Vinculante
    banner_title = (
        "PROPUESTA TÉCNICA Y ECONÓMICA PRELIMINAR (DOCUMENTO BORRADOR SIN SELLO)"
        if inject_pdf_defect
        else "PROPUESTA TÉCNICA PRELIMINAR NO VINCULANTE — SUJETA A VISITA TÉCNICA"
    )
    header_data = [
        [
            Paragraph("<b>INGENIERÍA DELTA AYSÉN (Delta Aysén SpA)</b><br/>Pangal 899, Puerto Aysén · Coyhaique · ingenieriadelta.cl", title_style),
            Paragraph(
                f"<b>Expediente:</b> {expediente.lead_ref}<br/>"
                f"<b>Fecha Emisión:</b> {issue_date}<br/>"
                f"<b>Vigencia:</b> 15 días corridos",
                subtitle_style,
            ),
        ],
        [
            Paragraph(f"<b>{banner_title}</b>", subtitle_style),
            Paragraph("<b>Contacto:</b> +56 9 6741 3329 · bcabrera@ingenieriadelta.cl", subtitle_style),
        ],
    ]
    header_table = Table(header_data, colWidths=[118 * mm, 64 * mm])
    header_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), COLOR_DARK_FOREST),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("LINEABOVE", (0, 1), (-1, 1), 0.5, COLOR_DELTA_GREEN),
            ]
        )
    )
    story.append(header_table)
    story.append(Spacer(1, 4 * mm))

    # 2. Antecedentes del Cliente y Pre-Ingeniería Conceptual
    story.append(Paragraph("1. Antecedentes del Proyecto y Pre-Ingeniería Conceptual", section_style))
    client_info_data = [
        [
            Paragraph("<b>Cliente / Titular:</b>", cell_bold_style),
            Paragraph(expediente.nombre, cell_style),
            Paragraph("<b>Localidad / Zona:</b>", cell_bold_style),
            Paragraph(f"{expediente.ubicacion} ({boq.zone_label})", cell_style),
        ],
        [
            Paragraph("<b>Perfil / Uso:</b>", cell_bold_style),
            Paragraph(f"{expediente.empresa} ({expediente.perfil_cliente.capitalize()})", cell_style),
            Paragraph("<b>Sistema / Empalme:</b>", cell_bold_style),
            Paragraph(f"{boq.system_title} ({boq.system_phases})", cell_style),
        ],
        [
            Paragraph("<b>Potencia Solar FV:</b>", cell_bold_style),
            Paragraph(f"{boq.total_kwp:.2f} kWp ({boq.panel_count}x {boq.panel_wp} Wp)", cell_style),
            Paragraph("<b>Generación Anual Est.:</b>", cell_bold_style),
            Paragraph(f"{boq.annual_generation_kwh:,}".replace(",", ".") + " kWh/año", cell_style),
        ],
        [
            Paragraph("<b>Configuración Strings:</b>", cell_bold_style),
            Paragraph(f"{boq.strings_config} (Voc -10°C: {boq.voc_cold_10c_v} Vdc)", cell_style),
            Paragraph("<b>Almacenamiento Litio:</b>", cell_bold_style),
            Paragraph(
                f"{boq.bess_total_kwh:.1f} kWh ({boq.bess_module_count}x {boq.bess_model})"
                if boq.includes_bess
                else "Sin baterías (On-Grid Net Billing directo)",
                cell_style,
            ),
        ],
    ]
    client_table = Table(client_info_data, colWidths=[34 * mm, 57 * mm, 36 * mm, 55 * mm])
    client_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), COLOR_LIGHT_BG),
                ("GRID", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(client_table)
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(f"<b>Resumen de Arquitectura:</b> {boq.architecture_summary}", body_style))
    story.append(Paragraph(f"<b>Protecciones Eléctricas Consideradas:</b> {boq.electrical_protection_summary}", body_style))
    story.append(Spacer(1, 3 * mm))

    # 3. Listado de Materiales, Protecciones y Ferretería Eléctrica (BOQ)
    story.append(Paragraph("2. Listado de Materiales, Equipamiento, Protecciones y Ferretería Eléctrica (BOQ)", section_style))

    boq_rows = [
        [
            Paragraph("<b>Ítem / SKU</b>", header_cell_style),
            Paragraph("<b>Descripción Técnica del Equipamiento / Material</b>", header_cell_style),
            Paragraph("<b>Cant.</b>", header_cell_style),
            Paragraph("<b>Unidad</b>", header_cell_style),
            Paragraph("<b>Subtotal Neto Cliente</b>", header_cell_style),
        ]
    ]

    for item in quote.priced_items:
        # Mostrar en la tabla BOQ todos los equipos, protecciones y ferretería (la instalación se consolida abajo)
        if item.category in ("EQUIPAMIENTO", "FERRETERIA_Y_PROTECCIONES"):
            boq_rows.append(
                [
                    Paragraph(item.sku, cell_style),
                    Paragraph(item.description, cell_style),
                    Paragraph(str(item.quantity), cell_style),
                    Paragraph(item.unit, cell_style),
                    Paragraph(_fmt_clp(item.client_subtotal_net_clp), cell_style),
                ]
            )

    boq_table = Table(boq_rows, colWidths=[35 * mm, 85 * mm, 13 * mm, 17 * mm, 32 * mm], repeatRows=1)
    boq_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), COLOR_DELTA_GREEN),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.4, COLOR_BORDER),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, COLOR_LIGHT_BG]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (2, 1), (3, -1), "CENTER"),
                ("ALIGN", (4, 1), (4, -1), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story.append(boq_table)
    story.append(Spacer(1, 4 * mm))

    # 4. Resumen Económico Final para el Cliente (Sin exponer costos de proveedor ni márgenes internos)
    story.append(Paragraph("3. Resumen Económico del Proyecto Llave en Mano (Valores para Cliente)", section_style))

    summary_rows = [
        [
            Paragraph("<b>Partida del Proyecto</b>", header_cell_style),
            Paragraph("<b>Alcance Incluido</b>", header_cell_style),
            Paragraph("<b>Valor Neto (CLP)</b>", header_cell_style),
        ],
        [
            Paragraph("1. Equipamiento Solar, Protecciones AC/DC y Ferretería Eléctrica", cell_style),
            Paragraph("Módulos FV, inversores/MPPT, baterías (si aplica), tableros IP65, termomagnéticos, diferenciales, SPD, estructura aluminio y conductores SEC.", cell_style),
            Paragraph(_fmt_clp(quote.venta_equipos_neto_clp), cell_style),
        ],
        [
            Paragraph("2. Logística, Flete a la Región de Aysén y Transporte a Obra", cell_style),
            Paragraph(f"Embalaje industrial, transporte consolidado hacia Región de Aysén y traslado local hasta {expediente.ubicacion}.", cell_style),
            Paragraph(_fmt_clp(quote.venta_logistica_neto_clp), cell_style),
        ],
        [
            Paragraph("3. Instalación Eléctrica, Montaje Estructural y Puesta en Marcha", cell_style),
            Paragraph("Mano de obra certificada, montaje en cubierta/suelo, conexionado AC/DC, comisionamiento y tramitación SEC TE4 (si aplica).", cell_style),
            Paragraph(_fmt_clp(quote.venta_instalacion_neto_clp), cell_style),
        ],
        [
            Paragraph("<b>PRECIO FINAL NETO CLIENTE</b>", cell_bold_style),
            Paragraph("<b>Total Neto Proyecto Llave en Mano (Sin IVA)</b>", cell_bold_style),
            Paragraph(f"<b>{_fmt_clp(quote.precio_final_neto_cliente_clp)}</b>", cell_bold_style),
        ],
        [
            Paragraph("IVA (19%)", cell_style),
            Paragraph("Impuesto al Valor Agregado legal vigente", cell_style),
            Paragraph(_fmt_clp(quote.iva_19_pct_clp), cell_style),
        ],
        [
            Paragraph("<b>PRECIO TOTAL PROYECTO (IVA INCLUIDO)</b>", cell_bold_style),
            Paragraph(f"<b>Equivalente referencial: {quote.precio_final_uf:.2f} UF (UF = {_fmt_clp(int(quote.uf_value_clp))})</b>", cell_bold_style),
            Paragraph(f"<b>{_fmt_clp(quote.precio_final_bruto_cliente_clp)}</b>", cell_bold_style),
        ],
    ]

    summary_table = Table(summary_rows, colWidths=[56 * mm, 92 * mm, 34 * mm])
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), COLOR_DARK_FOREST),
                ("BACKGROUND", (0, 4), (-1, 4), COLOR_LIGHT_BG),
                ("BACKGROUND", (0, 6), (-1, 6), COLOR_WARNING_BG),
                ("GRID", (0, 0), (-1, -1), 0.5, COLOR_BORDER),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (2, 1), (2, -1), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(summary_table)
    story.append(Spacer(1, 3 * mm))

    # 5. Alternativa de Financiamiento Largo Plazo Alza Dédalo ($0 Pie a 10, 15, 20 y 25 años)
    if quote.dedalo_options:
        story.append(
            Paragraph(
                "4. Alternativa de Financiamiento Largo Plazo Alza Dédalo ($0 Pie · 10 a 25 Años · 1ª Cuota en 4 Meses)",
                section_style,
            )
        )
        dedalo_rows = [
            [
                Paragraph("<b>Plazo Crédito</b>", cell_bold_style),
                Paragraph("<b>Pie Inicial</b>", cell_bold_style),
                Paragraph("<b>Cuota Mensual Est. (UF)</b>", cell_bold_style),
                Paragraph("<b>Cuota Mensual Est. (CLP)</b>", cell_bold_style),
                Paragraph("<b>Ahorro Solar Mensual Est.</b>", cell_bold_style),
            ]
        ]
        for term_key in ("10", "15", "20", "25"):
            opt = quote.dedalo_options.get(term_key)
            if opt:
                dedalo_rows.append(
                    [
                        Paragraph(f"{opt.term_years} años ({opt.months} meses)", cell_style),
                        Paragraph("$0 CLP (100% financiado)", cell_style),
                        Paragraph(f"{opt.monthly_fee_uf:.2f} UF/mes", cell_style),
                        Paragraph(f"{_fmt_clp(opt.monthly_fee_clp)}/mes", cell_style),
                        Paragraph(f"{_fmt_clp(quote.monthly_solar_savings_clp)}/mes", cell_style),
                    ]
                )
        dedalo_table = Table(dedalo_rows, colWidths=[36 * mm, 36 * mm, 36 * mm, 37 * mm, 37 * mm])
        dedalo_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), COLOR_LIGHT_BG),
                    ("GRID", (0, 0), (-1, -1), 0.4, COLOR_BORDER),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        story.append(dedalo_table)
        story.append(
            Paragraph(
                "<i>Requisitos evaluación comercial Alza Dédalo / Sunplug (solo si opta por $0 pie): Ser propietario del inmueble "
                "inscrito en el Conservador de Bienes Raíces (CBR) para inscripción de prenda sobre equipos solares y prohibición "
                "de venta (costos legales cubiertos en la estructuración vía sunplug.cl) y evaluación crediticia del RUT titular.</i>",
                body_style,
            )
        )
        story.append(Spacer(1, 3 * mm))

    # 6. Nota de Alcance No Vinculante e Invitación a Reunión / Visita Técnica
    footer_disclaimer_title = (
        "NOTA TÉCNICA IMPORTANTE (BORRADOR PRELIMINAR):"
        if inject_pdf_defect
        else "NOTA TÉCNICA IMPORTANTE (PROPUESTA TÉCNICA PRELIMINAR NO VINCULANTE):"
    )
    story.append(
        Paragraph(
            f"<b>{footer_disclaimer_title}</b> "
            "El presente documento constituye un dimensionamiento de pre-ingeniería conceptual y presupuesto referencial "
            "elaborado automáticamente a partir de los antecedentes suministrados por el cliente. El listado definitivo "
            "de materiales (BOQ), longitudes exactas de canalización y valor vinculante final se confirman tras una "
            "<b>Reunión Técnica de 30 minutos o Visita Técnica en Terreno</b> con nuestros ingenieros Benjamín Cabrera "
            "(bcabrera@ingenieriadelta.cl) y Carlos Díaz (cdiaz@ingenieriadelta.cl).",
            body_style,
        )
    )

    doc.build(story)

    pdf_bytes = pdf_path.read_bytes()
    pdf_b64 = base64.b64encode(pdf_bytes).decode("ascii")
    return pdf_filename, str(pdf_path), len(pdf_bytes), pdf_b64
