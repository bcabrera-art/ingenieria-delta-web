"""
Adaptador Dual-Provider de WhatsApp para Ingeniería Delta Aysén (+56 9 6741 3329).
Soporta:
1. Evolution API (Docker QR / Coexistencia con el teléfono móvil de Delta)
2. WhatsApp Cloud API Oficial (Meta Graph API para escalamiento en producción)
"""
from __future__ import annotations

import os
from typing import Any, Dict

import httpx


class WhatsAppGateway:
    def __init__(self) -> None:
        self.provider = os.getenv("WHATSAPP_PROVIDER", "evolution").lower()
        self.evolution_url = os.getenv("EVOLUTION_API_URL", "http://evolution-api:8080")
        self.evolution_instance = os.getenv("EVOLUTION_INSTANCE", "delta_aysen")
        self.evolution_apikey = os.getenv("EVOLUTION_API_KEY", "")
        self.meta_token = os.getenv("META_WA_ACCESS_TOKEN", "")
        self.meta_phone_id = os.getenv("META_WA_PHONE_NUMBER_ID", "")

    def send_proposal_message_and_pdf(
        self,
        phone: str,
        message_text: str,
        pdf_filename: str,
        pdf_base64: str,
    ) -> Dict[str, Any]:
        """
        Envía el mensaje comercial del Agente 1 + el documento PDF validado por el Agente 4.
        Si no hay credenciales externas activas (modo test/local), retorna el recibo simulado.
        """
        clean_number = "".join(c for c in phone if c.isdigit())

        if self.provider == "evolution" and self.evolution_apikey:
            try:
                headers = {"apikey": self.evolution_apikey, "Content-Type": "application/json"}
                with httpx.Client(timeout=15.0) as client:
                    # 1. Enviar mensaje de texto ejecutivo
                    client.post(
                        f"{self.evolution_url}/message/sendText/{self.evolution_instance}",
                        headers=headers,
                        json={"number": clean_number, "text": message_text},
                    )
                    # 2. Enviar PDF adjunto
                    resp = client.post(
                        f"{self.evolution_url}/message/sendMedia/{self.evolution_instance}",
                        headers=headers,
                        json={
                            "number": clean_number,
                            "mediatype": "document",
                            "mimetype": "application/pdf",
                            "caption": f"Propuesta Técnica No Vinculante — {pdf_filename}",
                            "media": pdf_base64,
                            "fileName": pdf_filename,
                        },
                    )
                    return {"sent": resp.status_code < 300, "provider": "evolution", "status_code": resp.status_code}
            except Exception as exc:
                return {"sent": False, "provider": "evolution", "error": str(exc)}

        if self.provider == "meta" and self.meta_token and self.meta_phone_id:
            try:
                headers = {"Authorization": f"Bearer {self.meta_token}", "Content-Type": "application/json"}
                with httpx.Client(timeout=15.0) as client:
                    resp = client.post(
                        f"https://graph.facebook.com/v21.0/{self.meta_phone_id}/messages",
                        headers=headers,
                        json={
                            "messaging_product": "whatsapp",
                            "to": clean_number,
                            "type": "text",
                            "text": {"body": message_text},
                        },
                    )
                    return {"sent": resp.status_code < 300, "provider": "meta", "status_code": resp.status_code}
            except Exception as exc:
                return {"sent": False, "provider": "meta", "error": str(exc)}

        return {
            "sent": True,
            "simulated": True,
            "provider": self.provider,
            "recipient": clean_number,
            "pdf_filename": pdf_filename,
        }
