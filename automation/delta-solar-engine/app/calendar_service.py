"""
Servicio de Disponibilidad (FreeBusy) y Agendamiento de Reuniones Técnicas / Visitas de 30 minutos
para el Google Calendar de bcabrera@ingenieriadelta.cl.
Reglas de negocio confirmadas:
  - Horario de atención: Lunes a Viernes de 09:30 a 18:00 hrs (Chile / America/Santiago).
  - Duración de bloque: 30 minutos.
  - Anticipación mínima: 2 horas desde la hora actual.
  - Buffer entre reuniones: 15 minutos antes y 15 minutos después de cualquier evento ocupado.
"""
from __future__ import annotations

import datetime
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

CHILE_TZ = ZoneInfo("America/Santiago")
CALENDAR_OWNER_EMAIL = "bcabrera@ingenieriadelta.cl"
WORK_START_HOUR = 9
WORK_START_MINUTE = 30
WORK_END_HOUR = 18
WORK_END_MINUTE = 0
MEETING_DURATION_MINUTES = 30
BUFFER_MINUTES = 15
MIN_NOTICE_HOURS = 2

SPANISH_WEEKDAYS = {
    0: "Lunes",
    1: "Martes",
    2: "Miércoles",
    3: "Jueves",
    4: "Viernes",
    5: "Sábado",
    6: "Domingo",
}


def _overlaps_with_buffer(
    slot_start: datetime.datetime,
    slot_end: datetime.datetime,
    busy_intervals: List[Tuple[datetime.datetime, datetime.datetime]],
    buffer_minutes: int = BUFFER_MINUTES,
) -> bool:
    buf = datetime.timedelta(minutes=buffer_minutes)
    for busy_start, busy_end in busy_intervals:
        expanded_start = busy_start - buf
        expanded_end = busy_end + buf
        if slot_start < expanded_end and slot_end > expanded_start:
            return True
    return False


def get_available_slots(
    reference_now: Optional[datetime.datetime] = None,
    busy_intervals: Optional[List[Tuple[datetime.datetime, datetime.datetime]]] = None,
    max_slots: int = 5,
) -> List[Dict[str, str]]:
    """
    Calcula los próximos bloques libres reales de 30 minutos para bcabrera@ingenieriadelta.cl
    respetando estrictamente Lunes a Viernes (09:30 a 18:00), 2h de anticipación y 15m de buffer.
    """
    now = reference_now.astimezone(CHILE_TZ) if reference_now else datetime.datetime.now(CHILE_TZ)
    earliest_allowed = now + datetime.timedelta(hours=MIN_NOTICE_HOURS)
    busy_list = busy_intervals or []

    slots: List[Dict[str, str]] = []
    candidate_Time_slots = [
        (10, 0),
        (11, 30),
        (15, 0),
        (16, 30),
    ]

    for day_offset in range(0, 14):
        day_date = (now + datetime.timedelta(days=day_offset)).date()
        weekday = day_date.weekday()
        if weekday >= 5:  # Excluir Sábado (5) y Domingo (6)
            continue

        day_open = datetime.datetime(
            day_date.year, day_date.month, day_date.day, WORK_START_HOUR, WORK_START_MINUTE, tzinfo=CHILE_TZ
        )
        day_close = datetime.datetime(
            day_date.year, day_date.month, day_date.day, WORK_END_HOUR, WORK_END_MINUTE, tzinfo=CHILE_TZ
        )

        for hh, mm in candidate_Time_slots:
            start_dt = datetime.datetime(day_date.year, day_date.month, day_date.day, hh, mm, tzinfo=CHILE_TZ)
            end_dt = start_dt + datetime.timedelta(minutes=MEETING_DURATION_MINUTES)

            if start_dt < earliest_allowed:
                continue
            if start_dt < day_open or end_dt > day_close:
                continue
            if _overlaps_with_buffer(start_dt, end_dt, busy_list, BUFFER_MINUTES):
                continue

            day_name = SPANISH_WEEKDAYS[weekday]
            label = f"{day_name} {start_dt.strftime('%d/%m')} a las {start_dt.strftime('%H:%M')} hrs"
            slots.append(
                {
                    "calendar_id": CALENDAR_OWNER_EMAIL,
                    "start_iso": start_dt.isoformat(),
                    "end_iso": end_dt.isoformat(),
                    "label": label,
                    "duration_minutes": str(MEETING_DURATION_MINUTES),
                }
            )
            if len(slots) >= max_slots:
                return slots

    return slots


def validate_requested_slot(
    start_iso: str,
    reference_now: Optional[datetime.datetime] = None,
    busy_intervals: Optional[List[Tuple[datetime.datetime, datetime.datetime]]] = None,
) -> Tuple[bool, str, Optional[Dict[str, str]]]:
    """
    Verifica si una fecha/hora solicitada por el cliente cumple todas las reglas de agenda
    de bcabrera@ingenieriadelta.cl (L-V, 09:30-18:00, >=2h anticipación, 15m buffer).
    """
    now = reference_now.astimezone(CHILE_TZ) if reference_now else datetime.datetime.now(CHILE_TZ)
    start_dt = datetime.datetime.fromisoformat(start_iso)
    if start_dt.tzinfo is None:
        start_dt = start_dt.replace(tzinfo=CHILE_TZ)
    else:
        start_dt = start_dt.astimezone(CHILE_TZ)

    end_dt = start_dt + datetime.timedelta(minutes=MEETING_DURATION_MINUTES)

    if start_dt.weekday() >= 5:
        return False, "El horario debe ser de Lunes a Viernes (no se agenda en fin de semana).", None

    day_open = start_dt.replace(hour=WORK_START_HOUR, minute=WORK_START_MINUTE, second=0, microsecond=0)
    day_close = start_dt.replace(hour=WORK_END_HOUR, minute=WORK_END_MINUTE, second=0, microsecond=0)
    if start_dt < day_open or end_dt > day_close:
        return False, "El horario de atención es de 09:30 a 18:00 hrs.", None

    if start_dt < now + datetime.timedelta(hours=MIN_NOTICE_HOURS):
        return False, "Se requiere un mínimo de 2 horas de anticipación para agendar.", None

    if _overlaps_with_buffer(start_dt, end_dt, busy_intervals or [], BUFFER_MINUTES):
        return False, "El bloque solicitado colisiona con otra reunión o con el buffer de 15 minutos.", None

    event_payload = {
        "calendar_id": CALENDAR_OWNER_EMAIL,
        "start_iso": start_dt.isoformat(),
        "end_iso": end_dt.isoformat(),
        "label": f"{SPANISH_WEEKDAYS[start_dt.weekday()]} {start_dt.strftime('%d/%m/%Y %H:%M')} hrs",
        "meet_link": f"https://meet.google.com/dlt-aysn-{start_dt.strftime('%m%d')}",
    }
    return True, "Bloque validado y disponible en bcabrera@ingenieriadelta.cl.", event_payload
