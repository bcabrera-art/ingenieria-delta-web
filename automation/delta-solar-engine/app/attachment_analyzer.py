"""
Analizador Multimodal de Adjuntos (Boleta Eléctrica PDF y Foto de Placa de Generador)
usando Google Gemini 2.5 Flash (google-genai) con fallback determinista local (PyMuPDF / regex).
"""
from __future__ import annotations

import base64
import json
import os
import re
from typing import Any, Dict, Optional

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None


def _extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    if fitz is not None:
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            text = "\n".join(page.get_text("text") for page in doc)
            doc.close()
            return text
        except Exception:
            pass
    return ""


def analyze_attachment(
    filename: str,
    mime_type: str,
    content_base64: str,
    gemini_api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Extrae datos estructurados desde una boleta eléctrica en PDF (Edelaysen / Saesa)
    o una fotografía de placa/chasis de generador diésel.
    """
    api_key = gemini_api_key or os.getenv("GEMINI_API_KEY", "")
    raw_bytes = base64.b64decode(content_base64) if content_base64 else b""
    is_pdf = "pdf" in mime_type.lower() or filename.lower().endswith(".pdf")

    # 1. Extracción con Google Gemini 2.5 Flash si hay API Key configurada
    if api_key and raw_bytes:
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)
            prompt = (
                "Eres un ingeniero eléctrico de Delta Aysén. Analiza este documento adjunto. "
                "Si es una boleta eléctrica chilena (ej. Edelaysen, Saesa), extrae en JSON: "
                '{"tipo_adjunto": "boleta_electrica", "distribuidora": str, "consumo_kwh_mes": float, '
                '"monto_total_clp": int, "tarifa": str, "numero_cliente": str, "direccion": str}. '
                "Si es una foto de generador o placa técnica, extrae en JSON: "
                '{"tipo_adjunto": "placa_generador", "potencia_kva": float, "potencia_kw": float, '
                '"fases": "Monofásico 220V" | "Trifásico 380V", "marca_modelo": str}. '
                "Responde únicamente con el objeto JSON válido."
            )
            response = client.models.generate_content(
                model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
                contents=[
                    types.Part.from_bytes(data=raw_bytes, mime_type=mime_type),
                    prompt,
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.0,
                ),
            )
            if response and response.text:
                parsed = json.loads(response.text)
                parsed["extraction_engine"] = "gemini-2.5-flash"
                return parsed
        except Exception as exc:
            # Continúa hacia el extractor determinista local si la API no está disponible
            fallback_note = f"Fallback local activado ({type(exc).__name__})"
    else:
        fallback_note = "Extracción local determinista (sin GEMINI_API_KEY activa)"

    # 2. Extractor determinista local para PDFs (PyMuPDF + expresiones regulares de boletas chilenas)
    if is_pdf and raw_bytes:
        text = _extract_text_from_pdf_bytes(raw_bytes)
        distribuidora = "Edelaysen"
        if re.search(r"saesa", text, re.I):
            distribuidora = "Saesa"
        elif re.search(r"frontel", text, re.I):
            distribuidora = "Frontel"
        elif re.search(r"crell", text, re.I):
            distribuidora = "CRELL"

        kwh_match = re.search(r"(\d{2,6}(?:[.,]\d{1,2})?)\s*kWh", text, re.I)
        clp_match = re.search(r"\$\s*([\d.]{4,10})", text)
        tarifa_match = re.search(r"\b(BT1[a-z]?|BT2|BT3|BT4\.?\d?|AT4\.?\d?|TRAT1)\b", text, re.I)

        kwh_val = float(kwh_match.group(1).replace(".", "").replace(",", ".")) if kwh_match else None
        clp_val = int(clp_match.group(1).replace(".", "")) if clp_match else None

        return {
            "tipo_adjunto": "boleta_electrica",
            "filename": filename,
            "distribuidora": distribuidora,
            "consumo_kwh_mes": kwh_val,
            "monto_total_clp": clp_val,
            "tarifa": tarifa_match.group(1).upper() if tarifa_match else "BT1",
            "extraction_engine": fallback_note,
        }

    # 3. Fallback para fotografía de generador cuando no hay GEMINI_API_KEY
    kva_hint = re.search(r"(\d{1,3})\s*kva", filename, re.I)
    return {
        "tipo_adjunto": "placa_generador",
        "filename": filename,
        "potencia_kva": float(kva_hint.group(1)) if kva_hint else None,
        "fases": "Trifásico 380V" if "3p" in filename.lower() or "trif" in filename.lower() else None,
        "extraction_engine": fallback_note,
    }
