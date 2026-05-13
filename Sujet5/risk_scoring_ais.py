from __future__ import annotations

import argparse
import csv
import math
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data_generated"
DEFAULT_AIS_INPUT = DATA_DIR / "ais_signals_simulated.csv"
DEFAULT_OUTPUT = DATA_DIR / "risk_events_generated.csv"


HIGH_THREAT = {"Porte-avions", "Sous-marin", "Destroyer", "Croiseur"}
MEDIUM_THREAT = {"Fr\u00e9gate", "Corvette", "Navire de guerre"}
SUPPORT_THREAT = {"B\u00e2timent de d\u00e9barquement", "Navire de soutien"}
RISK_POINTS = {"Critical": 15, "High": 10, "Medium": 5, "Low": 0}
RISK_ORDER = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1, "Unknown": 0}


FALLBACK_ZONE_CONTEXT: dict[str, dict[str, Any]] = {
    "D\u00e9troit d'Ormuz": {
        "effective_risk_level": "Critical",
        "max_priority_score": 88,
        "avg_priority_score": 68,
        "base_type": "Base Sous-marine",
        "mil_density": 2,
        "mil_zone_active": True,
        "business_proxy_zone": "D\u00e9troit d'Ormuz",
    },
    "Mer Rouge": {
        "effective_risk_level": "High",
        "max_priority_score": 72,
        "avg_priority_score": 54,
        "base_type": "Base Navale",
        "mil_density": 2,
        "mil_zone_active": True,
        "business_proxy_zone": "Canal de Suez",
    },
    "M\u00e9diterran\u00e9e orientale": {
        "effective_risk_level": "High",
        "max_priority_score": 70,
        "avg_priority_score": 52,
        "base_type": "Base Navale",
        "mil_density": 1,
        "mil_zone_active": False,
        "business_proxy_zone": "Port militaire de Toulon",
    },
    "Mer Noire": {
        "effective_risk_level": "High",
        "max_priority_score": 74,
        "avg_priority_score": 56,
        "base_type": "Base Navale",
        "mil_density": 2,
        "mil_zone_active": True,
        "business_proxy_zone": "",
    },
    "D\u00e9troit de Ta\u00efwan": {
        "effective_risk_level": "Critical",
        "max_priority_score": 90,
        "avg_priority_score": 66,
        "base_type": "Base Sous-marine",
        "mil_density": 3,
        "mil_zone_active": True,
        "business_proxy_zone": "Port de Shanghai",
    },
}


@dataclass
class BusinessContext:
    zone_profiles: dict[str, dict[str, Any]] = field(default_factory=dict)
    category_priority: dict[str, float] = field(default_factory=dict)
    zone_category_priority: dict[tuple[str, str], float] = field(default_factory=dict)
    source_files: list[str] = field(default_factory=list)


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


def text_key(value: Any) -> str:
    normalized = unicodedata.normalize("NFKD", clean_text(value))
    return normalized.encode("ascii", "ignore").decode("ascii").casefold().strip()


def to_bool(value: Any) -> bool:
    return clean_text(value).casefold() in {"true", "1", "yes", "oui", "vrai"}


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


def read_csv_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    encodings = ("utf-8-sig", "utf-8", "cp1252", "latin1")
    last_error: Exception | None = None
    for encoding in encodings:
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                rows: list[dict[str, Any]] = []
                for row in csv.DictReader(handle):
                    rows.append({clean_text(key): clean_text(value) for key, value in row.items()})
                return rows
        except UnicodeError as exc:
            last_error = exc
    raise RuntimeError(f"Cannot read {path}: {last_error}")


def find_generalisation_dir(root: Path) -> Path | None:
    direct = root / "G\u00e9n\u00e9ralisation"
    if direct.exists():
        return direct
    for child in root.iterdir():
        normalized = unicodedata.normalize("NFKD", child.name).encode("ascii", "ignore").decode("ascii")
        if child.is_dir() and normalized.casefold() == "generalisation":
            return child
    return None


def highest_risk(current: str, candidate: str) -> str:
    current_clean = clean_text(current) or "Unknown"
    candidate_clean = clean_text(candidate) or "Unknown"
    return candidate_clean if RISK_ORDER.get(candidate_clean, 0) > RISK_ORDER.get(current_clean, 0) else current_clean


def extract_location_name(raw_name: str) -> str:
    name = clean_text(raw_name)
    match = re.search(r"\s-\s(.+)$", name)
    return match.group(1).strip() if match else name


def parse_coordinates(raw: str) -> tuple[float, float] | None:
    parts = [part.strip() for part in clean_text(raw).split(",")]
    if len(parts) != 2:
        return None
    lat = to_float(parts[0], default=float("nan"))
    lon = to_float(parts[1], default=float("nan"))
    if math.isnan(lat) or math.isnan(lon):
        return None
    return lat, lon


def load_business_context(root: Path) -> BusinessContext:
    context = BusinessContext()
    generalisation_dir = find_generalisation_dir(root)
    if not generalisation_dir:
        context.zone_profiles = {text_key(name): profile.copy() | {"zone_name": name} for name, profile in FALLBACK_ZONE_CONTEXT.items()}
        return context

    outputs_dir = generalisation_dir / "outputs_priorisation_v2"
    processed_dir = generalisation_dir / "data" / "processed"
    raw_dir = generalisation_dir / "data" / "raw"

    scored_path = outputs_dir / "scored_detections_v2.csv"
    zone_summary_path = processed_dir / "zones_resume_scoring.csv"
    military_zones_path = raw_dir / "military_zones.csv"

    if scored_path.exists():
        rows = read_csv_rows(scored_path)
        context.source_files.append(str(scored_path))
        df = pd.DataFrame(rows)
        if not df.empty:
            for col in ["priority_score", "score_vessel", "score_geo", "score_context", "score_confidence", "score_anomaly"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
            if {"category", "priority_score"}.issubset(df.columns):
                context.category_priority = {
                    text_key(category): float(score)
                    for category, score in df.groupby("category")["priority_score"].median().to_dict().items()
                }
            if {"zone_name", "category", "priority_score"}.issubset(df.columns):
                grouped = df.groupby(["zone_name", "category"])["priority_score"].median()
                context.zone_category_priority = {
                    (text_key(zone), text_key(category)): float(score) for (zone, category), score in grouped.to_dict().items()
                }
            if {"zone_name", "priority_score"}.issubset(df.columns):
                for zone_name, group in df.groupby("zone_name"):
                    profile = context.zone_profiles.setdefault(text_key(zone_name), {"zone_name": clean_text(zone_name)})
                    profile["max_priority_score"] = max(to_float(profile.get("max_priority_score")), float(group["priority_score"].max()))
                    profile["avg_priority_score"] = float(group["priority_score"].mean())
                    if "effective_risk_level" in group.columns:
                        risks = [clean_text(value) for value in group["effective_risk_level"].dropna().tolist()]
                        for risk in risks:
                            profile["effective_risk_level"] = highest_risk(profile.get("effective_risk_level", "Unknown"), risk)
                    if "base_type" in group.columns:
                        base_values = [clean_text(value) for value in group["base_type"].dropna().tolist() if clean_text(value)]
                        if base_values:
                            profile["base_type"] = max(base_values, key=lambda value: {"Base Sous-marine": 3, "Base Navale": 2, "Base A\u00e9rienne": 1}.get(value, 0))
                    if "mil_density" in group.columns:
                        profile["mil_density"] = max(to_float(profile.get("mil_density")), float(pd.to_numeric(group["mil_density"], errors="coerce").fillna(0).max()))
                    if "mil_zone_active" in group.columns:
                        profile["mil_zone_active"] = bool(group["mil_zone_active"].map(to_bool).any())

    if zone_summary_path.exists():
        context.source_files.append(str(zone_summary_path))
        for row in read_csv_rows(zone_summary_path):
            zone_name = clean_text(row.get("zone_name"))
            if not zone_name:
                continue
            profile = context.zone_profiles.setdefault(text_key(zone_name), {"zone_name": zone_name})
            profile["effective_risk_level"] = highest_risk(profile.get("effective_risk_level", "Unknown"), row.get("risk_level", row.get("effective_risk_level", "")))
            profile["max_priority_score"] = max(to_float(profile.get("max_priority_score")), to_float(row.get("max_priority", row.get("max_priority_score"))))
            if row.get("avg_priority"):
                profile["avg_priority_score"] = max(to_float(profile.get("avg_priority_score")), to_float(row.get("avg_priority")))
            if row.get("latitude"):
                profile["latitude"] = to_float(row.get("latitude"))
            if row.get("longitude"):
                profile["longitude"] = to_float(row.get("longitude"))

    if military_zones_path.exists():
        context.source_files.append(str(military_zones_path))
        for row in read_csv_rows(military_zones_path):
            zone_name = extract_location_name(row.get("name", ""))
            if not zone_name:
                continue
            profile = context.zone_profiles.setdefault(text_key(zone_name), {"zone_name": zone_name})
            profile["effective_risk_level"] = highest_risk(profile.get("effective_risk_level", "Unknown"), row.get("risk_level", ""))
            profile["mil_zone_active"] = bool(profile.get("mil_zone_active", False) or to_bool(row.get("active")))
            base_name = clean_text(row.get("base_name"))
            if "Base Sous-marine" in base_name:
                profile["base_type"] = "Base Sous-marine"
            elif "Base Navale" in base_name and profile.get("base_type") != "Base Sous-marine":
                profile["base_type"] = "Base Navale"
            elif "Base A\u00e9rienne" in base_name and not profile.get("base_type"):
                profile["base_type"] = "Base A\u00e9rienne"
            profile["mil_density"] = to_float(profile.get("mil_density"), 0) + 1
            coordinates = parse_coordinates(row.get("coordinates", ""))
            if coordinates:
                profile["latitude"], profile["longitude"] = coordinates

    for zone_name, fallback in FALLBACK_ZONE_CONTEXT.items():
        key = text_key(zone_name)
        profile = context.zone_profiles.setdefault(key, {"zone_name": zone_name})
        for field_name, value in fallback.items():
            profile.setdefault(field_name, value)
        profile["effective_risk_level"] = highest_risk(profile.get("effective_risk_level", "Unknown"), fallback.get("effective_risk_level", "Unknown"))

    return context


def resolve_zone_profile(maritime_zone: str, context: BusinessContext) -> dict[str, Any]:
    zone_key = text_key(maritime_zone)
    profile = context.zone_profiles.get(zone_key)
    if profile:
        return profile
    fallback = FALLBACK_ZONE_CONTEXT.get(clean_text(maritime_zone), {})
    proxy_key = text_key(fallback.get("business_proxy_zone", ""))
    if proxy_key and proxy_key in context.zone_profiles:
        proxy_profile = context.zone_profiles[proxy_key].copy()
        proxy_profile["zone_name"] = clean_text(maritime_zone)
        proxy_profile["business_proxy_zone"] = fallback.get("business_proxy_zone")
        return proxy_profile
    return fallback.copy() | {"zone_name": clean_text(maritime_zone), "effective_risk_level": fallback.get("effective_risk_level", "Unknown")}


def score_vessel_type(vessel_type: str, is_military: bool) -> tuple[int, str | None]:
    vessel = clean_text(vessel_type)
    if vessel in HIGH_THREAT:
        return 35, "navire de combat strategique"
    if vessel in MEDIUM_THREAT:
        return 20, "navire de combat"
    if vessel in SUPPORT_THREAT:
        return 14, "navire de soutien/amphibie"
    if is_military:
        return 10, "navire militaire"
    return 0, None


def score_geo(row: dict[str, Any], zone_profile: dict[str, Any]) -> tuple[int, list[str]]:
    reasons: list[str] = []
    near_sensitive = to_bool(row.get("near_sensitive_zone"))
    distance_km = to_float(row.get("sensitive_zone_distance_km"), default=9999)
    base_type = clean_text(zone_profile.get("base_type"))
    density = to_float(zone_profile.get("mil_density"), default=0)
    zone_active = bool(zone_profile.get("mil_zone_active", False))

    score = 0
    if near_sensitive:
        score += 13 if distance_km <= 25 else 9
        reasons.append("proximite zone sensible")
    if zone_active:
        score += 5
        reasons.append("zone sensible active")
    if base_type == "Base Sous-marine":
        score += 8
        reasons.append("base sous-marine ou equivalent")
    elif base_type == "Base Navale":
        score += 5
        reasons.append("zone navale connue")
    elif base_type == "Base A\u00e9rienne":
        score += 3
        reasons.append("composante aeronavale")
    if density > 0:
        score += min(4, int(density))
    return min(30, score), reasons


def score_ais_behavior(row: dict[str, Any]) -> tuple[int, list[str]]:
    reasons: list[str] = []
    score = 0
    ais_status = clean_text(row.get("ais_status")).casefold()
    gap = to_int(row.get("ais_gap_minutes"))
    if ais_status == text_key("Interrompu") or "interrompu" in ais_status:
        if gap >= 240:
            score += 24
        elif gap >= 120:
            score += 20
        elif gap >= 45:
            score += 15
        else:
            score += 10
        reasons.append(f"coupure AIS {gap} min")

    nearest_nm = to_float(row.get("nearest_vessel_distance_nm"), default=999)
    nearby_count = to_int(row.get("nearby_vessel_count"))
    if nearest_nm <= 1.0:
        score += 10
        reasons.append("proximite immediate autre navire")
    elif nearest_nm <= 2.5:
        score += 6
        reasons.append("proximite autre navire")
    if nearby_count >= 4:
        score += 5
        reasons.append("regroupement de navires")
    elif nearby_count >= 2:
        score += 3

    course_change = to_float(row.get("course_change_deg"))
    if course_change >= 110:
        score += 8
        reasons.append("variation de cap tres forte")
    elif course_change >= 70:
        score += 5
        reasons.append("variation de cap forte")

    speed = to_float(row.get("speed_knots"))
    near_sensitive = to_bool(row.get("near_sensitive_zone"))
    if near_sensitive and speed <= 2.5:
        score += 7
        reasons.append("stationnement lent en zone sensible")
    elif speed >= 27:
        score += 5
        reasons.append("vitesse elevee")

    behavior_label = text_key(row.get("behavior_label"))
    if behavior_label == "suspect":
        score += 7
        reasons.append("comportement AIS suspect")

    return min(35, score), reasons


def score_legacy_business(row: dict[str, Any], zone_profile: dict[str, Any], context: BusinessContext) -> tuple[int, list[str]]:
    reasons: list[str] = []
    zone_key = text_key(row.get("maritime_zone"))
    vessel_key = text_key(row.get("vessel_type"))
    proxy_zone_key = text_key(zone_profile.get("business_proxy_zone", ""))

    exact_priority = context.zone_category_priority.get((zone_key, vessel_key))
    if exact_priority is None and proxy_zone_key:
        exact_priority = context.zone_category_priority.get((proxy_zone_key, vessel_key))
    category_priority = context.category_priority.get(vessel_key, 0.0)
    zone_priority = to_float(zone_profile.get("max_priority_score"), default=0)
    reference_priority = max(exact_priority or 0.0, category_priority, zone_priority)

    score = 0
    if reference_priority >= 85:
        score = 15
    elif reference_priority >= 70:
        score = 11
    elif reference_priority >= 50:
        score = 7
    elif reference_priority >= 35:
        score = 4
    if score:
        reasons.append("historique metier prioritaire")
    return score, reasons


def risk_level_from_score(score: int) -> str:
    if score >= 93:
        return "Risque critique"
    if score >= 85:
        return "Escalade op\u00e9rationnelle"
    if score >= 75:
        return "Risque \u00e9lev\u00e9"
    if score >= 60:
        return "Revue analyste"
    if score >= 50:
        return "Surveillance renforc\u00e9e"
    return "Veille contextuelle"


def recommended_action(score: int, risk_level: str) -> str:
    if risk_level == "Risque critique":
        return "Transmission immediate a une cellule analyste/operationnelle"
    if risk_level == "Escalade op\u00e9rationnelle":
        return "Escalade operationnelle apres validation humaine"
    if risk_level == "Risque \u00e9lev\u00e9":
        return "Prioriser la revue analyste"
    if risk_level == "Revue analyste":
        return "Qualifier par un analyste maritime"
    if score >= 50:
        return "Surveillance renforcee"
    return "Veille"


def is_immediate_review(row: dict[str, Any], final_score: int, risk_level: str, zone_risk: str) -> bool:
    ais_gap = to_int(row.get("ais_gap_minutes"))
    ais_cut = "interrompu" in clean_text(row.get("ais_status")).casefold()
    return (
        final_score >= 93
        or risk_level == "Risque critique"
        or (ais_cut and ais_gap >= 120 and zone_risk == "Critical" and to_bool(row.get("near_sensitive_zone")))
    )


def score_row(row: dict[str, Any], context: BusinessContext) -> dict[str, Any]:
    zone_profile = resolve_zone_profile(row.get("maritime_zone", ""), context)
    zone_risk = clean_text(zone_profile.get("effective_risk_level") or row.get("zone_risk_level") or "Unknown")
    vessel_score, vessel_reason = score_vessel_type(row.get("vessel_type", ""), to_bool(row.get("is_military")))
    geo_score, geo_reasons = score_geo(row, zone_profile)
    ais_score, ais_reasons = score_ais_behavior(row)
    legacy_score, legacy_reasons = score_legacy_business(row, zone_profile, context)
    zone_score = RISK_POINTS.get(zone_risk, RISK_POINTS.get(clean_text(row.get("zone_risk_level")), 0))
    quality = to_float(row.get("signal_quality"), default=0.8)
    signal_score = 4 if quality >= 0.85 else 2 if quality >= 0.65 else 0

    reasons = []
    if vessel_reason:
        reasons.append(vessel_reason)
    if zone_score:
        reasons.append(f"zone {zone_risk.lower()}")
    reasons.extend(geo_reasons)
    reasons.extend(ais_reasons)
    reasons.extend(legacy_reasons)

    final_score = min(100, int(round(vessel_score + geo_score + zone_score + ais_score + legacy_score + signal_score)))

    if (
        "interrompu" in clean_text(row.get("ais_status")).casefold()
        and to_int(row.get("ais_gap_minutes")) >= 120
        and zone_risk == "Critical"
        and to_bool(row.get("near_sensitive_zone"))
    ):
        final_score = max(final_score, 93)
        reasons.append("coupure AIS longue dans zone critique")

    if to_bool(row.get("near_sensitive_zone")) and text_key(row.get("behavior_label")) == "suspect" and to_float(row.get("nearest_vessel_distance_nm"), 999) <= 2.5:
        final_score = max(final_score, 85)
        reasons.append("signal suspect proche zone sensible et autre navire")

    risk_level = risk_level_from_score(final_score)
    immediate_review = is_immediate_review(row, final_score, risk_level, zone_risk)
    attention_required = final_score >= 50

    return {
        **row,
        "business_zone_reference": clean_text(zone_profile.get("business_proxy_zone") or zone_profile.get("zone_name") or row.get("maritime_zone")),
        "business_zone_risk": zone_risk,
        "business_max_priority_score": int(to_float(zone_profile.get("max_priority_score"), default=0)),
        "score_vessel": vessel_score,
        "score_geo": geo_score,
        "score_zone_risk": zone_score,
        "score_ais_behavior": ais_score,
        "score_legacy_business": legacy_score,
        "score_signal_quality": signal_score,
        "final_risk_score": final_score,
        "risk_level": risk_level,
        "attention_required": attention_required,
        "immediate_review_flag": immediate_review,
        "recommended_action": recommended_action(final_score, risk_level),
        "risk_reasons": "; ".join(dict.fromkeys(reasons)) if reasons else "aucun signal prioritaire",
        "scoring_version": "ais-risk-v1",
    }


def build_risk_events(ais_path: Path, output_path: Path) -> pd.DataFrame:
    if not ais_path.exists():
        raise FileNotFoundError(
            f"Missing AIS input: {ais_path}. Run `python generate_ais_data.py` before scoring."
        )

    context = load_business_context(ROOT)
    ais = pd.read_csv(ais_path, encoding="utf-8-sig")
    ais = ais.fillna("")
    rows = [{clean_text(key): value for key, value in row.items()} for row in ais.to_dict(orient="records")]
    scored_rows = [score_row(row, context) for row in rows]
    scored = pd.DataFrame(scored_rows)
    if scored.empty:
        alerts = scored
    else:
        alerts = scored[scored["attention_required"] == True].copy()
        alerts = alerts.sort_values(["final_risk_score", "immediate_review_flag", "timestamp_utc"], ascending=[False, False, False])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    alerts.to_csv(output_path, index=False, encoding="utf-8-sig")
    return alerts


def main() -> None:
    parser = argparse.ArgumentParser(description="Cross simulated AIS data with existing maritime business scoring.")
    parser.add_argument("--ais-input", type=Path, default=DEFAULT_AIS_INPUT, help="Input simulated AIS CSV path.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output alerts CSV path.")
    args = parser.parse_args()

    ais_path = args.ais_input if args.ais_input.is_absolute() else ROOT / args.ais_input
    output_path = args.output if args.output.is_absolute() else ROOT / args.output
    alerts = build_risk_events(ais_path, output_path)

    print(f"Risk events written to: {output_path}")
    print(f"Alerts: {len(alerts)}")
    if not alerts.empty:
        print(f"Critical alerts: {(alerts['risk_level'] == 'Risque critique').sum()}")
        print(f"Maximum score: {int(alerts['final_risk_score'].max())}")
        print("Top zones:")
        print(alerts["maritime_zone"].value_counts().head(5).to_string())


if __name__ == "__main__":
    main()
