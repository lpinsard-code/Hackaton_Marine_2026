from __future__ import annotations

import argparse
import csv
import json
import math
import mimetypes
import socket
import unicodedata
from datetime import UTC, datetime
from functools import lru_cache
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent
GENERALISATION_DIR = ROOT / "Generalisation"
if not GENERALISATION_DIR.exists():
    for child in ROOT.iterdir():
        normalized = unicodedata.normalize("NFKD", child.name)
        ascii_name = normalized.encode("ascii", "ignore").decode("ascii").lower()
        if child.is_dir() and ascii_name == "generalisation":
            GENERALISATION_DIR = child
            break

OUTPUTS_DIR = GENERALISATION_DIR / "outputs_priorisation_v2"
RAW_DIR = GENERALISATION_DIR / "data" / "raw"

DETECTIONS_CSV = OUTPUTS_DIR / "scored_detections_v2.csv"
ZONE_SUMMARY_CSV = OUTPUTS_DIR / "zone_summary_v2.csv"
DAILY_SUMMARY_CSV = OUTPUTS_DIR / "daily_zone_summary_v2.csv"
MILITARY_ZONES_CSV = RAW_DIR / "military_zones.csv"
LOGO_DIR = ROOT / "logo officielle marine nationale"
LOGO_FILE = next(
    (
        path
        for path in LOGO_DIR.glob("*")
        if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".svg", ".webp"}
    ),
    None,
)


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if any(marker in text for marker in ("\u00c3", "\u00c2", "\u00e2", "\u00f0")):
        try:
            return text.encode("latin1").decode("utf-8")
        except UnicodeError:
            return text
    return text


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        number = float(str(value).replace(",", "."))
        if math.isnan(number) or math.isinf(number):
            return default
        return number
    except (TypeError, ValueError):
        return default


def to_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ""):
            return default
        return int(float(str(value).replace(",", ".")))
    except (TypeError, ValueError):
        return default


def to_bool(value: Any) -> bool:
    return clean_text(value).lower() in {"true", "1", "yes", "oui", "vrai"}


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    encodings = ("utf-8-sig", "utf-8", "cp1252", "latin1")
    last_error: Exception | None = None
    for encoding in encodings:
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                return [
                    {clean_text(key): clean_text(value) for key, value in row.items()}
                    for row in csv.DictReader(handle)
                ]
        except UnicodeError as exc:
            last_error = exc
    raise RuntimeError(f"Impossible de lire {path}: {last_error}")


def parse_coordinate_pair(raw: str) -> tuple[float, float] | None:
    if not raw:
        return None
    parts = [part.strip() for part in raw.split(",")]
    if len(parts) != 2:
        return None
    lat = to_float(parts[0], default=float("nan"))
    lon = to_float(parts[1], default=float("nan"))
    if math.isnan(lat) or math.isnan(lon):
        return None
    return lat, lon


def normalize_detection(row: dict[str, str]) -> dict[str, Any]:
    return {
        "detection_id": row.get("detection_id", ""),
        "image_id": row.get("image_id", ""),
        "file_name": row.get("file_name", ""),
        "image_datetime": row.get("image_datetime", ""),
        "date_only": row.get("date_only", ""),
        "category": row.get("category", "Inconnu"),
        "vessel_group": row.get("vessel_group", "unknown"),
        "confidence": to_float(row.get("confidence")),
        "adjusted_confidence": to_float(row.get("adjusted_confidence")),
        "cloud_cover": to_float(row.get("cloud_cover")),
        "quality_score": to_int(row.get("quality_score")),
        "quality_level": row.get("quality_level", "Inconnue"),
        "bbox": row.get("bbox", ""),
        "bbox_ratio": to_float(row.get("bbox_ratio")),
        "bbox_area_pct": to_float(row.get("bbox_area_pct")),
        "bbox_inside_image": to_bool(row.get("bbox_inside_image")),
        "bbox_plausibility": row.get("bbox_plausibility", ""),
        "classification_uncertainty_flag": to_bool(row.get("classification_uncertainty_flag")),
        "zone_name": row.get("zone_name", "Zone inconnue"),
        "country": row.get("country", "Inconnu"),
        "image_lat": to_float(row.get("image_lat")),
        "image_lon": to_float(row.get("image_lon")),
        "detection_risk_level": row.get("detection_risk_level", ""),
        "mil_risk_level": row.get("mil_risk_level", ""),
        "effective_risk_level": row.get("effective_risk_level", "Unknown"),
        "in_sensitive_military_zone": to_bool(row.get("in_sensitive_military_zone")),
        "mil_zone_active": to_bool(row.get("mil_zone_active")),
        "base_type": row.get("base_type", ""),
        "mil_density": to_float(row.get("mil_density")),
        "nearest_sensitive_zone": row.get("nearest_sensitive_zone", ""),
        "nearest_sensitive_zone_distance_km": to_float(
            row.get("nearest_sensitive_zone_distance_km")
        ),
        "near_sensitive_zone_25km": to_bool(row.get("near_sensitive_zone_25km")),
        "same_image_detection_count": to_int(row.get("same_image_detection_count")),
        "same_image_combat_count": to_int(row.get("same_image_combat_count")),
        "same_image_civilian_count": to_int(row.get("same_image_civilian_count")),
        "same_zone_day_detection_count": to_int(row.get("same_zone_day_detection_count")),
        "same_zone_day_combat_count": to_int(row.get("same_zone_day_combat_count")),
        "same_zone_day_civilian_count": to_int(row.get("same_zone_day_civilian_count")),
        "possible_co_presence_proxy": to_bool(row.get("possible_co_presence_proxy")),
        "dense_activity_same_day": to_bool(row.get("dense_activity_same_day")),
        "zone_observation_days": to_int(row.get("zone_observation_days")),
        "zone_observation_span_days": to_int(row.get("zone_observation_span_days")),
        "score_vessel": to_int(row.get("score_vessel")),
        "score_geo": to_int(row.get("score_geo")),
        "score_context": to_int(row.get("score_context")),
        "score_confidence": to_int(row.get("score_confidence")),
        "score_anomaly": to_int(row.get("score_anomaly")),
        "priority_score": to_int(row.get("priority_score")),
        "alert_level": row.get("alert_level", "Non qualifie"),
        "requires_human_review": to_bool(row.get("requires_human_review")),
        "review_reasons": row.get("review_reasons", ""),
        "scoring_version": row.get("scoring_version", ""),
    }


def normalize_zone_summary(row: dict[str, str]) -> dict[str, Any]:
    return {
        "zone_name": row.get("zone_name", "Zone inconnue"),
        "detections": to_int(row.get("detections")),
        "human_reviews": to_int(row.get("human_reviews")),
        "combat_detections": to_int(row.get("combat_detections")),
        "support_detections": to_int(row.get("support_detections")),
        "civilian_detections": to_int(row.get("civilian_detections")),
        "max_priority_score": to_int(row.get("max_priority_score")),
        "avg_priority_score": to_float(row.get("avg_priority_score")),
        "avg_quality_score": to_float(row.get("avg_quality_score")),
        "max_alert_level": row.get("max_alert_level", ""),
        "effective_risk_level": row.get("effective_risk_level", ""),
        "image_lat": to_float(row.get("image_lat")),
        "image_lon": to_float(row.get("image_lon")),
        "first_observation": row.get("first_observation", ""),
        "last_observation": row.get("last_observation", ""),
        "observation_days": to_int(row.get("observation_days")),
        "possible_co_presence_count": to_int(row.get("possible_co_presence_count")),
    }


def normalize_daily_summary(row: dict[str, str]) -> dict[str, Any]:
    return {
        "date_only": row.get("date_only", ""),
        "zone_name": row.get("zone_name", "Zone inconnue"),
        "detections": to_int(row.get("detections")),
        "human_reviews": to_int(row.get("human_reviews")),
        "max_priority_score": to_int(row.get("max_priority_score")),
        "avg_priority_score": to_float(row.get("avg_priority_score")),
        "combat_detections": to_int(row.get("combat_detections")),
        "support_detections": to_int(row.get("support_detections")),
        "civilian_detections": to_int(row.get("civilian_detections")),
        "possible_co_presence": to_bool(row.get("possible_co_presence")),
    }


def normalize_military_zone(row: dict[str, str]) -> dict[str, Any]:
    coordinates = parse_coordinate_pair(row.get("coordinates", ""))
    lat, lon = coordinates if coordinates else (0.0, 0.0)
    return {
        "zone_id": row.get("zone_id", ""),
        "name": row.get("name", ""),
        "coordinates": row.get("coordinates", ""),
        "country": row.get("country", ""),
        "risk_level": row.get("risk_level", "Unknown"),
        "description": row.get("description", ""),
        "base_name": row.get("base_name", ""),
        "active": to_bool(row.get("active")),
        "lat": lat,
        "lon": lon,
    }


@lru_cache(maxsize=1)
def load_payload() -> dict[str, Any]:
    detections = [normalize_detection(row) for row in read_csv(DETECTIONS_CSV)]
    zone_summary = [normalize_zone_summary(row) for row in read_csv(ZONE_SUMMARY_CSV)]
    daily_summary = [normalize_daily_summary(row) for row in read_csv(DAILY_SUMMARY_CSV)]
    military_zones = [normalize_military_zone(row) for row in read_csv(MILITARY_ZONES_CSV)]

    detections = [
        detection
        for detection in detections
        if -90 <= detection["image_lat"] <= 90 and -180 <= detection["image_lon"] <= 180
    ]

    return {
        "detections": detections,
        "zoneSummary": zone_summary,
        "dailySummary": daily_summary,
        "militaryZones": military_zones,
        "sourceFiles": {
            "detections": str(DETECTIONS_CSV.relative_to(ROOT)),
            "zoneSummary": str(ZONE_SUMMARY_CSV.relative_to(ROOT)),
            "dailySummary": str(DAILY_SUMMARY_CSV.relative_to(ROOT)),
            "militaryZones": str(MILITARY_ZONES_CSV.relative_to(ROOT)),
        },
        "generatedAt": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }


HTML_TEMPLATE = r"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Centre de priorisation maritime</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
  <script src="https://unpkg.com/lucide@0.468.0/dist/umd/lucide.min.js"></script>
  <style>
    :root {
      --bg: #f6f8fc;
      --panel: #ffffff;
      --ink: #0B1F33;
      --muted: #65718a;
      --line: #e2e8f0;
      --navy: #071d3a;
      --navy-2: #0e356a;
      --steel: #2E5E7E;
      --teal: #2C7A7B;
      --green: #2f855a;
      --amber: #f5bd42;
      --orange: #D97706;
      --red: #B91C1C;
      --blue: #2E5E7E;
      --text-gray: #334155;
      --shadow: 0 14px 34px rgba(15, 23, 42, 0.08);
      --card-shadow: 0 10px 28px rgba(15, 23, 42, 0.07);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      letter-spacing: 0;
    }
    button, input, select {
      font: inherit;
    }
    .app-shell {
      min-height: 100vh;
      display: grid;
      grid-template-columns: 312px minmax(0, 1fr);
      background: var(--bg);
    }
    .sidebar {
      background:
        radial-gradient(circle at 20% 0%, rgba(46, 94, 126, 0.42), transparent 32%),
        linear-gradient(180deg, #061934 0%, #0a2b5a 54%, #082349 100%);
      border-right: 1px solid rgba(255, 255, 255, 0.12);
      box-shadow: 10px 0 30px rgba(7, 29, 58, 0.18);
      color: #eaf2ff;
      padding: 26px 20px 24px;
      overflow-y: auto;
      position: sticky;
      top: 0;
      height: 100vh;
    }
    .brand {
      display: block;
      padding: 0 0 22px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.16);
      margin-bottom: 22px;
    }
    .mn-lockup {
      align-items: center;
      display: flex;
      gap: 12px;
      margin-bottom: 26px;
    }
    .marine-logo {
      display: block;
      height: auto;
      max-width: 210px;
      width: 190px;
    }
    .brand h1 {
      color: #fff;
      font-size: 19px;
      font-weight: 850;
      line-height: 1.2;
      margin: 0 0 8px;
    }
    .brand p {
      color: #c4d3ea;
      margin: 3px 0 0;
      font-size: 14px;
      line-height: 1.4;
    }
    .filter-block {
      border-bottom: 1px solid rgba(255, 255, 255, 0.1);
      padding: 18px 0;
    }
    .filter-title {
      align-items: center;
      color: #e8eefc;
      display: flex;
      font-size: 11px;
      font-weight: 850;
      justify-content: space-between;
      margin-bottom: 10px;
      text-transform: uppercase;
    }
    label {
      color: #edf4ff;
      display: block;
      font-size: 12px;
      font-weight: 700;
      margin-bottom: 7px;
    }
    .input, select {
      background: rgba(6, 22, 48, 0.62);
      border: 1px solid rgba(170, 194, 230, 0.25);
      border-radius: 8px;
      color: #f8fbff;
      min-height: 44px;
      padding: 10px 12px;
      width: 100%;
    }
    .input::placeholder {
      color: #a9b9d1;
    }
    .search-field {
      position: relative;
    }
    .search-field .input {
      padding-right: 42px;
    }
    .search-field i {
      color: #b8c7df;
      height: 20px;
      position: absolute;
      right: 13px;
      top: 50%;
      transform: translateY(-50%);
      width: 20px;
    }
    .input:focus, select:focus {
      border-color: #8bb9ff;
      outline: 2px solid rgba(139, 185, 255, 0.22);
    }
    .range-row {
      align-items: center;
      display: grid;
      gap: 10px;
      grid-template-columns: 1fr 44px;
    }
    input[type="range"] {
      accent-color: #79a8f4;
      width: 100%;
    }
    .range-value {
      background: rgba(6, 22, 48, 0.62);
      border: 1px solid rgba(170, 194, 230, 0.25);
      border-radius: 8px;
      color: #fff;
      font-weight: 800;
      min-height: 44px;
      padding: 11px 7px;
      text-align: center;
    }
    .date-grid {
      display: grid;
      gap: 8px;
      grid-template-columns: 1fr 1fr;
    }
    .check-list {
      display: grid;
      gap: 7px;
      max-height: 170px;
      overflow: auto;
      padding-right: 3px;
    }
    .check-row, .toggle-row {
      align-items: center;
      display: grid;
      gap: 8px;
      grid-template-columns: 18px minmax(0, 1fr) auto;
      line-height: 1.2;
    }
    .check-row label, .toggle-row label {
      color: #edf4ff;
      font-size: 13px;
      font-weight: 600;
      margin: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .check-row span {
      color: #b7c7df;
      font-size: 12px;
    }
    .toggle-row {
      grid-template-columns: 18px minmax(0, 1fr);
      margin: 9px 0;
    }
    input[type="checkbox"] {
      accent-color: #6ea0e8;
      height: 16px;
      margin: 0;
      width: 16px;
    }
    .button-row {
      display: grid;
      gap: 8px;
      grid-template-columns: 1fr 1fr;
      margin-top: 12px;
    }
    .button {
      align-items: center;
      background: #224f8c;
      border: 1px solid #3c6fac;
      border-radius: 8px;
      color: #fff;
      cursor: pointer;
      display: inline-flex;
      font-weight: 800;
      justify-content: center;
      min-height: 38px;
      padding: 8px 12px;
      text-decoration: none;
    }
    .button.secondary {
      background: rgba(6, 22, 48, 0.34);
      border-color: rgba(170, 194, 230, 0.28);
      color: #edf4ff;
    }
    .button.active {
      background: var(--orange);
      border-color: var(--orange);
      color: #fff;
    }
    details.advanced-filters {
      border-bottom: 1px solid rgba(255, 255, 255, 0.1);
      padding: 14px 0;
    }
    details.advanced-filters summary {
      color: var(--text-gray);
      color: #edf4ff;
      cursor: pointer;
      font-size: 12px;
      font-weight: 850;
      list-style: none;
      text-transform: uppercase;
    }
    details.advanced-filters summary::-webkit-details-marker {
      display: none;
    }
    details.advanced-filters summary::after {
      content: "+";
      float: right;
    }
    details.advanced-filters[open] summary::after {
      content: "-";
    }
    .advanced-filters .filter-block:last-child {
      border-bottom: 0;
      padding-bottom: 0;
    }
    .sidebar-footer {
      align-items: center;
      color: #c6d5ec;
      display: flex;
      justify-content: space-between;
      padding-top: 18px;
    }
    .sidebar-footer i {
      height: 22px;
      width: 22px;
    }
    .button:disabled {
      cursor: wait;
      opacity: 0.65;
    }
    main {
      min-width: 0;
      padding: 42px 48px 32px;
    }
    .topbar {
      align-items: center;
      display: flex;
      gap: 12px;
      justify-content: space-between;
      margin-bottom: 14px;
    }
    .topbar h2 {
      color: var(--navy);
      font-size: 31px;
      font-weight: 900;
      line-height: 1.08;
      margin: 0;
    }
    .source-line {
      color: var(--muted);
      font-size: 15px;
      margin-top: 8px;
    }
    .data-line {
      align-items: center;
      color: var(--muted);
      display: flex;
      gap: 8px;
      font-size: 13px;
      font-weight: 700;
      margin-top: 14px;
    }
    .data-line svg {
      height: 18px;
      width: 18px;
    }
    .toolbar {
      align-items: center;
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      justify-content: flex-end;
    }
    .status-pill {
      background: #fff;
      border: 1px solid var(--line);
      border-radius: 24px;
      box-shadow: 0 8px 20px rgba(15, 23, 42, 0.04);
      color: var(--navy);
      display: inline-flex;
      align-items: center;
      gap: 10px;
      font-size: 14px;
      font-weight: 850;
      padding: 12px 18px;
    }
    .status-pill svg {
      background: var(--navy);
      border-radius: 999px;
      color: #fff;
      height: 24px;
      padding: 5px;
      width: 24px;
    }
    .kpis {
      display: grid;
      gap: 18px;
      grid-template-columns: repeat(6, minmax(110px, 1fr));
      margin: 22px 0 24px;
    }
    .kpi {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 12px;
      box-shadow: var(--card-shadow);
      min-height: 158px;
      padding: 22px 22px 18px;
    }
    .kpi-top {
      align-items: center;
      display: flex;
      gap: 14px;
      min-height: 38px;
    }
    .kpi-icon {
      color: var(--navy);
      display: inline-flex;
      flex: 0 0 auto;
    }
    .kpi-icon svg {
      height: 34px;
      stroke-width: 2.4;
      width: 34px;
    }
    .kpi .label {
      color: #273650;
      font-size: 12px;
      font-weight: 900;
      line-height: 1.2;
      text-transform: uppercase;
    }
    .kpi .value {
      color: var(--navy);
      font-size: 41px;
      font-weight: 850;
      margin-top: 24px;
    }
    .kpi .sub {
      color: var(--muted);
      font-size: 12px;
      margin-top: 4px;
    }
    .kpi-meter {
      background: #e6ebf2;
      border-radius: 999px;
      height: 5px;
      margin-top: 18px;
      overflow: hidden;
      width: 68%;
    }
    .kpi-meter span {
      background: var(--navy);
      display: block;
      height: 100%;
      width: 58%;
    }
    .work-grid {
      display: grid;
      gap: 14px;
      grid-template-columns: minmax(0, 1.65fr) minmax(300px, 0.85fr);
    }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 12px;
      box-shadow: var(--shadow);
      min-width: 0;
    }
    .panel-header {
      align-items: center;
      border-bottom: 1px solid var(--line);
      display: flex;
      gap: 10px;
      justify-content: space-between;
      min-height: 52px;
      padding: 16px 20px;
    }
    .panel-title {
      align-items: center;
      color: var(--navy);
      display: inline-flex;
      gap: 10px;
      font-size: 15px;
      font-weight: 850;
      margin: 0;
      text-transform: uppercase;
    }
    .panel-title svg {
      height: 20px;
      width: 20px;
    }
    .panel-body {
      padding: 20px;
    }
    .briefing {
      border-left: 4px solid var(--red);
      margin-bottom: 20px;
    }
    .briefing-text {
      color: var(--text-gray);
      font-size: 15px;
      line-height: 1.55;
      margin: 0;
    }
    #map {
      background: #dfe7ec;
      border-radius: 0 0 12px 12px;
      height: 472px;
      min-height: 430px;
      width: 100%;
    }
    .map-fallback {
      align-items: center;
      color: var(--muted);
      display: grid;
      font-weight: 700;
      height: 100%;
      justify-items: center;
      padding: 24px;
      text-align: center;
    }
    .legend {
      align-items: center;
      display: flex;
      flex-wrap: wrap;
      gap: 8px 12px;
    }
    .legend-item {
      align-items: center;
      color: #536075;
      display: inline-flex;
      font-size: 12px;
      gap: 6px;
    }
    .swatch {
      border: 1px solid rgba(0, 0, 0, 0.14);
      border-radius: 999px;
      display: inline-block;
      height: 12px;
      width: 12px;
    }
    .detail-grid {
      display: grid;
      gap: 0;
      grid-template-columns: 1fr 1fr;
      border-bottom: 1px solid var(--line);
    }
    .detail-item {
      border-bottom: 1px solid var(--line);
      padding: 16px 18px;
    }
    .detail-item:nth-child(odd) {
      border-right: 1px solid var(--line);
    }
    .detail-item strong {
      display: block;
      font-size: 12px;
      color: var(--muted);
      margin-bottom: 3px;
    }
    .detail-value {
      color: var(--navy);
      font-size: 16px;
      font-weight: 800;
      line-height: 1.3;
    }
    .detail-metrics {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      border-bottom: 1px solid var(--line);
      margin-bottom: 4px;
    }
    .metric-item {
      border-right: 1px solid var(--line);
      padding: 18px;
    }
    .metric-item:last-child {
      border-right: 0;
    }
    .metric-label {
      color: var(--muted);
      display: block;
      font-size: 12px;
      font-weight: 850;
      margin-bottom: 8px;
    }
    .metric-value {
      color: var(--navy);
      font-size: 24px;
      font-weight: 900;
    }
    .metric-value.red { color: var(--red); }
    .score-stack {
      display: grid;
      gap: 7px;
      margin-top: 10px;
    }
    .recommendation {
      background: #fff8f8;
      border: 1px solid #f3c9c9;
      border-left: 4px solid var(--red);
      border-radius: 8px;
      margin: 20px 0;
      padding: 18px;
    }
    .recommendation strong {
      display: block;
      font-size: 12px;
      color: var(--muted);
      margin-bottom: 4px;
      text-transform: uppercase;
    }
    .recommendation span {
      color: var(--navy);
      font-size: 20px;
      font-weight: 850;
    }
    .recommendation-row {
      align-items: flex-start;
      display: grid;
      gap: 12px;
      grid-template-columns: 28px 1fr;
    }
    .recommendation-row svg {
      color: var(--red);
      height: 28px;
      width: 28px;
    }
    .recommendation p {
      color: var(--text-gray);
      font-size: 13px;
      line-height: 1.35;
      margin: 4px 0 0;
    }
    .why-list {
      display: grid;
      gap: 7px;
      margin-top: 8px;
    }
    .why-item {
      align-items: center;
      background: #fff;
      border: 1px solid #E2E8F0;
      border-radius: 8px;
      display: flex;
      justify-content: space-between;
      padding: 8px 10px;
    }
    .why-item strong {
      color: var(--navy);
      font-size: 13px;
      margin-right: 10px;
    }
    .score-line {
      display: grid;
      gap: 8px;
      grid-template-columns: 92px 1fr 34px;
      align-items: center;
      font-size: 12px;
    }
    .meter {
      background: #edf0f4;
      border-radius: 999px;
      height: 8px;
      overflow: hidden;
    }
    .meter span {
      background: var(--teal);
      display: block;
      height: 100%;
      width: 0;
    }
    .charts {
      display: grid;
      gap: 14px;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      margin-top: 14px;
    }
    .bar-list {
      display: grid;
      gap: 9px;
    }
    .bar-row {
      display: grid;
      gap: 8px;
      grid-template-columns: minmax(92px, 1fr) 2fr 44px;
      align-items: center;
      font-size: 12px;
    }
    .bar-label {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .bar-track {
      background: #edf0f4;
      border-radius: 999px;
      height: 9px;
      overflow: hidden;
    }
    .bar-fill {
      background: var(--teal);
      height: 100%;
      width: 0;
    }
    .timeline {
      height: 186px;
      width: 100%;
    }
    .timeline text {
      fill: var(--muted);
      font-size: 11px;
    }
    .table-panel {
      margin-top: 14px;
    }
    .table-wrap {
      max-height: 420px;
      overflow: auto;
    }
    table {
      border-collapse: collapse;
      font-size: 12px;
      min-width: 980px;
      width: 100%;
    }
    th, td {
      border-bottom: 1px solid #edf0f4;
      padding: 9px 10px;
      text-align: left;
      vertical-align: top;
    }
    th {
      background: #f7f9fb;
      color: #405064;
      font-size: 11px;
      position: sticky;
      text-transform: uppercase;
      top: 0;
      z-index: 1;
    }
    td .mini-button {
      background: #fff;
      border: 1px solid #cfd7e2;
      border-radius: 7px;
      color: #243241;
      cursor: pointer;
      font-size: 12px;
      font-weight: 800;
      min-height: 28px;
      padding: 4px 8px;
    }
    .badge {
      border-radius: 999px;
      display: inline-flex;
      font-size: 11px;
      font-weight: 850;
      padding: 4px 8px;
      white-space: nowrap;
    }
    .badge.red { background: #fee2e2; color: #991b1b; }
    .badge.orange { background: #ffedd5; color: #9a3412; }
    .badge.amber { background: #fef3c7; color: #92400e; }
    .badge.teal { background: #ccfbf1; color: #115e59; }
    .badge.gray { background: #e5e7eb; color: #374151; }
    .empty-state {
      color: var(--muted);
      font-weight: 800;
      padding: 26px;
      text-align: center;
    }
    .leaflet-popup-content {
      font-family: inherit;
      min-width: 288px;
    }
    .leaflet-popup-content-wrapper {
      border-radius: 12px;
      box-shadow: 0 14px 36px rgba(15, 23, 42, 0.22);
    }
    .popup-title {
      font-weight: 850;
      margin-bottom: 12px;
      color: var(--navy);
    }
    .popup-grid {
      display: grid;
      gap: 5px;
      grid-template-columns: 96px 1fr;
      font-size: 13px;
    }
    .popup-grid span:nth-child(odd) {
      color: #64748b;
      font-weight: 800;
    }
    @media (max-width: 1180px) {
      .app-shell { grid-template-columns: 286px minmax(0, 1fr); }
      .kpis { grid-template-columns: repeat(3, minmax(120px, 1fr)); }
      .work-grid { grid-template-columns: 1fr; }
      .charts { grid-template-columns: 1fr; }
      #map { height: 520px; }
    }
    @media (max-width: 780px) {
      .app-shell { display: block; }
      .sidebar { height: auto; position: static; }
      main { padding: 12px; }
      .topbar { align-items: flex-start; flex-direction: column; }
      .toolbar { justify-content: flex-start; width: 100%; }
      .kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      #map { height: 440px; min-height: 380px; }
      .date-grid, .button-row { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand">
        <div class="mn-lockup">
          <img class="marine-logo" src="/official-logo" alt="Marine Nationale">
        </div>
        <h1>Centre de priorisation maritime</h1>
        <p>Carte, score op&eacute;rationnel et revue analyste</p>
      </div>

      <section class="filter-block">
        <label for="search">Recherche</label>
        <div class="search-field">
          <input class="input" id="search" placeholder="Zone, navire, ID, pays">
          <i data-lucide="search"></i>
        </div>
      </section>

      <section class="filter-block">
        <div class="filter-title">Score op&eacute;rationnel minimum</div>
        <div class="range-row">
          <input id="minScore" type="range" min="0" max="100" value="0">
          <div class="range-value" id="minScoreValue">0</div>
        </div>
      </section>

      <section class="filter-block">
        <div class="filter-title">Dates</div>
        <div class="date-grid">
          <div>
            <label for="dateStart">D&eacute;but</label>
            <input class="input" id="dateStart" type="date">
          </div>
          <div>
            <label for="dateEnd">Fin</label>
            <input class="input" id="dateEnd" type="date">
          </div>
        </div>
      </section>

      <section class="filter-block">
        <div class="filter-title">Alerte</div>
        <div class="check-list" id="alertChecks"></div>
      </section>

      <section class="filter-block">
        <div class="filter-title">Risque</div>
        <div class="check-list" id="riskChecks"></div>
      </section>

      <section class="filter-block">
        <div class="filter-title">Pays</div>
        <div class="check-list" id="countryChecks"></div>
      </section>

      <section class="filter-block">
        <div class="filter-title">Type de navire</div>
        <div class="check-list" id="categoryChecks"></div>
      </section>

      <section class="filter-block">
        <button class="button" id="topPriorities" type="button">Afficher le Top 10 priorit&eacute;s</button>
      </section>

      <details class="advanced-filters">
        <summary>Filtres avanc&eacute;s</summary>

        <section class="filter-block">
          <div class="filter-title">Classe civil/militaire</div>
          <div class="check-list" id="groupChecks"></div>
        </section>

        <section class="filter-block">
          <div class="filter-title">Qualit&eacute;</div>
          <div class="check-list" id="qualityChecks"></div>
        </section>

        <section class="filter-block">
          <div class="filter-title">Contexte</div>
          <div class="toggle-row">
            <input id="humanOnly" type="checkbox">
            <label for="humanOnly">Revue humaine requise</label>
          </div>
          <div class="toggle-row">
            <input id="sensitiveOnly" type="checkbox">
            <label for="sensitiveOnly">Zone militaire sensible</label>
          </div>
          <div class="toggle-row">
            <input id="copresenceOnly" type="checkbox">
            <label for="copresenceOnly">Co-pr&eacute;sence potentielle</label>
          </div>
          <div class="toggle-row">
            <input id="denseOnly" type="checkbox">
            <label for="denseOnly">Activit&eacute; dense</label>
          </div>
        </section>

        <section class="filter-block">
          <label for="mapMode">Couleur carte</label>
          <select id="mapMode">
            <option value="priority">Priorit&eacute;</option>
            <option value="risk">Risque</option>
            <option value="group">Classe navire</option>
          </select>
        </section>

        <section class="filter-block">
          <label for="sortMode">Tri tableau</label>
          <select id="sortMode">
            <option value="priority">Score op&eacute;rationnel</option>
            <option value="date">Date r&eacute;cente</option>
            <option value="confidence">Confiance</option>
            <option value="zone">Zone</option>
          </select>
        </section>
      </details>

      <section class="filter-block">
        <div class="button-row">
          <button class="button secondary" id="resetFilters">R&eacute;initialiser</button>
          <button class="button" id="exportCsv">Exporter CSV</button>
        </div>
      </section>

      <div class="sidebar-footer" aria-hidden="true">
        <i data-lucide="chevron-left"></i>
        <i data-lucide="settings"></i>
        <i data-lucide="circle-help"></i>
      </div>
    </aside>

    <main>
      <div class="topbar">
        <div>
          <h2>Centre de priorisation des observations navales</h2>
          <div class="source-line">Carte, score op&eacute;rationnel et revue analyste</div>
          <div class="data-line"><i data-lucide="clock-3"></i><span id="sourceLine">Chargement des donn&eacute;es</span></div>
        </div>
        <div class="toolbar">
          <span class="status-pill"><i data-lucide="badge-dot"></i><span id="resultStatus">0 observation</span></span>
          <span class="status-pill"><i data-lucide="clipboard-list"></i><span id="reviewStatus">0 revue</span></span>
        </div>
      </div>

      <section class="kpis">
        <div class="kpi">
          <div class="kpi-top"><span class="kpi-icon"><i data-lucide="eye"></i></span><div class="label">&Agrave; examiner</div></div>
          <div class="value" id="kpiImmediate">0</div><div class="sub">score 80-100</div><div class="kpi-meter"><span></span></div>
        </div>
        <div class="kpi">
          <div class="kpi-top"><span class="kpi-icon"><i data-lucide="bell"></i></span><div class="label">Alertes analyste</div></div>
          <div class="value" id="kpiAnalystAlerts">0</div><div class="sub">score 60-79</div><div class="kpi-meter"><span></span></div>
        </div>
        <div class="kpi">
          <div class="kpi-top"><span class="kpi-icon"><i data-lucide="crosshair"></i></span><div class="label">Score max</div></div>
          <div class="value" id="kpiMaxScore">0</div><div class="sub" id="kpiMaxAlert">alerte</div><div class="kpi-meter"><span></span></div>
        </div>
        <div class="kpi">
          <div class="kpi-top"><span class="kpi-icon"><i data-lucide="map-pin"></i></span><div class="label">Zones sensibles touch&eacute;es</div></div>
          <div class="value" id="kpiSensitiveZones">0</div><div class="sub">zones touch&eacute;es</div><div class="kpi-meter"><span></span></div>
        </div>
        <div class="kpi">
          <div class="kpi-top"><span class="kpi-icon"><i data-lucide="ship"></i></span><div class="label">Navires militaires d&eacute;tect&eacute;s</div></div>
          <div class="value" id="kpiMilitary">0</div><div class="sub" id="kpiMilitaryRate">0%</div><div class="kpi-meter"><span></span></div>
        </div>
        <div class="kpi">
          <div class="kpi-top"><span class="kpi-icon"><i data-lucide="shield-check"></i></span><div class="label">Confiance moyenne</div></div>
          <div class="value" id="kpiConfidence">0%</div><div class="sub">observations filtr&eacute;es</div><div class="kpi-meter"><span></span></div>
        </div>
      </section>

      <section class="panel briefing">
        <div class="panel-header"><h3 class="panel-title"><i data-lucide="clipboard-list"></i>Briefing op&eacute;rationnel</h3></div>
        <div class="panel-body"><p class="briefing-text" id="briefingText">Chargement du briefing.</p></div>
      </section>

      <section class="work-grid">
        <div class="panel">
          <div class="panel-header">
            <h3 class="panel-title"><i data-lucide="map"></i>Carte interactive</h3>
            <div class="legend" id="mapLegend"></div>
          </div>
          <div id="map"></div>
        </div>

        <div class="panel">
          <div class="panel-header">
            <h3 class="panel-title"><i data-lucide="crosshair"></i>Observation s&eacute;lectionn&eacute;e</h3>
          </div>
          <div class="panel-body" id="detailPanel">
            <div class="empty-state">Aucune observation s&eacute;lectionn&eacute;e</div>
          </div>
        </div>
      </section>

      <section class="charts">
        <div class="panel">
          <div class="panel-header"><h3 class="panel-title"><i data-lucide="bell"></i>Alertes</h3></div>
          <div class="panel-body"><div class="bar-list" id="alertChart"></div></div>
        </div>
        <div class="panel">
          <div class="panel-header"><h3 class="panel-title"><i data-lucide="map-pin"></i>Top zones</h3></div>
          <div class="panel-body"><div class="bar-list" id="zoneChart"></div></div>
        </div>
        <div class="panel">
          <div class="panel-header"><h3 class="panel-title"><i data-lucide="activity"></i>Evolution</h3></div>
          <div class="panel-body"><svg class="timeline" id="timelineChart" role="img"></svg></div>
        </div>
      </section>

      <section class="panel table-panel">
        <div class="panel-header">
          <h3 class="panel-title"><i data-lucide="list-filter"></i>Observations &agrave; examiner</h3>
          <span class="status-pill" id="tableStatus">0 ligne</span>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Score</th>
                <th>Alerte</th>
                <th>Navire</th>
                <th>Zone</th>
                <th>Pays</th>
                <th>Confiance</th>
                <th>Action</th>
                <th>Raisons de priorisation</th>
                <th>D&eacute;tail</th>
              </tr>
            </thead>
            <tbody id="tableBody"></tbody>
          </table>
        </div>
      </section>
    </main>
  </div>

  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script>
    const app = {
      all: [],
      zones: [],
      daily: [],
      militaryZones: [],
      filtered: [],
      map: null,
      detectionLayer: null,
      zoneLayer: null,
      markerById: new Map(),
      selectedId: null,
      topPrioritiesOnly: false,
      dateMin: "",
      dateMax: "",
    };

    const palette = {
      red: "#B91C1C",
      orange: "#D97706",
      amber: "#D9A441",
      teal: "#2C7A7B",
      green: "#2f855a",
      blue: "#2E5E7E",
      gray: "#64748b",
      navy: "#0B1F33",
      purple: "#5B4B8A"
    };

    const els = {};
    [
      "search", "minScore", "minScoreValue", "dateStart", "dateEnd",
      "alertChecks", "riskChecks", "countryChecks", "categoryChecks",
      "groupChecks", "qualityChecks", "humanOnly", "sensitiveOnly",
      "copresenceOnly", "denseOnly", "mapMode", "sortMode", "topPriorities",
      "resetFilters", "exportCsv", "sourceLine", "resultStatus", "reviewStatus",
      "kpiImmediate", "kpiAnalystAlerts", "kpiMaxScore", "kpiMaxAlert",
      "kpiSensitiveZones", "kpiMilitary", "kpiMilitaryRate", "kpiConfidence",
      "briefingText", "mapLegend", "detailPanel", "alertChart", "zoneChart",
      "timelineChart", "tableStatus", "tableBody"
    ].forEach((id) => els[id] = document.getElementById(id));

    function fmtNumber(value) {
      return new Intl.NumberFormat("fr-FR").format(value || 0);
    }

    function fmtPercent(value) {
      return `${Math.round((value || 0) * 100)}%`;
    }

    function fmtGeneratedAt(value) {
      const date = new Date(value);
      if (Number.isNaN(date.getTime())) return value || "";
      const day = date.toLocaleDateString("fr-FR", { day: "2-digit", month: "long", year: "numeric" });
      return `${day} • ${date.toISOString().slice(11, 19)}Z`;
    }

    function escapeHtml(value) {
      return String(value ?? "").replace(/[&<>"']/g, (char) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        "\"": "&quot;",
        "'": "&#039;"
      }[char]));
    }

    function uniqueSorted(rows, key) {
      return [...new Set(rows.map((row) => row[key]).filter(Boolean))]
        .sort((a, b) => String(a).localeCompare(String(b), "fr"));
    }

    function countBy(rows, key) {
      const counts = new Map();
      rows.forEach((row) => counts.set(row[key] || "Inconnu", (counts.get(row[key] || "Inconnu") || 0) + 1));
      return counts;
    }

    function checkedValues(container) {
      return [...container.querySelectorAll("input[type='checkbox']:checked")].map((node) => node.value);
    }

    function buildChecks(container, values, counts, prefix) {
      container.innerHTML = values.map((value, index) => {
        const safeId = `${prefix}-${index}`;
        return `
          <div class="check-row">
            <input id="${safeId}" value="${escapeHtml(value)}" type="checkbox" checked>
            <label for="${safeId}" title="${escapeHtml(value)}">${escapeHtml(value)}</label>
            <span>${fmtNumber(counts.get(value) || 0)}</span>
          </div>
        `;
      }).join("");
      container.querySelectorAll("input").forEach((node) => node.addEventListener("change", applyFilters));
    }

    function setupFilters() {
      const dates = app.all.map((row) => row.date_only).filter(Boolean).sort();
      app.dateMin = dates[0] || "";
      app.dateMax = dates[dates.length - 1] || "";
      els.dateStart.min = app.dateMin;
      els.dateStart.max = app.dateMax;
      els.dateEnd.min = app.dateMin;
      els.dateEnd.max = app.dateMax;
      els.dateStart.value = app.dateMin;
      els.dateEnd.value = app.dateMax;

      buildChecks(els.alertChecks, uniqueSorted(app.all, "alert_level"), countBy(app.all, "alert_level"), "alert");
      buildChecks(els.riskChecks, uniqueSorted(app.all, "effective_risk_level"), countBy(app.all, "effective_risk_level"), "risk");
      buildChecks(els.countryChecks, uniqueSorted(app.all, "country"), countBy(app.all, "country"), "country");
      buildChecks(els.categoryChecks, uniqueSorted(app.all, "category"), countBy(app.all, "category"), "category");
      buildChecks(els.groupChecks, uniqueSorted(app.all, "vessel_group"), countBy(app.all, "vessel_group"), "group");
      buildChecks(els.qualityChecks, uniqueSorted(app.all, "quality_level"), countBy(app.all, "quality_level"), "quality");

      [
        els.search, els.minScore, els.dateStart, els.dateEnd, els.humanOnly,
        els.sensitiveOnly, els.copresenceOnly, els.denseOnly, els.mapMode, els.sortMode
      ].forEach((node) => node.addEventListener("input", applyFilters));
      els.topPriorities.addEventListener("click", () => {
        app.topPrioritiesOnly = !app.topPrioritiesOnly;
        els.topPriorities.classList.toggle("active", app.topPrioritiesOnly);
        els.topPriorities.textContent = app.topPrioritiesOnly ? "Top 10 priorités activé" : "Afficher le Top 10 priorités";
        applyFilters();
      });
      els.resetFilters.addEventListener("click", resetFilters);
      els.exportCsv.addEventListener("click", exportCsv);
    }

    function initMap() {
      if (!window.L) {
        document.getElementById("map").innerHTML = '<div class="map-fallback">Leaflet indisponible. Les filtres, scores et tableaux restent actifs.</div>';
        return;
      }
      app.map = L.map("map", {
        preferCanvas: true,
        worldCopyJump: true,
        zoomControl: true
      }).setView([23, 18], 2);
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 18,
        attribution: "&copy; OpenStreetMap"
      }).addTo(app.map);
      app.zoneLayer = L.layerGroup().addTo(app.map);
      app.detectionLayer = L.layerGroup().addTo(app.map);
    }

    function scoreColor(score) {
      if (score >= 80) return palette.red;
      if (score >= 60) return palette.orange;
      if (score >= 40) return palette.amber;
      return palette.gray;
    }

    function operationalAction(score) {
      if (score >= 80) return { label: "Revue prioritaire immédiate", className: "red" };
      if (score >= 60) return { label: "Alerte analyste", className: "orange" };
      if (score >= 40) return { label: "Surveillance", className: "amber" };
      return { label: "Veille", className: "teal" };
    }

    function isMilitary(row) {
      return !String(row.vessel_group || "").toLowerCase().includes("civil");
    }

    function shortReason(row) {
      const strategic = String(row.vessel_group || "").toLowerCase().includes("strategique");
      const critical = String(row.effective_risk_level || "").toLowerCase().includes("critical");
      if (critical && strategic) return "Zone critique + navire stratégique";
      if (row.confidence >= 0.85 && (row.in_sensitive_military_zone || row.near_sensitive_zone_25km)) return "Confiance élevée + proximité zone sensible";
      if (isMilitary(row) && row.mil_zone_active) return "Navire militaire + zone active";
      if (isMilitary(row) && critical) return "Navire militaire + zone critique";
      if (row.possible_co_presence_proxy) return "Co-présence à vérifier";
      if (row.dense_activity_same_day) return "Activité dense le même jour";
      return row.review_reasons ? row.review_reasons.split(";")[0].trim() : "Priorité calculée par le score";
    }

    function scoreContributions(row) {
      const items = [];
      if (row.score_vessel > 0) {
        const strategic = String(row.vessel_group || "").toLowerCase().includes("strategique");
        items.push([row.score_vessel, strategic ? "navire stratégique" : isMilitary(row) ? "navire militaire" : "type de navire"]);
      }
      if (row.score_geo > 0) {
        const critical = String(row.effective_risk_level || "").toLowerCase().includes("critical");
        items.push([row.score_geo, critical ? "zone critique" : "zone sensible"]);
      }
      if (row.score_confidence > 0) items.push([row.score_confidence, "confiance élevée"]);
      if (row.score_context > 0) {
        items.push([row.score_context, row.dense_activity_same_day ? "activité dense" : "contexte opérationnel"]);
      }
      if (row.score_anomaly > 0) {
        items.push([row.score_anomaly, row.mil_zone_active ? "zone militaire active proche" : "anomalie géospatiale"]);
      }
      return items;
    }

    function riskColor(risk) {
      const value = String(risk || "").toLowerCase();
      if (value.includes("critical")) return palette.red;
      if (value.includes("high")) return palette.orange;
      if (value.includes("medium")) return palette.amber;
      if (value.includes("low")) return palette.green;
      return palette.gray;
    }

    function groupColor(group) {
      const value = String(group || "").toLowerCase();
      if (value.includes("strategique")) return palette.red;
      if (value === "combat") return palette.orange;
      if (value.includes("soutien") || value.includes("amphibie")) return palette.purple;
      if (value.includes("civil")) return palette.green;
      return palette.gray;
    }

    function colorFor(row) {
      const mode = els.mapMode.value;
      if (mode === "risk") return riskColor(row.effective_risk_level);
      if (mode === "group") return groupColor(row.vessel_group);
      return scoreColor(row.priority_score);
    }

    function badgeClass(row, field) {
      const value = String(row[field] || "").toLowerCase();
      if (field === "priority_score") {
        if (row.priority_score >= 80) return "red";
        if (row.priority_score >= 60) return "orange";
        if (row.priority_score >= 40) return "amber";
        return "teal";
      }
      if (value.includes("immediate") || value.includes("critique") || value.includes("critical")) return "red";
      if (value.includes("alerte") || value.includes("high")) return "orange";
      if (value.includes("examiner") || value.includes("medium")) return "amber";
      if (value.includes("veille") || value.includes("low")) return "teal";
      return "gray";
    }

    function jitter(row, index) {
      const angle = (index * 137.508) * Math.PI / 180;
      const radius = Math.min(0.18, 0.018 + (row.same_zone_day_detection_count || 0) * 0.006);
      return {
        lat: row.image_lat + Math.sin(angle) * radius,
        lon: row.image_lon + Math.cos(angle) * radius
      };
    }

    function popupHtml(row) {
      const action = operationalAction(row.priority_score).label;
      return `
        <div class="popup-title">Navire : ${escapeHtml(row.category)}</div>
        <div class="popup-grid">
          <span>Score</span><span>${row.priority_score}</span>
          <span>Zone</span><span>${escapeHtml(row.zone_name)}</span>
          <span>Risque</span><span>${escapeHtml(row.effective_risk_level)}</span>
          <span>Confiance</span><span>${fmtPercent(row.confidence)}</span>
          <span>Action</span><span>${escapeHtml(action)}</span>
        </div>
      `;
    }

    function updateLegend() {
      const mode = els.mapMode.value;
      let rows;
      if (mode === "risk") {
        rows = [["Critical", palette.red], ["High", palette.orange], ["Medium", palette.amber], ["Low", palette.green]];
      } else if (mode === "group") {
        rows = [["Stratégique", palette.red], ["Militaire", palette.orange], ["Soutien", palette.purple], ["Civil", palette.green]];
      } else {
        rows = [["80-100", palette.red], ["60-79", palette.orange], ["40-59", palette.amber], ["0-39", palette.gray]];
      }
      els.mapLegend.innerHTML = rows.map(([label, color]) => `
        <span class="legend-item"><span class="swatch" style="background:${color}"></span>${label}</span>
      `).join("");
    }

    function renderMap() {
      updateLegend();
      if (!app.map || !app.detectionLayer || !app.zoneLayer) return;
      app.detectionLayer.clearLayers();
      app.zoneLayer.clearLayers();
      app.markerById.clear();

      app.militaryZones.forEach((zone) => {
        if (!zone.lat || !zone.lon) return;
        const color = riskColor(zone.risk_level);
        L.circle([zone.lat, zone.lon], {
          radius: zone.active ? 32000 : 22000,
          color,
          fillColor: color,
          fillOpacity: zone.active ? 0.12 : 0.06,
          opacity: zone.active ? 0.58 : 0.28,
          weight: zone.active ? 2 : 1
        }).bindPopup(`
          <div class="popup-title">${escapeHtml(zone.name)}</div>
          <div class="popup-grid">
            <span>Risque</span><span>${escapeHtml(zone.risk_level)}</span>
            <span>Pays</span><span>${escapeHtml(zone.country)}</span>
            <span>Base</span><span>${escapeHtml(zone.base_name)}</span>
            <span>Active</span><span>${zone.active ? "Oui" : "Non"}</span>
          </div>
        `).addTo(app.zoneLayer);
      });

      const bounds = [];
      app.filtered.forEach((row, index) => {
        const point = jitter(row, index);
        const color = colorFor(row);
        const marker = L.circleMarker([point.lat, point.lon], {
          radius: Math.max(5, Math.min(15, 4 + row.priority_score / 9)),
          color: "#ffffff",
          fillColor: color,
          fillOpacity: 0.86,
          opacity: 0.95,
          weight: row.requires_human_review ? 2.5 : 1.4
        }).bindPopup(popupHtml(row));
        marker.on("click", () => renderDetail(row));
        marker.addTo(app.detectionLayer);
        app.markerById.set(row.detection_id, marker);
        bounds.push([point.lat, point.lon]);
      });
      if (bounds.length > 0) {
        app.map.fitBounds(bounds, { padding: [26, 26], maxZoom: 8 });
      }
    }

    function renderDetail(row) {
      app.selectedId = row.detection_id;
      const action = operationalAction(row.priority_score);
      const contributions = scoreContributions(row);
      els.detailPanel.innerHTML = `
        <div class="detail-grid">
          <div class="detail-item"><strong>ID</strong><div class="detail-value">${escapeHtml(row.detection_id)}</div></div>
          <div class="detail-item"><strong>Navire</strong><div class="detail-value">${escapeHtml(row.category)}</div></div>
          <div class="detail-item"><strong>Zone</strong><div class="detail-value">${escapeHtml(row.zone_name)}</div></div>
          <div class="detail-item"><strong>Pays</strong><div class="detail-value">${escapeHtml(row.country)}</div></div>
        </div>
        <div class="detail-metrics">
          <div class="metric-item"><span class="metric-label">Score</span><span class="metric-value red">${row.priority_score}</span></div>
          <div class="metric-item"><span class="metric-label">Confiance</span><span class="metric-value">${fmtPercent(row.confidence)}</span></div>
          <div class="metric-item"><span class="metric-label">Risque</span><span class="badge ${badgeClass(row, "effective_risk_level")}">${escapeHtml(row.effective_risk_level)}</span></div>
          <div class="metric-item"><span class="metric-label">Alerte</span><span class="badge ${action.className}">${escapeHtml(action.label)}</span></div>
        </div>
        <div class="recommendation" style="border-left-color:${scoreColor(row.priority_score)}">
          <div class="recommendation-row">
            <i data-lucide="triangle-alert"></i>
            <div>
              <strong>Recommandation opérationnelle</strong>
              <span>${escapeHtml(action.label)}</span>
              <p>${row.priority_score >= 80 ? "Revue prioritaire immédiate recommandée." : row.priority_score >= 60 ? "Validation nécessaire par un analyste." : row.priority_score >= 40 ? "Surveillance renforcée recommandée." : "Veille régulière suffisante."}</p>
            </div>
          </div>
        </div>
        <h4 class="panel-title">Pourquoi cette priorité ?</h4>
        <div class="why-list">
          ${contributions.length ? contributions.map(([value, label]) => `
            <div class="why-item"><span>${escapeHtml(label)}</span><strong>+${value}</strong></div>
          `).join("") : '<div class="why-item"><span>Priorité basse</span><strong>+0</strong></div>'}
        </div>
        <div class="detail-item" style="border-bottom:0;margin-top:10px">
          <strong>Raisons de priorisation complètes</strong>${escapeHtml(row.review_reasons || "Aucune")}
        </div>
      `;
      if (window.lucide) lucide.createIcons();
    }

    function summarize(rows) {
      const total = rows.length;
      const reviews = rows.filter((row) => row.requires_human_review).length;
      const immediate = rows.filter((row) => row.priority_score >= 80).length;
      const analystAlerts = rows.filter((row) => row.priority_score >= 60 && row.priority_score < 80).length;
      const military = rows.filter((row) => isMilitary(row)).length;
      const sensitiveZones = new Set(rows.filter((row) => row.in_sensitive_military_zone || row.near_sensitive_zone_25km).map((row) => row.zone_name)).size;
      const maxScore = rows.reduce((max, row) => Math.max(max, row.priority_score || 0), 0);
      const maxAlert = operationalAction(maxScore).label;
      const avgConf = total ? rows.reduce((sum, row) => sum + (row.confidence || 0), 0) / total : 0;
      els.kpiImmediate.textContent = fmtNumber(immediate);
      els.kpiAnalystAlerts.textContent = fmtNumber(analystAlerts);
      els.kpiMaxScore.textContent = maxScore;
      els.kpiMaxAlert.textContent = maxAlert;
      els.kpiSensitiveZones.textContent = fmtNumber(sensitiveZones);
      els.kpiMilitary.textContent = fmtNumber(military);
      els.kpiMilitaryRate.textContent = total ? fmtPercent(military / total) : "0%";
      els.kpiConfidence.textContent = fmtPercent(avgConf);
      els.resultStatus.textContent = `${fmtNumber(total)} observation${total > 1 ? "s" : ""}`;
      els.reviewStatus.textContent = `${fmtNumber(reviews)} revue${reviews > 1 ? "s" : ""}`;
    }

    function renderBriefing(rows) {
      const reviews = rows.filter((row) => row.requires_human_review || row.priority_score >= 60).length;
      const topZones = aggregate(rows, "zone_name").slice(0, 3).map((row) => row.label);
      const militaryRows = rows.filter((row) => isMilitary(row));
      const topVessels = aggregate(militaryRows.length ? militaryRows : rows, "category").slice(0, 3).map((row) => row.label);
      if (!rows.length) {
        els.briefingText.textContent = "Aucune observation ne correspond aux filtres actifs.";
        return;
      }
      const zoneText = topZones.length ? topZones.join(", ") : "aucune zone dominante";
      const vesselText = topVessels.length ? topVessels.join(", ") : "aucun type dominant";
      els.briefingText.textContent = `${fmtNumber(reviews)} observations nécessitent une revue. Les zones les plus sensibles sont ${zoneText}. Les navires prioritaires détectés sont principalement des ${vesselText}.`;
    }

    function aggregate(rows, key) {
      return [...countBy(rows, key).entries()]
        .map(([label, value]) => ({ label, value }))
        .sort((a, b) => b.value - a.value);
    }

    function renderBars(container, rows, colorFn) {
      const max = Math.max(...rows.map((row) => row.value), 1);
      if (!rows.length) {
        container.innerHTML = '<div class="empty-state">Aucune donnee</div>';
        return;
      }
      container.innerHTML = rows.map((row) => `
        <div class="bar-row">
          <div class="bar-label" title="${escapeHtml(row.label)}">${escapeHtml(row.label)}</div>
          <div class="bar-track"><div class="bar-fill" style="width:${Math.max(3, row.value / max * 100)}%; background:${colorFn(row.label)}"></div></div>
          <strong>${fmtNumber(row.value)}</strong>
        </div>
      `).join("");
    }

    function renderTimeline(rows) {
      const svg = els.timelineChart;
      const width = svg.clientWidth || 360;
      const height = svg.clientHeight || 186;
      const pad = { top: 12, right: 18, bottom: 28, left: 30 };
      const byDate = new Map();
      rows.forEach((row) => byDate.set(row.date_only, (byDate.get(row.date_only) || 0) + 1));
      const points = [...byDate.entries()]
        .filter(([date]) => date)
        .sort((a, b) => a[0].localeCompare(b[0]));
      if (points.length === 0) {
        svg.innerHTML = '<text x="50%" y="50%" text-anchor="middle">Aucune donnee</text>';
        return;
      }
      const max = Math.max(...points.map(([, value]) => value), 1);
      const xScale = (index) => pad.left + (points.length === 1 ? 0 : index * (width - pad.left - pad.right) / (points.length - 1));
      const yScale = (value) => height - pad.bottom - value * (height - pad.top - pad.bottom) / max;
      const path = points.map(([, value], index) => `${xScale(index)},${yScale(value)}`).join(" ");
      const firstDate = points[0][0];
      const lastDate = points[points.length - 1][0];
      svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
      svg.innerHTML = `
        <line x1="${pad.left}" y1="${height - pad.bottom}" x2="${width - pad.right}" y2="${height - pad.bottom}" stroke="#d8dee7"/>
        <line x1="${pad.left}" y1="${pad.top}" x2="${pad.left}" y2="${height - pad.bottom}" stroke="#d8dee7"/>
        <polyline fill="none" stroke="${palette.teal}" stroke-width="3" points="${path}"/>
        ${points.map(([, value], index) => `<circle cx="${xScale(index)}" cy="${yScale(value)}" r="3.5" fill="${palette.orange}"><title>${value} observations</title></circle>`).join("")}
        <text x="${pad.left}" y="${height - 8}">${escapeHtml(firstDate)}</text>
        <text x="${width - pad.right}" y="${height - 8}" text-anchor="end">${escapeHtml(lastDate)}</text>
        <text x="${pad.left + 2}" y="${pad.top + 10}">${max}</text>
      `;
    }

    function renderCharts() {
      renderBars(els.alertChart, aggregate(app.filtered, "alert_level").slice(0, 6), (label) => {
        const lower = String(label).toLowerCase();
        if (lower.includes("immediate")) return palette.red;
        if (lower.includes("alerte")) return palette.orange;
        if (lower.includes("examiner")) return palette.amber;
        return palette.teal;
      });
      renderBars(els.zoneChart, aggregate(app.filtered, "zone_name").slice(0, 8), () => palette.blue);
      renderTimeline(app.filtered);
    }

    function sortedRows(rows) {
      const mode = els.sortMode.value;
      const copy = [...rows];
      if (mode === "date") return copy.sort((a, b) => String(b.date_only).localeCompare(String(a.date_only)));
      if (mode === "confidence") return copy.sort((a, b) => b.confidence - a.confidence);
      if (mode === "zone") return copy.sort((a, b) => String(a.zone_name).localeCompare(String(b.zone_name), "fr"));
      return copy.sort((a, b) => b.priority_score - a.priority_score);
    }

    function renderTable() {
      const rows = sortedRows(app.filtered).slice(0, 250);
      els.tableStatus.textContent = `${fmtNumber(rows.length)} ligne${rows.length > 1 ? "s" : ""}`;
      if (rows.length === 0) {
        els.tableBody.innerHTML = '<tr><td colspan="9"><div class="empty-state">Aucune observation avec ces filtres</div></td></tr>';
        return;
      }
      els.tableBody.innerHTML = rows.map((row) => `
        <tr>
          <td><span class="badge ${operationalAction(row.priority_score).className}">${row.priority_score}</span></td>
          <td><span class="badge ${badgeClass(row, "alert_level")}">${escapeHtml(row.alert_level)}</span></td>
          <td>${escapeHtml(row.category)}</td>
          <td>${escapeHtml(row.zone_name)}</td>
          <td>${escapeHtml(row.country)}</td>
          <td>${fmtPercent(row.confidence)}</td>
          <td><span class="badge ${operationalAction(row.priority_score).className}">${escapeHtml(operationalAction(row.priority_score).label)}</span></td>
          <td title="${escapeHtml(row.review_reasons)}">${escapeHtml(shortReason(row))}</td>
          <td><button class="mini-button" data-id="${escapeHtml(row.detection_id)}">Voir</button></td>
        </tr>
      `).join("");
      els.tableBody.querySelectorAll("button[data-id]").forEach((button) => {
        button.addEventListener("click", () => focusDetection(button.dataset.id));
      });
    }

    function focusDetection(id) {
      const row = app.filtered.find((item) => item.detection_id === id);
      if (!row) return;
      renderDetail(row);
      const marker = app.markerById.get(id);
      if (marker && app.map) {
        app.map.setView(marker.getLatLng(), Math.max(app.map.getZoom(), 7));
        marker.openPopup();
      }
    }

    function applyFilters() {
      els.minScoreValue.textContent = els.minScore.value;
      const query = els.search.value.trim().toLowerCase();
      const alertSet = new Set(checkedValues(els.alertChecks));
      const riskSet = new Set(checkedValues(els.riskChecks));
      const categorySet = new Set(checkedValues(els.categoryChecks));
      const groupSet = new Set(checkedValues(els.groupChecks));
      const qualitySet = new Set(checkedValues(els.qualityChecks));
      const countrySet = new Set(checkedValues(els.countryChecks));
      const minScore = Number(els.minScore.value || 0);
      const start = els.dateStart.value || app.dateMin;
      const end = els.dateEnd.value || app.dateMax;

      app.filtered = app.all.filter((row) => {
        const haystack = [
          row.detection_id, row.image_id, row.file_name, row.zone_name,
          row.country, row.category, row.vessel_group, row.alert_level,
          row.effective_risk_level, row.review_reasons
        ].join(" ").toLowerCase();
        return row.priority_score >= minScore
          && (!query || haystack.includes(query))
          && (!start || row.date_only >= start)
          && (!end || row.date_only <= end)
          && alertSet.has(row.alert_level)
          && riskSet.has(row.effective_risk_level)
          && categorySet.has(row.category)
          && groupSet.has(row.vessel_group)
          && qualitySet.has(row.quality_level)
          && countrySet.has(row.country)
          && (!els.humanOnly.checked || row.requires_human_review)
          && (!els.sensitiveOnly.checked || row.in_sensitive_military_zone)
          && (!els.copresenceOnly.checked || row.possible_co_presence_proxy)
          && (!els.denseOnly.checked || row.dense_activity_same_day);
      });
      if (app.topPrioritiesOnly) {
        app.filtered = [...app.filtered].sort((a, b) => b.priority_score - a.priority_score).slice(0, 10);
      }

      summarize(app.filtered);
      renderBriefing(app.filtered);
      renderMap();
      renderCharts();
      renderTable();
      if (app.selectedId && !app.filtered.some((row) => row.detection_id === app.selectedId)) {
        els.detailPanel.innerHTML = '<div class="empty-state">Aucune observation sélectionnée</div>';
        app.selectedId = null;
      }
    }

    function resetFilters() {
      els.search.value = "";
      els.minScore.value = "0";
      els.dateStart.value = app.dateMin;
      els.dateEnd.value = app.dateMax;
      [els.alertChecks, els.riskChecks, els.countryChecks, els.categoryChecks, els.groupChecks, els.qualityChecks].forEach((container) => {
        container.querySelectorAll("input[type='checkbox']").forEach((node) => node.checked = true);
      });
      [els.humanOnly, els.sensitiveOnly, els.copresenceOnly, els.denseOnly].forEach((node) => node.checked = false);
      app.topPrioritiesOnly = false;
      els.topPriorities.classList.remove("active");
      els.topPriorities.textContent = "Afficher le Top 10 priorités";
      els.mapMode.value = "priority";
      els.sortMode.value = "priority";
      applyFilters();
    }

    function exportCsv() {
      const columns = [
        "priority_score", "operational_action", "alert_level", "category", "zone_name",
        "country", "confidence", "effective_risk_level", "short_reason",
        "detection_id", "date_only", "review_reasons"
      ];
      const rows = [columns.join(",")].concat(app.filtered.map((row) => columns.map((column) => {
        const value = column === "operational_action"
          ? operationalAction(row.priority_score).label
          : column === "short_reason"
            ? shortReason(row)
            : row[column] ?? "";
        return `"${String(value).replaceAll("\"", "\"\"")}"`;
      }).join(",")));
      const blob = new Blob([rows.join("\n")], { type: "text/csv;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "observations_priorisees.csv";
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    }

    async function boot() {
      const response = await fetch("/api/data");
      if (!response.ok) throw new Error("data");
      const payload = await response.json();
      app.all = payload.detections || [];
      app.zones = payload.zoneSummary || [];
      app.daily = payload.dailySummary || [];
      app.militaryZones = payload.militaryZones || [];
      els.sourceLine.textContent = `${fmtNumber(app.all.length)} observations chargées • ${fmtGeneratedAt(payload.generatedAt)}`;
      setupFilters();
      initMap();
      applyFilters();
      if (window.lucide) lucide.createIcons();
    }

    boot().catch(() => {
      document.body.innerHTML = '<main style="padding:24px;font-family:system-ui"><h1>Chargement impossible</h1><p>Vérifiez la présence des CSV de priorisation.</p></main>';
    });
  </script>
</body>
</html>
"""


class AppHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/index.html"}:
            self.send_text(HTML_TEMPLATE, "text/html; charset=utf-8")
            return
        if parsed.path == "/official-logo":
            self.send_logo()
            return
        if parsed.path == "/api/data":
            payload = json.dumps(load_payload(), ensure_ascii=False).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)
            return
        if parsed.path == "/health":
            self.send_text("ok", "text/plain; charset=utf-8")
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def log_message(self, format: str, *args: Any) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {self.address_string()} - {format % args}")

    def send_text(self, text: str, content_type: str) -> None:
        body = text.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_logo(self) -> None:
        if LOGO_FILE is None or not LOGO_FILE.exists():
            self.send_error(HTTPStatus.NOT_FOUND, "Logo not found")
            return
        content_type = mimetypes.guess_type(LOGO_FILE.name)[0] or "application/octet-stream"
        body = LOGO_FILE.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def find_free_port(preferred: int) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("127.0.0.1", preferred))
            return preferred
        except OSError:
            pass
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def main() -> None:
    parser = argparse.ArgumentParser(description="Application web de priorisation navires.")
    parser.add_argument("--host", default="127.0.0.1", help="Adresse d'ecoute")
    parser.add_argument("--port", default=8050, type=int, help="Port prefere")
    parser.add_argument("--no-auto-port", action="store_true", help="Ne pas chercher un port libre")
    args = parser.parse_args()

    missing = [
        path
        for path in (DETECTIONS_CSV, ZONE_SUMMARY_CSV, DAILY_SUMMARY_CSV, MILITARY_ZONES_CSV)
        if not path.exists()
    ]
    if missing:
        formatted = "\n".join(f"- {path}" for path in missing)
        raise SystemExit(f"Fichiers de donnees introuvables:\n{formatted}")

    load_payload()
    port = args.port if args.no_auto_port else find_free_port(args.port)
    server = ThreadingHTTPServer((args.host, port), AppHandler)
    print(f"Application disponible sur http://{args.host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nArret du serveur")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
