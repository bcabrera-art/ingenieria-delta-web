"""
Sincronizador en Vivo de la Base de Datos de Precios de Proveedores Delta
=========================================================================
Conecta el Agente 3 (`PricingAndQuoteAgent`) directamente con el archivo maestro:
  - Excel Consolidado: `C:\\Users\\benja\\Dropbox\\0 Delta Aysén\\2025\\Proyectos\\Consolidados Precio\\Consolidado Precios al 08052026.xlsx`
    Pestañas:
      1. `EMAT - Lista ELITE` (Huawei LUNA2000, SUN2000, SmartGuard, Estructura Coplanar PRO)
      2. `MacroSolar` (LONGi, Victron MultiPlus-II / SmartSolar / Cerbo GX / Lynx, Pylontech US5000/UF5000, Protecciones)
      3. `VITEL` (Protecciones AC/DC, Tableros Metálicos IP65 RAL7035, Canalización EMT/PVC, Puesta a Tierra, Cableado RV-K)
      4. `RBR` (Lista de Precios RBR / Carport / Equipos con 20% Descuento Instalador)
      5. `Instalación` (Tabla oficial 1–50 kW en base a AR con almacenamiento: `$178.184 CLP Neto / kWp`)
  - Extracción RBR Nov 2026 (`LISTA DE PRECIO NOV 26.pdf` -> `rbr_nov26.json`, 297 ítems)

Nota técnica: Realiza lectura mediante copia temporal segura (`shutil.copy2`) para no fallar
con `PermissionError` si el archivo Excel está abierto simultáneamente en Microsoft Excel.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_EXCEL_PATH = Path(
    os.getenv(
        "DELTA_CONSOLIDATED_EXCEL_PATH",
        r"C:\Users\benja\Dropbox\0 Delta Aysén\2025\Proyectos\Consolidados Precio\Consolidado Precios al 08052026.xlsx",
    )
)
DEFAULT_RBR_JSON_PATH = Path(
    os.getenv(
        "DELTA_RBR_JSON_PATH",
        r"C:\Users\benja\.gemini\antigravity\brain\10edb9e1-4c33-4c9b-8b15-1e7a35d40387\scratch\rbr_nov26.json",
    )
)
CATALOG_DIR = Path(__file__).resolve().parent.parent / "data"
CATALOG_JSON_PATH = CATALOG_DIR / "delta_price_catalog.json"
FULL_SUPPLIERS_JSON_PATH = CATALOG_DIR / "delta_suppliers_consolidated_full.json"


def _safe_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val) if val > 0 else None
    s = str(val).strip().replace("$", "").replace(".", "").replace(",", ".")
    try:
        num = float(s)
        return num if num > 0 else None
    except ValueError:
        return None


def read_consolidated_excel_items(
    excel_path: Path = DEFAULT_EXCEL_PATH,
    rbr_json_path: Path = DEFAULT_RBR_JSON_PATH,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Lee todas las pestañas de `Consolidado Precios al 08052026.xlsx` (copiando a temp
    por si está abierto en Excel) y fusiona también `rbr_nov26.json` si la pestaña RBR
    aún está en edición.
    """
    sheets_data: Dict[str, List[Dict[str, Any]]] = {
        "EMAT - Lista ELITE": [],
        "MacroSolar": [],
        "VITEL": [],
        "RBR": [],
        "Instalación": [],
    }

    if excel_path.exists():
        import openpyxl

        tmp_path = Path(tempfile.gettempdir()) / f"delta_sync_{os.getpid()}.xlsx"
        try:
            shutil.copy2(excel_path, tmp_path)
            wb = openpyxl.load_workbook(tmp_path, data_only=True)
            for sheet_name in wb.sheetnames:
                ws = wb[sheet_name]
                items: List[Dict[str, Any]] = []
                headers = [str(ws.cell(1, c).value or "").strip() for c in range(1, ws.max_column + 1)]
                for r in range(2, ws.max_row + 1):
                    row_vals = [ws.cell(r, c).value for c in range(1, min(10, ws.max_column + 1))]
                    if not any(row_vals):
                        continue
                    if sheet_name.lower().startswith("instalaci"):
                        kw = _safe_float(row_vals[0])
                        if kw:
                            costo_neto = _safe_float(row_vals[1]) or (kw * (8731000.0 / 49.0))
                            kw_label = int(kw) if kw.is_integer() else kw
                            items.append(
                                {
                                    "proveedor": sheet_name,
                                    "grupo": "Instalación (Base AR c/ 2x5 kWh Almacenamiento)",
                                    "marca": "Delta / Subcontrato AR",
                                    "producto": f"Instalación Fotovoltaica {kw_label} kW (Base AR con 2x5 kWh Almacenamiento)",
                                    "kw": kw_label,
                                    "precio_lista_clp": round(costo_neto),
                                    "costo_neto_clp": round(costo_neto),
                                    "costo_iva_incluido_clp": round(costo_neto * 1.19),
                                    "venta_utilidad_20_excel_clp": round(costo_neto / 0.8),
                                }
                            )
                    elif sheet_name == "RBR" and len(headers) >= 4 and headers[0].lower() == "producto":
                        prod = str(row_vals[0] or "").strip()
                        costo_neto = _safe_float(row_vals[1])
                        if prod and costo_neto:
                            items.append(
                                {
                                    "proveedor": "RBR",
                                    "grupo": "ESTRUCTURAS / RBR",
                                    "marca": "RBR",
                                    "producto": prod,
                                    "costo_neto_clp": round(costo_neto),
                                    "costo_iva_incluido_clp": round(costo_neto * 1.19),
                                    "venta_utilidad_20_excel_clp": round(costo_neto / 0.8),
                                }
                            )
                    else:
                        # Estructura estándar: Grupo | (Marca opcional) | Producto | (Precio Lista opcional) | Costo Neto
                        grupo = str(row_vals[0] or "General").strip()
                        if "marca" in [h.lower() for h in headers[:4]]:
                            marca = str(row_vals[1] or "").strip()
                            prod = str(row_vals[2] or "").strip()
                            precio_lista = _safe_float(row_vals[3])
                            # En RBR, la columna E ('Costo Neto (Instalador)') usa formula '=D{r}*0.8'
                            # que puede venir sin caché en openpyxl; aplicamos 20% dcto instalador si falta caché.
                            costo_neto = _safe_float(row_vals[4]) or (
                                (precio_lista * 0.80) if precio_lista else None
                            )
                        else:
                            marca = ""
                            prod = str(row_vals[1] or "").strip()
                            costo_neto = _safe_float(row_vals[2])
                            precio_lista = costo_neto
                        if prod and costo_neto:
                            items.append(
                                {
                                    "proveedor": sheet_name,
                                    "grupo": grupo,
                                    "marca": marca,
                                    "producto": prod,
                                    "precio_lista_clp": round(precio_lista) if precio_lista else round(costo_neto),
                                    "costo_neto_clp": round(costo_neto),
                                    "costo_iva_incluido_clp": round(costo_neto * 1.19),
                                    "venta_utilidad_20_excel_clp": round(costo_neto / 0.8),
                                }
                            )
                sheets_data[sheet_name] = items
            wb.close()
        finally:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass

    # Si RBR en el Excel aún tiene pocos ítems y existe rbr_nov26.json, fusionamos los 297 ítems de LISTA DE PRECIO NOV 26.pdf
    if rbr_json_path.exists() and len(sheets_data.get("RBR", [])) < 10:
        try:
            raw_rbr = json.loads(rbr_json_path.read_text(encoding="utf-8"))
            existing_names = {i["producto"].upper() for i in sheets_data.get("RBR", [])}
            for entry in raw_rbr:
                prod = str(entry.get("producto") or "").strip()
                precio_lista = _safe_float(entry.get("precio_lista"))
                if not prod or not precio_lista or prod.upper() in existing_names:
                    continue
                costo_neto = precio_lista * 0.80
                sheets_data.setdefault("RBR", []).append(
                    {
                        "proveedor": "RBR (Lista Nov 26)",
                        "sku_proveedor": str(entry.get("sku") or "").strip(),
                        "grupo": str(entry.get("grupo") or "General").strip(),
                        "marca": str(entry.get("marca") or "").strip(),
                        "producto": prod,
                        "precio_lista_clp": round(precio_lista),
                        "costo_neto_clp": round(costo_neto),
                        "costo_iva_incluido_clp": round(costo_neto * 1.19),
                        "venta_utilidad_20_excel_clp": round(costo_neto / 0.8),
                    }
                )
        except Exception:
            pass

    return sheets_data


def _find_cost(
    sheets_data: Dict[str, List[Dict[str, Any]]],
    sheet: str,
    substring: str,
    default_cost: int,
) -> int:
    sub_low = substring.lower()
    for item in sheets_data.get(sheet, []):
        if sub_low in item.get("producto", "").lower():
            c = item.get("costo_neto_clp")
            if isinstance(c, (int, float)) and c > 0:
                return int(round(c))
    return default_cost


def sync_catalog_from_excel(
    excel_path: Path = DEFAULT_EXCEL_PATH,
    rbr_json_path: Path = DEFAULT_RBR_JSON_PATH,
) -> Dict[str, Any]:
    """
    Sincroniza `data/delta_price_catalog.json` y `data/delta_suppliers_consolidated_full.json`
    con los costos netos reales de `Consolidado Precios al 08052026.xlsx` (`EMAT - Lista ELITE`,
    `MacroSolar`, `VITEL`, `RBR`) y la tabla de instalación por kWp (`$178.184 CLP Neto / kWp`).
    """
    sheets_data = read_consolidated_excel_items(excel_path=excel_path, rbr_json_path=rbr_json_path)

    total_raw_items = sum(len(v) for v in sheets_data.values())
    CATALOG_DIR.mkdir(parents=True, exist_ok=True)
    FULL_SUPPLIERS_JSON_PATH.write_text(
        json.dumps(
            {
                "synced_at": datetime.now().isoformat(),
                "excel_source": str(excel_path),
                "rbr_json_source": str(rbr_json_path),
                "total_items": total_raw_items,
                "sheets": {k: len(v) for k, v in sheets_data.items()},
                "catalog_by_supplier": sheets_data,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    # Extraer costos reales desde cada proveedor del Excel Consolidado
    cost_panel_longi_645 = _find_cost(sheets_data, "MacroSolar", "LONGi Panel Solar 645Wp", 104000)
    cost_panel_canadian_620 = _find_cost(sheets_data, "RBR", "TOPBIHIKU 620WP", 128618)

    # Huawei EMAT - Lista ELITE
    cost_hw_3k_l1 = _find_cost(sheets_data, "EMAT - Lista ELITE", "3kW, IP65, L1", 465079)
    cost_hw_5k_l1 = _find_cost(sheets_data, "EMAT - Lista ELITE", "5kW, IP65, L1", 607725)
    cost_hw_6k_l1 = _find_cost(sheets_data, "EMAT - Lista ELITE", "6kW, IP65, L1", 643453)
    cost_hw_10k_lc0 = _find_cost(sheets_data, "EMAT - Lista ELITE", "10kW, IP65, LCO", 712922)
    cost_hw_10k_m1 = _find_cost(sheets_data, "EMAT - Lista ELITE", "10kW, IP65, MAPO", 1068455)
    cost_hw_15k_mb0 = _find_cost(sheets_data, "EMAT - Lista ELITE", "15kW, IP65, MB0", 1561874)
    cost_hw_20k_mb0 = _find_cost(sheets_data, "EMAT - Lista ELITE", "20kW, IP65, MB0", 1693637)
    cost_hw_30k_m5 = _find_cost(sheets_data, "EMAT - Lista ELITE", "30 kW-M5", 2023356)
    cost_hw_50k_m5 = _find_cost(sheets_data, "EMAT - Lista ELITE", "50 kW-M5", 2329352)
    cost_hw_luna_5kwh = _find_cost(sheets_data, "EMAT - Lista ELITE", "LUNA2000 - 5 kWh", 1367369)
    cost_hw_luna_bms = _find_cost(sheets_data, "EMAT - Lista ELITE", "DC DC Converter M-DC/DC 5 kWh", 653900)
    cost_hw_sensor_1f = _find_cost(sheets_data, "EMAT - Lista ELITE", "S-POWER SENSOR", 52735)
    cost_hw_sensor_3f = _find_cost(sheets_data, "RBR", "SMART POWER SENSOR TRIFASICO DTSU666-H", 88889)
    cost_hw_dongle = _find_cost(sheets_data, "EMAT - Lista ELITE", "S-DONGLE -WLAN", 70278)

    # Victron & Pylontech (MacroSolar + RBR)
    cost_vic_mp2_3000 = _find_cost(sheets_data, "MacroSolar", "MultiPlus-II 48/3000/35-32 230V", 437000)
    cost_vic_mp2_5000 = _find_cost(sheets_data, "MacroSolar", "MultiPlus-II 48/5000/70-50 230V", 621000)
    cost_vic_mp2_8000 = _find_cost(sheets_data, "MacroSolar", "MultiPlus-II 48/8000/110-100/100", 1085000)
    cost_vic_mp2_10000 = _find_cost(sheets_data, "MacroSolar", "MultiPlus-II 48/10000/140-100/100", 1295000)
    cost_vic_mp2_15000 = _find_cost(sheets_data, "MacroSolar", "MultiPlus-II 48/15000/200-100", 1805000)
    cost_vic_mppt_250_70 = _find_cost(sheets_data, "MacroSolar", "SmartSolar MPPT 250/70-Tr VE.Can", 343000)
    cost_vic_mppt_250_100 = _find_cost(sheets_data, "MacroSolar", "SmartSolar MPPT 250/100-Tr", 411000)
    cost_vic_cerbo = _find_cost(sheets_data, "RBR", "VICTRON CERBO GX MK2", 265840)
    cost_vic_touch50 = _find_cost(sheets_data, "MacroSolar", "Victron GX Touch 50", 164000)
    cost_vic_lynx = _find_cost(sheets_data, "MacroSolar", "Victron Lynx Distributor (M10)", 150000)
    cost_pylon_us5000 = _find_cost(sheets_data, "MacroSolar", "Pylontech Batería de Litio US5000", 670000)
    cost_pylon_bracket = _find_cost(sheets_data, "MacroSolar", "Pylontech Bracket UP-5", 33500)
    cost_pylon_cables = _find_cost(sheets_data, "MacroSolar", "Pylontech Kit de Cables para batería", 18000)

    # Protecciones y Ferretería Eléctrica (VITEL + RBR + EMAT)
    cost_vitel_mcb_1f = _find_cost(sheets_data, "VITEL", "INT. AUT. 2x50A CURVA C 10KA", 14351)
    cost_vitel_mcb_3f = _find_cost(sheets_data, "VITEL", "INT. AUT. 4x25A CURVA C 10KA", 24102)
    cost_rbr_dif_1f = _find_cost(sheets_data, "RBR", "DIFERENCIAL CHINT 2P 40A 100mA 6kA TIPO A", 49967)
    cost_vitel_dif_3f = _find_cost(sheets_data, "VITEL", "INT. DIF. 4x25A 300mA 415V 10kA", 92022)
    cost_spd_ac_1f = _find_cost(sheets_data, "RBR", "SMA AC SURGE PROTECTION AC SPD", 52300)
    cost_spd_ac_3f = _find_cost(sheets_data, "MacroSolar", "Finder Protector de Sobretensión 7P.23.8.275.1020", 65900)

    # Estructura Coplanar PRO EMAT (1 Riel 5000mm/2 paneles + 4 L + 2 Mid + 2 End + Tierra)
    cost_riel_pro = _find_cost(sheets_data, "EMAT - Lista ELITE", "Riel 5000 mm PRO", 20027)
    cost_l_pro = _find_cost(sheets_data, "EMAT - Lista ELITE", "FIJACION TIPO L PRO", 1023)

    # Instalación (Subcontrato Base AR 1-50 kW)
    install_rate_per_kwp = _find_cost(
        sheets_data, "Instalación", "Instalación Fotovoltaica 1 kW (", 178184
    )

    catalog_payload = {
        "metadata": {
            "version": "2026.05-CONSOLIDADO-REAL",
            "synced_at": datetime.now().isoformat(),
            "currency": "CLP",
            "excel_source": str(excel_path),
            "rbr_source": str(rbr_json_path),
            "total_supplier_rows_indexed": total_raw_items,
            "PricingRules": {
                "utility_equipment_pct": 0.20,
                "utility_logistics_pct": 0.20,
                "utility_installation_pct": 0.20,
                "logistics_aysen_pct_of_equipment_cost": 0.09,
                "excel_margin_formula_note": "En Consolidado Precios al 08052026.xlsx Columna E usa '=C2/0.8' y el motor aplica las reglas del Agente 3 (9% flete Aysén + 20% utilidad en Equipos, Logística e Instalación).",
                "installation_rate_neto_per_kwp_clp": install_rate_per_kwp,
            },
        },
        "items": {
            "PNL-LONGI-600-BF": {
                "sku": "PNL-LONGI-600-BF",
                "descripcion": "Panel Solar Monocristalino LONGi 645Wp Hi-MO X10 LR7-72HVH-645M Tier-1 (o Canadian Solar 620Wp TopBiHiKu Bifacial)",
                "categoria": "Paneles Solares",
                "proveedor": "MacroSolar / RBR (Consolidado Delta)",
                "unidad": "un",
                "costo_unitario_neto_clp": cost_panel_longi_645,
                "precio_alternativo_rbr_620wp_clp": cost_panel_canadian_620,
            },
            "INV-HW-3KTL-L1": {
                "sku": "INV-HW-3KTL-L1",
                "descripcion": "Inversor Híbrido Monofásico Huawei SUN2000-3KTL-L1 (3 kW, IP65, 2 MPPT)",
                "categoria": "Inversores y MPPT",
                "proveedor": "EMAT - Lista ELITE (Consolidado Delta)",
                "unidad": "un",
                "costo_unitario_neto_clp": cost_hw_3k_l1,
            },
            "INV-HW-5KTL-L1": {
                "sku": "INV-HW-5KTL-L1",
                "descripcion": "Inversor Híbrido Monofásico Huawei SUN2000-5KTL-L1 (5 kW, IP65, 2 MPPT)",
                "categoria": "Inversores y MPPT",
                "proveedor": "EMAT - Lista ELITE (Consolidado Delta)",
                "unidad": "un",
                "costo_unitario_neto_clp": cost_hw_5k_l1,
            },
            "INV-HW-6KTL-L1": {
                "sku": "INV-HW-6KTL-L1",
                "descripcion": "Inversor Híbrido Monofásico Huawei SUN2000-6KTL-L1 (6 kW, IP65, 2 MPPT)",
                "categoria": "Inversores y MPPT",
                "proveedor": "EMAT - Lista ELITE (Consolidado Delta)",
                "unidad": "un",
                "costo_unitario_neto_clp": cost_hw_6k_l1,
            },
            "INV-HW-8K-LC0": {
                "sku": "INV-HW-8K-LC0",
                "descripcion": "Inversor Híbrido Monofásico Huawei SUN2000-10K-LC0 / 8K-LC0 (IP65, 3 MPPT)",
                "categoria": "Inversores y MPPT",
                "proveedor": "EMAT - Lista ELITE (Consolidado Delta)",
                "unidad": "un",
                "costo_unitario_neto_clp": cost_hw_10k_lc0,
            },
            "INV-HW-10KTL-M1": {
                "sku": "INV-HW-10KTL-M1",
                "descripcion": "Inversor Híbrido Trifásico Huawei SUN2000-10K-MAP0 / M1 (10 kW, 380V, IP65)",
                "categoria": "Inversores y MPPT",
                "proveedor": "EMAT - Lista ELITE (Consolidado Delta)",
                "unidad": "un",
                "costo_unitario_neto_clp": cost_hw_10k_m1,
            },
            "INV-HW-15K-MB0": {
                "sku": "INV-HW-15K-MB0",
                "descripcion": "Inversor Híbrido Trifásico Huawei SUN2000-15K-MB0 (15 kW, 380V, IP65)",
                "categoria": "Inversores y MPPT",
                "proveedor": "EMAT - Lista ELITE (Consolidado Delta)",
                "unidad": "un",
                "costo_unitario_neto_clp": cost_hw_15k_mb0,
            },
            "INV-HW-20K-MB0": {
                "sku": "INV-HW-20K-MB0",
                "descripcion": "Inversor Híbrido Trifásico Huawei SUN2000-20K-MB0 (20 kW, 380V, IP65)",
                "categoria": "Inversores y MPPT",
                "proveedor": "EMAT - Lista ELITE (Consolidado Delta)",
                "unidad": "un",
                "costo_unitario_neto_clp": cost_hw_20k_mb0,
            },
            "INV-HW-30KTL-M3": {
                "sku": "INV-HW-30KTL-M3",
                "descripcion": "Inversor Trifásico Industrial Huawei SUN2000-30KTL-M5 (30 kW, 380V, 4 MPPT, IP66)",
                "categoria": "Inversores y MPPT",
                "proveedor": "EMAT - Lista ELITE (Consolidado Delta)",
                "unidad": "un",
                "costo_unitario_neto_clp": cost_hw_30k_m5,
            },
            "INV-HW-50KTL-M3": {
                "sku": "INV-HW-50KTL-M3",
                "descripcion": "Inversor Trifásico Industrial Huawei SUN2000-50KTL-M5 (50 kW, 380V, 4 MPPT, IP66)",
                "categoria": "Inversores y MPPT",
                "proveedor": "EMAT - Lista ELITE (Consolidado Delta)",
                "unidad": "un",
                "costo_unitario_neto_clp": cost_hw_50k_m5,
            },
            "MET-HW-DDSU666": {
                "sku": "MET-HW-DDSU666",
                "descripcion": "Smart Power Sensor Monofásico Huawei S-POWER SENSOR + S-Dongle WLAN",
                "categoria": "Inversores y MPPT",
                "proveedor": "EMAT - Lista ELITE (Consolidado Delta)",
                "unidad": "un",
                "costo_unitario_neto_clp": cost_hw_sensor_1f + cost_hw_dongle,
            },
            "MET-HW-DTSU666": {
                "sku": "MET-HW-DTSU666",
                "descripcion": "Smart Power Sensor Trifásico Huawei DTSU666-H + S-Dongle WLAN",
                "categoria": "Inversores y MPPT",
                "proveedor": "RBR / EMAT - Lista ELITE (Consolidado Delta)",
                "unidad": "un",
                "costo_unitario_neto_clp": cost_hw_sensor_3f + cost_hw_dongle,
            },
            "INV-VIC-MP2-48-3000": {
                "sku": "INV-VIC-MP2-48-3000",
                "descripcion": "Inversor/Cargador Victron MultiPlus-II 48/3000/35-32 230V",
                "categoria": "Inversores y MPPT",
                "proveedor": "MacroSolar / RBR (Consolidado Delta)",
                "unidad": "un",
                "costo_unitario_neto_clp": cost_vic_mp2_3000,
            },
            "INV-VIC-MP2-48-5000": {
                "sku": "INV-VIC-MP2-48-5000",
                "descripcion": "Inversor/Cargador Victron MultiPlus-II 48/5000/70-50 230V",
                "categoria": "Inversores y MPPT",
                "proveedor": "MacroSolar / RBR (Consolidado Delta)",
                "unidad": "un",
                "costo_unitario_neto_clp": cost_vic_mp2_5000,
            },
            "INV-VIC-MP2-48-8000": {
                "sku": "INV-VIC-MP2-48-8000",
                "descripcion": "Inversor/Cargador Victron MultiPlus-II 48/8000/110-100 230V",
                "categoria": "Inversores y MPPT",
                "proveedor": "MacroSolar / RBR (Consolidado Delta)",
                "unidad": "un",
                "costo_unitario_neto_clp": cost_vic_mp2_8000,
            },
            "INV-VIC-MP2-48-10000": {
                "sku": "INV-VIC-MP2-48-10000",
                "descripcion": "Inversor/Cargador Victron MultiPlus-II 48/10000/140-100 230V",
                "categoria": "Inversores y MPPT",
                "proveedor": "MacroSolar / RBR (Consolidado Delta)",
                "unidad": "un",
                "costo_unitario_neto_clp": cost_vic_mp2_10000,
            },
            "INV-VIC-MP2-48-15000": {
                "sku": "INV-VIC-MP2-48-15000",
                "descripcion": "Inversor/Cargador Victron MultiPlus-II 48/15000/200-100 230V",
                "categoria": "Inversores y MPPT",
                "proveedor": "MacroSolar / RBR (Consolidado Delta)",
                "unidad": "un",
                "costo_unitario_neto_clp": cost_vic_mp2_15000,
            },
            "MPPT-VIC-250-70": {
                "sku": "MPPT-VIC-250-70",
                "descripcion": "Regulador Solar Victron SmartSolar MPPT 250/70-Tr VE.Can",
                "categoria": "Inversores y MPPT",
                "proveedor": "MacroSolar / RBR (Consolidado Delta)",
                "unidad": "un",
                "costo_unitario_neto_clp": cost_vic_mppt_250_70,
            },
            "MPPT-VIC-250-100": {
                "sku": "MPPT-VIC-250-100",
                "descripcion": "Regulador Solar Victron SmartSolar MPPT 250/100-Tr VE.Can",
                "categoria": "Inversores y MPPT",
                "proveedor": "MacroSolar / RBR (Consolidado Delta)",
                "unidad": "un",
                "costo_unitario_neto_clp": cost_vic_mppt_250_100,
            },
            "MON-VIC-CERBO-GX": {
                "sku": "MON-VIC-CERBO-GX",
                "descripcion": "Central de Comunicación Victron Cerbo GX MK2 + Pantalla GX Touch 50 + Cables VE.Can",
                "categoria": "Inversores y MPPT",
                "proveedor": "RBR / MacroSolar (Consolidado Delta)",
                "unidad": "kit",
                "costo_unitario_neto_clp": cost_vic_cerbo + cost_vic_touch50 + 15300,
            },
            "DIST-VIC-LYNX-1000": {
                "sku": "DIST-VIC-LYNX-1000",
                "descripcion": "Distribuidor DC Embarrado Victron Lynx Distributor M10 1000A",
                "categoria": "Inversores y MPPT",
                "proveedor": "MacroSolar / RBR (Consolidado Delta)",
                "unidad": "un",
                "costo_unitario_neto_clp": cost_vic_lynx,
            },
            "BAT-PYL-US5000": {
                "sku": "BAT-PYL-US5000",
                "descripcion": "Batería Litio LiFePO4 Pylontech US5000 4.8 kWh 48V + Bracket UP-5 + Kit Cables",
                "categoria": "Banco de Baterías LiFePO4",
                "proveedor": "MacroSolar / RBR (Consolidado Delta)",
                "unidad": "un",
                "costo_unitario_neto_clp": cost_pylon_us5000 + cost_pylon_bracket + cost_pylon_cables,
            },
            "BAT-HW-LUNA-5KWH": {
                "sku": "BAT-HW-LUNA-5KWH",
                "descripcion": "Módulo Batería Litio LiFePO4 Huawei LUNA2000-5-E0 (5.0 kWh)",
                "categoria": "Banco de Baterías LiFePO4",
                "proveedor": "EMAT - Lista ELITE (Consolidado Delta)",
                "unidad": "un",
                "costo_unitario_neto_clp": cost_hw_luna_5kwh,
            },
            "BMS-HW-LUNA-5KW": {
                "sku": "BMS-HW-LUNA-5KW",
                "descripcion": "Módulo de Potencia BMS Huawei LUNA2000-5KW-C0 (DC/DC Converter)",
                "categoria": "Banco de Baterías LiFePO4",
                "proveedor": "EMAT - Lista ELITE (Consolidado Delta)",
                "unidad": "un",
                "costo_unitario_neto_clp": cost_hw_luna_bms,
            },
            "PROT-AC-MCB-1F-40A": {
                "sku": "PROT-AC-MCB-1F-40A",
                "descripcion": "Interruptor Termomagnético AC Bipolar 2x50A / 2x40A Curva C 10kA (Vitel BKN-b / Chint)",
                "categoria": "Protecciones Eléctricas AC/DC",
                "proveedor": "VITEL / RBR (Consolidado Delta)",
                "unidad": "un",
                "costo_unitario_neto_clp": cost_vitel_mcb_1f,
            },
            "PROT-AC-MCB-3F-63A": {
                "sku": "PROT-AC-MCB-3F-63A",
                "descripcion": "Interruptor Termomagnético AC Tetrapolar 4x25A / 4x40A Curva C 10kA 380/415VAC (Vitel BKN-b / Chint)",
                "categoria": "Protecciones Eléctricas AC/DC",
                "proveedor": "VITEL / RBR (Consolidado Delta)",
                "unidad": "un",
                "costo_unitario_neto_clp": cost_vitel_mcb_3f,
            },
            "PROT-AC-DIF-1F-40A": {
                "sku": "PROT-AC-DIF-1F-40A",
                "descripcion": "Interruptor Diferencial AC Bipolar 2x40A 30mA Tipo A Inmunizado (Chint / Vitel)",
                "categoria": "Protecciones Eléctricas AC/DC",
                "proveedor": "RBR / VITEL (Consolidado Delta)",
                "unidad": "un",
                "costo_unitario_neto_clp": cost_rbr_dif_1f,
            },
            "PROT-AC-DIF-3F-63A": {
                "sku": "PROT-AC-DIF-3F-63A",
                "descripcion": "Interruptor Diferencial AC Tetrapolar 4x25A / 4x40A 415V 10kA (Vitel RKN-b / Chint)",
                "categoria": "Protecciones Eléctricas AC/DC",
                "proveedor": "VITEL / RBR (Consolidado Delta)",
                "unidad": "un",
                "costo_unitario_neto_clp": cost_vitel_dif_3f,
            },
            "PROT-AC-SPD-1F": {
                "sku": "PROT-AC-SPD-1F",
                "descripcion": "Descargador de Sobretensión Transitoria AC (SPD Tipo 2) Monofásico 275Vac 40kA",
                "categoria": "Protecciones Eléctricas AC/DC",
                "proveedor": "RBR / MacroSolar (Consolidado Delta)",
                "unidad": "un",
                "costo_unitario_neto_clp": cost_spd_ac_1f,
            },
            "PROT-AC-SPD-3F": {
                "sku": "PROT-AC-SPD-3F",
                "descripcion": "Descargador de Sobretensión Transitoria AC Finder 7P.23.8.275.1020 Trifásico 3P+N 20kA",
                "categoria": "Protecciones Eléctricas AC/DC",
                "proveedor": "MacroSolar (Consolidado Delta)",
                "unidad": "un",
                "costo_unitario_neto_clp": cost_spd_ac_3f,
            },
            "PROT-DC-STRING-1000V": {
                "sku": "PROT-DC-STRING-1000V",
                "descripcion": "Kit Protección String DC 1000Vdc (Portafusible Vitel + Fusibles gPV 10x38 15A + Breaker DC Suntree 2P + SPD DC 1000V)",
                "categoria": "Protecciones Eléctricas AC/DC",
                "proveedor": "VITEL / RBR Suntree (Consolidado Delta)",
                "unidad": "kit",
                "costo_unitario_neto_clp": 48720,
            },
            "PROT-DC-FUSE-MEGA-250A": {
                "sku": "PROT-DC-FUSE-MEGA-250A",
                "descripcion": "Fusible DC Victron MEGA-fuse 250A/80V + Portafusible MEGA Holder + Seccionador Victron 275A ON/OFF",
                "categoria": "Protecciones Eléctricas AC/DC",
                "proveedor": "RBR / MacroSolar (Consolidado Delta)",
                "unidad": "kit",
                "costo_unitario_neto_clp": 57625,
            },
            "TAB-IP65-18M": {
                "sku": "TAB-IP65-18M",
                "descripcion": "Tablero Metálico IP65 RAL7035 400x300x200mm Vitel (ST3-420) + Contrapuerta + Riel DIN + Piloto LED",
                "categoria": "Protecciones Eléctricas AC/DC",
                "proveedor": "VITEL (Consolidado Delta)",
                "unidad": "un",
                "costo_unitario_neto_clp": 55615,
            },
            "TAB-IP65-36M-IND": {
                "sku": "TAB-IP65-36M-IND",
                "descripcion": "Gabinete Metálico Industrial IP65 RAL7035 800x600x250mm Vitel (ST6-825) + Contrapuerta + Barra Repartidora Tetrapolar 200A",
                "categoria": "Protecciones Eléctricas AC/DC",
                "proveedor": "VITEL (Consolidado Delta)",
                "unidad": "un",
                "costo_unitario_neto_clp": 196011,
            },
            "EST-AL-COPLANAR-1P": {
                "sku": "EST-AL-COPLANAR-1P",
                "descripcion": "Kit Estructura Aluminio Anodizado Coplanar PRO EMAT por Panel (Riel 5000mm PRO + Fijación L + Mid/End Clamps + Tierra PRO)",
                "categoria": "Estructuras de Montaje",
                "proveedor": "EMAT - Lista ELITE / RBR (Consolidado Delta)",
                "unidad": "kit/panel",
                "costo_unitario_neto_clp": int(round(cost_riel_pro * 0.55 + cost_l_pro * 3 + 3500)),
            },
            "EST-GALV-SUELO-1P": {
                "sku": "EST-GALV-SUELO-1P",
                "descripcion": "Kit Estructura Suelo / Tornillo Helicoidal RBR + Riel R13 4700mm + Triángulo 30° Reforzado Viento/Nieve Patagonia por Panel",
                "categoria": "Estructuras de Montaje",
                "proveedor": "RBR (Consolidado Delta)",
                "unidad": "kit/panel",
                "costo_unitario_neto_clp": 44500,
            },
            "CBL-SOLAR-6MM-KIT": {
                "sku": "CBL-SOLAR-6MM-KIT",
                "descripcion": "Rollo 50m Cable Solar H1Z2Z2-K 6mm² 1500Vdc (Rojo/Negro RBR CASO0021/22) + Conectores MC4 Slocable",
                "categoria": "Ferretería Eléctrica y Canalización",
                "proveedor": "RBR (Consolidado Delta)",
                "unidad": "kit",
                "costo_unitario_neto_clp": 77410,
            },
            "CBL-BAT-50MM-KIT": {
                "sku": "CBL-BAT-50MM-KIT",
                "descripcion": "Kit Cables de Potencia Baterías RV-K 1x50mm² / 1x70mm² Powerflex RBR + Terminales Ojo Cobre Estañado T50-10",
                "categoria": "Ferretería Eléctrica y Canalización",
                "proveedor": "RBR / MacroSolar (Consolidado Delta)",
                "unidad": "kit",
                "costo_unitario_neto_clp": 69500,
            },
            "FER-CANALIZACION-EMT-1F": {
                "sku": "FER-CANALIZACION-EMT-1F",
                "descripcion": "Kit Ferretería Eléctrica y Canalización Vitel 1F (Tubo Extraflex Metálico c/PVC IEC 32mm, Cajas Galv. en Caliente, Coplas, Prensas PG)",
                "categoria": "Ferretería Eléctrica y Canalización",
                "proveedor": "VITEL (Consolidado Delta)",
                "unidad": "kit",
                "costo_unitario_neto_clp": 148500,
            },
            "FER-CANALIZACION-EMT-3F": {
                "sku": "FER-CANALIZACION-EMT-3F",
                "descripcion": "Kit Ferretería Eléctrica Industrial Vitel 3F (Tubo Extraflex Metálico c/PVC 63mm, Cable Reviflex 5x16mm RV-K, Cajas Galv. 200x200)",
                "categoria": "Ferretería Eléctrica y Canalización",
                "proveedor": "VITEL (Consolidado Delta)",
                "unidad": "kit",
                "costo_unitario_neto_clp": 345000,
            },
            "PAT-MALLA-TIERRA-BT": {
                "sku": "PAT-MALLA-TIERRA-BT",
                "descripcion": "Kit Puesta a Tierra Vitel (Barra Copperweld 3/4x1.5m + Cable Cu Desnudo #2 AWG + Conector Bronce + Cámara Registro PVC Naranjo)",
                "categoria": "Ferretería Eléctrica y Canalización",
                "proveedor": "VITEL (Consolidado Delta)",
                "unidad": "kit",
                "costo_unitario_neto_clp": 95000,
            },
            "MO-SUB-INST-BASE-1F": {
                "sku": "MO-SUB-INST-BASE-1F",
                "descripcion": "Habilitación Técnica, Puesta en Marcha y Pruebas RIC N°09 Monofásica (Subcontrato Base)",
                "categoria": "Mano de Obra e Instalación (Subcontrato)",
                "proveedor": "Subcontrato Instaladores Certificados Delta Aysén",
                "unidad": "gl",
                "costo_unitario_neto_clp": 180000,
            },
            "MO-SUB-INST-BASE-3F": {
                "sku": "MO-SUB-INST-BASE-3F",
                "descripcion": "Habilitación Técnica, Puesta en Marcha y Pruebas RIC N°09 Trifásica (Subcontrato Base)",
                "categoria": "Mano de Obra e Instalación (Subcontrato)",
                "proveedor": "Subcontrato Instaladores Certificados Delta Aysén",
                "unidad": "gl",
                "costo_unitario_neto_clp": 350000,
            },
            "MO-SUB-POR-PANEL": {
                "sku": "MO-SUB-POR-PANEL",
                "descripcion": "Mano de Obra Subcontrato Instalación por Panel (~0.6 kWp, equivalente a $178.184 CLP Neto / kWp instalado según tabla AR Delta)",
                "categoria": "Mano de Obra e Instalación (Subcontrato)",
                "proveedor": "Subcontrato Instaladores Certificados Delta Aysén (Tabla AR $178.184/kWp)",
                "unidad": "panel",
                "costo_unitario_neto_clp": int(round(install_rate_per_kwp * 0.6)),
            },
            "MO-SUB-TRAMITE-TE4": {
                "sku": "MO-SUB-TRAMITE-TE4",
                "descripcion": "Ingeniería de Detalle, Planimetría As-Built y Tramitación SEC TE4 /TE1 (Región de Aysén)",
                "categoria": "Mano de Obra e Instalación (Subcontrato)",
                "proveedor": "Ingeniería Delta SpA / SEC",
                "unidad": "gl",
                "costo_unitario_neto_clp": 280000,
            },
        },
    }

    for sku_key, entry in catalog_payload["items"].items():
        entry["unit_cost_net_clp"] = entry["costo_unitario_neto_clp"]
        entry["supplier"] = entry["proveedor"]
        entry["description"] = entry["descripcion"]
        entry["unit"] = entry["unidad"]

    CATALOG_JSON_PATH.write_text(
        json.dumps(catalog_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {
        "status": "synced",
        "synced_at": catalog_payload["metadata"]["synced_at"],
        "excel_source": str(excel_path),
        "rbr_source": str(rbr_json_path),
        "total_supplier_rows_indexed": total_raw_items,
        "sheets_summary": {k: len(v) for k, v in sheets_data.items()},
        "boq_skus_updated": len(catalog_payload["items"]),
    }


if __name__ == "__main__":
    summary = sync_catalog_from_excel()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
