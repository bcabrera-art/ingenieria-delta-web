"""
Capa de Persistencia SQLite (CRM, Embudo, Expedientes de los 4 Agentes y Control de Human Handoff).
Almacena toda la información levantada por el Agente 1 y los resultados de los Agentes 2, 3 y 4.
"""
from __future__ import annotations

import datetime
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.agents.commercial_agent import normalize_phone
from app.state import DeltaAgentGraphState


class DeltaCRMDatabase:
    def __init__(self, db_path: str | None = None) -> None:
        default_path = Path(__file__).resolve().parent.parent / "data" / "delta_crm_leads.sqlite3"
        self.db_path = Path(db_path) if db_path else default_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS leads_expedientes (
                    lead_ref TEXT PRIMARY KEY,
                    phone TEXT,
                    nombre TEXT,
                    correo TEXT,
                    ubicacion TEXT,
                    linea TEXT,
                    etapa_embudo TEXT,
                    interested_dedalo INTEGER DEFAULT 0,
                    precio_final_neto_clp INTEGER DEFAULT 0,
                    precio_final_bruto_clp INTEGER DEFAULT 0,
                    inspector_approved INTEGER DEFAULT 0,
                    wa_contacted INTEGER DEFAULT 0,
                    proactive_sent INTEGER DEFAULT 0,
                    bot_paused INTEGER DEFAULT 0,
                    pdf_filename TEXT,
                    pdf_path TEXT,
                    state_json TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_leads_phone ON leads_expedientes(phone)")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS handoff_controls (
                    phone TEXT PRIMARY KEY,
                    bot_paused INTEGER DEFAULT 0,
                    reason TEXT,
                    updated_at TEXT
                )
                """
            )
            conn.commit()

    def save_pipeline_state(self, state: DeltaAgentGraphState) -> Dict[str, Any]:
        exp = state["expediente"]
        boq = state["engineering_boq"]
        quote = state["pricing_quote"]
        inspector = state["inspector_report"]
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        phone = normalize_phone(exp.telefono)

        serializable_state = {
            "expediente": exp.model_dump(),
            "engineering_boq": boq.model_dump(),
            "pricing_quote": quote.model_dump(exclude={"pdf_base64"}),
            "inspector_report": inspector.model_dump(),
            "commercial_presentation_message": state.get("commercial_presentation_message", ""),
            "available_calendar_slots": state.get("available_calendar_slots", []),
            "audit_trail": state.get("audit_trail", []),
        }

        with self._connect() as conn:
            existing = conn.execute(
                "SELECT wa_contacted, proactive_sent, bot_paused, created_at FROM leads_expedientes WHERE lead_ref = ?",
                (exp.lead_ref,),
            ).fetchone()

            wa_contacted = int(existing["wa_contacted"]) if existing else 0
            proactive_sent = int(existing["proactive_sent"]) if existing else 0
            bot_paused = int(existing["bot_paused"]) if existing else (1 if self.is_bot_paused(phone) else 0)
            created_at = str(existing["created_at"]) if existing else now_iso

            conn.execute(
                """
                INSERT OR REPLACE INTO leads_expedientes (
                    lead_ref, phone, nombre, correo, ubicacion, linea, etapa_embudo,
                    interested_dedalo, precio_final_neto_clp, precio_final_bruto_clp,
                    inspector_approved, wa_contacted, proactive_sent, bot_paused,
                    pdf_filename, pdf_path, state_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    exp.lead_ref,
                    phone,
                    exp.nombre,
                    exp.correo,
                    exp.ubicacion,
                    exp.linea,
                    exp.etapa_embudo,
                    1 if exp.dedalo_kyc.interested_in_zero_down_long_term else 0,
                    quote.precio_final_neto_cliente_clp,
                    quote.precio_final_bruto_cliente_clp,
                    1 if inspector.approved else 0,
                    wa_contacted,
                    proactive_sent,
                    bot_paused,
                    quote.pdf_filename,
                    quote.pdf_path,
                    json.dumps(serializable_state, ensure_ascii=False),
                    created_at,
                    now_iso,
                ),
            )
            conn.commit()
        return serializable_state

    def get_lead_by_ref_or_phone(self, ref_or_phone: str) -> Optional[Dict[str, Any]]:
        clean_ref = ref_or_phone.strip()
        norm_phone = normalize_phone(clean_ref)
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM leads_expedientes
                WHERE lead_ref = ? OR (phone != '' AND phone = ?)
                ORDER BY updated_at DESC LIMIT 1
                """,
                (clean_ref, norm_phone),
            ).fetchone()
            if not row:
                return None
            record = dict(row)
            record["state"] = json.loads(record.pop("state_json", "{}"))
            record["bot_paused"] = bool(record["bot_paused"] or self.is_bot_paused(record.get("phone", "")))
            return record

    def mark_whatsapp_contacted(self, ref_or_phone: str) -> bool:
        lead = self.get_lead_by_ref_or_phone(ref_or_phone)
        if not lead:
            return False
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                "UPDATE leads_expedientes SET wa_contacted = 1, updated_at = ? WHERE lead_ref = ?",
                (now_iso, lead["lead_ref"]),
            )
            conn.commit()
        return True

    def set_human_handoff(self, phone: str, paused: bool, reason: str = "manual_from_phone") -> Dict[str, Any]:
        norm_phone = normalize_phone(phone)
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO handoff_controls (phone, bot_paused, reason, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (norm_phone, 1 if paused else 0, reason, now_iso),
            )
            conn.execute(
                "UPDATE leads_expedientes SET bot_paused = ?, updated_at = ? WHERE phone = ?",
                (1 if paused else 0, now_iso, norm_phone),
            )
            conn.commit()
        return {"phone": norm_phone, "bot_paused": paused, "reason": reason, "updated_at": now_iso}

    def is_bot_paused(self, phone: str) -> bool:
        norm_phone = normalize_phone(phone)
        if not norm_phone:
            return False
        with self._connect() as conn:
            row = conn.execute(
                "SELECT bot_paused FROM handoff_controls WHERE phone = ?",
                (norm_phone,),
            ).fetchone()
            return bool(row and row["bot_paused"])

    def list_leads_funnel(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT lead_ref, phone, nombre, correo, ubicacion, linea, etapa_embudo,
                       interested_dedalo, precio_final_neto_clp, precio_final_bruto_clp,
                       inspector_approved, wa_contacted, bot_paused, pdf_filename, updated_at
                FROM leads_expedientes
                ORDER BY updated_at DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
