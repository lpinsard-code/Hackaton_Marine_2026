from __future__ import annotations

import argparse
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data_generated"
DEFAULT_OUTPUT = DATA_DIR / "ais_signals_simulated.csv"
DEFAULT_SEED = 20260513


STRATEGIC_ZONES: list[dict[str, Any]] = [
    {
        "name": "D\u00e9troit d'Ormuz",
        "center_lat": 26.45,
        "center_lon": 56.25,
        "sensitive_lat": 26.0,
        "sensitive_lon": 56.0,
        "radius_km": 95,
        "risk_level": "Critical",
        "ais_cut_probability": 0.22,
        "suspect_probability": 0.34,
    },
    {
        "name": "Mer Rouge",
        "center_lat": 19.4,
        "center_lon": 38.7,
        "sensitive_lat": 18.8,
        "sensitive_lon": 39.0,
        "radius_km": 160,
        "risk_level": "High",
        "ais_cut_probability": 0.16,
        "suspect_probability": 0.28,
    },
    {
        "name": "M\u00e9diterran\u00e9e orientale",
        "center_lat": 34.5,
        "center_lon": 32.7,
        "sensitive_lat": 34.9,
        "sensitive_lon": 33.2,
        "radius_km": 150,
        "risk_level": "High",
        "ais_cut_probability": 0.13,
        "suspect_probability": 0.22,
    },
    {
        "name": "Mer Noire",
        "center_lat": 43.4,
        "center_lon": 34.0,
        "sensitive_lat": 44.6,
        "sensitive_lon": 33.5,
        "radius_km": 190,
        "risk_level": "High",
        "ais_cut_probability": 0.15,
        "suspect_probability": 0.25,
    },
    {
        "name": "D\u00e9troit de Ta\u00efwan",
        "center_lat": 24.35,
        "center_lon": 120.85,
        "sensitive_lat": 24.7,
        "sensitive_lon": 121.0,
        "radius_km": 110,
        "risk_level": "Critical",
        "ais_cut_probability": 0.24,
        "suspect_probability": 0.36,
    },
]


VESSEL_TYPES: list[dict[str, Any]] = [
    {"type": "Destroyer", "group": "combat_strategique", "is_military": True, "speed": (12, 28), "weight": 7},
    {"type": "Fr\u00e9gate", "group": "combat", "is_military": True, "speed": (11, 26), "weight": 9},
    {"type": "Sous-marin", "group": "combat_strategique", "is_military": True, "speed": (3, 15), "weight": 5},
    {"type": "Croiseur", "group": "combat_strategique", "is_military": True, "speed": (12, 27), "weight": 4},
    {"type": "Corvette", "group": "combat", "is_military": True, "speed": (10, 24), "weight": 6},
    {
        "type": "B\u00e2timent de d\u00e9barquement",
        "group": "soutien_ou_amphibie",
        "is_military": True,
        "speed": (8, 18),
        "weight": 4,
    },
    {"type": "Navire de soutien", "group": "soutien_ou_amphibie", "is_military": True, "speed": (7, 18), "weight": 5},
    {"type": "Cargo", "group": "civil", "is_military": False, "speed": (8, 18), "weight": 18},
    {"type": "P\u00e9trolier", "group": "civil", "is_military": False, "speed": (6, 15), "weight": 15},
    {"type": "Porte-conteneurs", "group": "civil", "is_military": False, "speed": (10, 20), "weight": 12},
    {"type": "Chalutier", "group": "civil", "is_military": False, "speed": (1, 9), "weight": 10},
    {"type": "Navire civil", "group": "civil", "is_military": False, "speed": (6, 17), "weight": 10},
]


FLAG_COUNTRIES = [
    "France",
    "Greece",
    "Panama",
    "Liberia",
    "Singapore",
    "Norway",
    "Turkey",
    "India",
    "China",
    "Taiwan",
    "Marshall Islands",
]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def offset_position(
    center_lat: float,
    center_lon: float,
    radius_km: float,
    rng: np.random.Generator,
) -> tuple[float, float]:
    bearing = rng.uniform(0, 2 * math.pi)
    distance = radius_km * math.sqrt(rng.uniform(0, 1))
    delta_lat = (distance / 111.0) * math.cos(bearing)
    delta_lon = (distance / (111.0 * max(0.2, math.cos(math.radians(center_lat))))) * math.sin(bearing)
    return center_lat + delta_lat, center_lon + delta_lon


def choose_weighted(items: list[dict[str, Any]], rng: np.random.Generator) -> dict[str, Any]:
    weights = np.array([float(item["weight"]) for item in items], dtype=float)
    index = int(rng.choice(len(items), p=weights / weights.sum()))
    return items[index]


def route_pattern(is_suspect: bool, ais_interrupted: bool, rng: np.random.Generator) -> str:
    if ais_interrupted:
        return str(rng.choice(["coupure AIS", "route sombre", "reapparition tardive"], p=[0.45, 0.35, 0.20]))
    if is_suspect:
        return str(rng.choice(["loitering", "variation de cap", "rendez-vous probable"], p=[0.38, 0.32, 0.30]))
    return str(rng.choice(["transit regulier", "approche portuaire", "patrouille declaree"], p=[0.55, 0.25, 0.20]))


def simulate_ais_signals(n_vessels: int, points_per_vessel: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    now_utc = datetime.now(timezone.utc).replace(microsecond=0)
    rows: list[dict[str, Any]] = []
    zone_weights = np.array([1.25, 1.05, 0.85, 0.95, 1.25], dtype=float)
    zone_weights = zone_weights / zone_weights.sum()

    for vessel_index in range(n_vessels):
        zone = STRATEGIC_ZONES[int(rng.choice(len(STRATEGIC_ZONES), p=zone_weights))]
        profile = choose_weighted(VESSEL_TYPES, rng)
        vessel_id = f"VES-{vessel_index + 1:04d}"
        mmsi = int(rng.integers(201000000, 775999999))
        name_prefix = "MN" if profile["is_military"] else str(rng.choice(["ATL", "OCEAN", "MER", "TRADE", "NORD"]))
        vessel_name = f"{name_prefix}-{rng.integers(100, 999)}"
        flag = "France" if profile["is_military"] and rng.random() < 0.35 else str(rng.choice(FLAG_COUNTRIES))
        base_lat, base_lon = offset_position(zone["center_lat"], zone["center_lon"], zone["radius_km"], rng)
        base_course = float(rng.uniform(0, 360))
        is_suspect_vessel = bool(rng.random() < zone["suspect_probability"])
        ais_interrupted_vessel = bool(rng.random() < zone["ais_cut_probability"] or (is_suspect_vessel and rng.random() < 0.35))
        first_timestamp = now_utc - timedelta(hours=float(rng.uniform(3, 36)))

        for point_index in range(points_per_vessel):
            timestamp = first_timestamp + timedelta(minutes=point_index * int(rng.integers(18, 95)))
            drift_km = point_index * rng.uniform(2.5, 13.5)
            drift_lat = (drift_km / 111.0) * math.cos(math.radians(base_course))
            drift_lon = (drift_km / (111.0 * max(0.2, math.cos(math.radians(base_lat))))) * math.sin(
                math.radians(base_course)
            )
            jitter_lat, jitter_lon = offset_position(0.0, 0.0, 7.0 if is_suspect_vessel else 3.5, rng)
            lat = base_lat + drift_lat + jitter_lat
            lon = base_lon + drift_lon + jitter_lon

            low_speed, high_speed = profile["speed"]
            speed = float(rng.uniform(low_speed, high_speed))
            if is_suspect_vessel and rng.random() < 0.36:
                speed = float(rng.choice([rng.uniform(0.2, 2.2), rng.uniform(high_speed + 2, high_speed + 9)]))

            course_change = abs(float(rng.normal(15, 10)))
            if is_suspect_vessel and rng.random() < 0.45:
                course_change = float(rng.uniform(65, 175))
            course = (base_course + rng.normal(0, 18) + point_index * rng.normal(1, 5) + course_change / 6) % 360

            interrupted_here = ais_interrupted_vessel and point_index >= max(1, points_per_vessel // 2)
            ais_gap_minutes = 0
            if interrupted_here:
                ais_gap_minutes = int(rng.choice([30, 45, 90, 120, 180, 240, 360], p=[0.10, 0.13, 0.18, 0.19, 0.18, 0.14, 0.08]))

            distance_sensitive = haversine_km(lat, lon, zone["sensitive_lat"], zone["sensitive_lon"])
            near_sensitive = bool(distance_sensitive <= 45 if zone["risk_level"] == "Critical" else distance_sensitive <= 60)
            if is_suspect_vessel:
                nearest_vessel_distance_nm = float(rng.uniform(0.15, 3.8))
                nearby_vessel_count = int(rng.integers(1, 6))
            else:
                nearest_vessel_distance_nm = float(rng.uniform(3.5, 28.0))
                nearby_vessel_count = int(rng.choice([0, 0, 1, 1, 2]))

            signal_quality = float(np.clip(rng.normal(0.88 if not interrupted_here else 0.54, 0.12), 0.2, 0.99))
            pattern = route_pattern(is_suspect_vessel, interrupted_here, rng)

            behavior_flags: list[str] = []
            if interrupted_here:
                behavior_flags.append("coupure AIS")
            if near_sensitive and is_suspect_vessel:
                behavior_flags.append("proximite zone sensible")
            if nearest_vessel_distance_nm < 2.0:
                behavior_flags.append("proximite autre navire")
            if course_change >= 70:
                behavior_flags.append("variation cap forte")
            if speed <= 2.5 and near_sensitive:
                behavior_flags.append("stationnement lent")
            if speed > high_speed + 2:
                behavior_flags.append("vitesse atypique")

            behavior_label = "suspect" if behavior_flags else "normal"
            rows.append(
                {
                    "ais_event_id": f"AIS-{vessel_index + 1:04d}-{point_index + 1:02d}",
                    "vessel_id": vessel_id,
                    "mmsi": mmsi,
                    "vessel_name": vessel_name,
                    "vessel_type": profile["type"],
                    "vessel_group": profile["group"],
                    "is_military": bool(profile["is_military"]),
                    "flag_country": flag,
                    "timestamp_utc": timestamp.isoformat(),
                    "latitude": round(lat, 5),
                    "longitude": round(lon, 5),
                    "speed_knots": round(speed, 2),
                    "course_deg": round(course, 1),
                    "course_change_deg": round(course_change, 1),
                    "ais_status": "Interrompu" if interrupted_here else "Actif",
                    "ais_gap_minutes": ais_gap_minutes,
                    "maritime_zone": zone["name"],
                    "zone_risk_level": zone["risk_level"],
                    "sensitive_zone_name": zone["name"],
                    "sensitive_zone_distance_km": round(distance_sensitive, 2),
                    "near_sensitive_zone": near_sensitive,
                    "nearest_vessel_distance_nm": round(nearest_vessel_distance_nm, 2),
                    "nearby_vessel_count": nearby_vessel_count,
                    "route_pattern": pattern,
                    "signal_quality": round(signal_quality, 3),
                    "behavior_label": behavior_label,
                    "behavior_flags": "; ".join(behavior_flags) if behavior_flags else "aucun",
                    "simulation_seed": seed,
                }
            )

    data = pd.DataFrame(rows)
    return data.sort_values(["timestamp_utc", "vessel_id", "ais_event_id"]).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate credible simulated AIS signals for strategic maritime zones.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output CSV path.")
    parser.add_argument("--vessels", type=int, default=78, help="Number of simulated vessels.")
    parser.add_argument("--points-per-vessel", type=int, default=5, help="Number of AIS points per vessel.")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="Deterministic simulation seed.")
    args = parser.parse_args()

    if args.vessels <= 0:
        raise ValueError("--vessels must be positive.")
    if args.points_per_vessel <= 0:
        raise ValueError("--points-per-vessel must be positive.")

    output_path = args.output if args.output.is_absolute() else ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    data = simulate_ais_signals(args.vessels, args.points_per_vessel, args.seed)
    data.to_csv(output_path, index=False, encoding="utf-8-sig")

    print(f"AIS simulated signals written to: {output_path}")
    print(f"Rows: {len(data)} | Vessels: {data['vessel_id'].nunique()} | Zones: {data['maritime_zone'].nunique()}")
    print(f"Interrupted AIS signals: {(data['ais_status'] == 'Interrompu').sum()}")
    print(f"Suspect behavior signals: {(data['behavior_label'] == 'suspect').sum()}")


if __name__ == "__main__":
    main()
