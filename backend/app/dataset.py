"""Deterministic demonstration dataset.

Generates an agronomically plausible, fully reproducible (seed=42) dataset that
mirrors the Supabase schema 1:1. Used as:
  * the demo/offline data source when Supabase is not configured, and
  * the seed payload for `python -m app.seed` when Supabase *is* configured.
"""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List

import numpy as np

from .config import CROP_LIBRARY, SOIL_LIBRARY

SEED = 42
TODAY = date(2026, 8, 7)
HISTORY_DAYS = 120
FORECAST_DAYS = 10

# Six real Kerala / Tamil Nadu locations -> hyper-local micro-climate variety.
FARM_SPECS = [
    dict(id="farm-01", name="Chalakudy River Farm", owner="Karthikeyan Y", phone="+919000000001",
         village="Kizhake Chalakudi", district="Thrissur", state="Kerala",
         lat=10.3062, lon=76.3341, area_ha=3.2, soil="Alluvial", lang="ml"),
    dict(id="farm-02", name="Vellangallur Paddy Block", owner="Suresh Menon", phone="+919000000002",
         village="Vellangallur", district="Thrissur", state="Kerala",
         lat=10.2634, lon=76.2210, area_ha=5.8, soil="Clay Loam", lang="ml"),
    dict(id="farm-03", name="Athirappilly Upland Estate", owner="Nisha Thomas", phone="+919000000003",
         village="Athirappilly", district="Thrissur", state="Kerala",
         lat=10.2851, lon=76.5695, area_ha=4.1, soil="Laterite", lang="en"),
    dict(id="farm-04", name="Pollachi Dryland Unit", owner="Murugesan R", phone="+919000000004",
         village="Pollachi", district="Coimbatore", state="Tamil Nadu",
         lat=10.6589, lon=77.0088, area_ha=6.5, soil="Red Sandy", lang="ta"),
    dict(id="farm-05", name="Kuttanad Lowland Plot", owner="Ajith Kumar", phone="+919000000005",
         village="Kainakary", district="Alappuzha", state="Kerala",
         lat=9.4390, lon=76.3860, area_ha=7.4, soil="Clay Loam", lang="ml"),
    dict(id="farm-06", name="Kanyakumari Coastal Grove", owner="Leema Rani", phone="+919000000006",
         village="Thovalai", district="Kanyakumari", state="Tamil Nadu",
         lat=8.2350, lon=77.4900, area_ha=2.6, soil="Coastal Sandy", lang="ta"),
]

PLOT_SPECS = [
    dict(id="plot-01", farm="farm-01", name="North Paddy A1", crop="Rice", variety="Jyothi",
         area_ha=1.4, sown_days_ago=68, irrigation="Flood", stress=0.05),
    dict(id="plot-02", farm="farm-01", name="River Bank Banana", crop="Banana", variety="Nendran",
         area_ha=1.8, sown_days_ago=190, irrigation="Drip", stress=0.12),
    dict(id="plot-03", farm="farm-02", name="Block B Paddy", crop="Rice", variety="Uma",
         area_ha=3.0, sown_days_ago=42, irrigation="Flood", stress=0.28),
    dict(id="plot-04", farm="farm-02", name="Bund Tapioca", crop="Tapioca", variety="Sree Vijaya",
         area_ha=2.8, sown_days_ago=150, irrigation="Rainfed", stress=0.18),
    dict(id="plot-05", farm="farm-03", name="Hill Pepper Terrace", crop="Black Pepper", variety="Panniyur-1",
         area_ha=2.2, sown_days_ago=300, irrigation="Micro-sprinkler", stress=0.34),
    dict(id="plot-06", farm="farm-03", name="Coconut Belt C", crop="Coconut", variety="WCT",
         area_ha=1.9, sown_days_ago=340, irrigation="Basin", stress=0.10),
    dict(id="plot-07", farm="farm-04", name="Dryland Maize D2", crop="Maize", variety="CoH(M)-6",
         area_ha=3.4, sown_days_ago=58, irrigation="Drip", stress=0.52),
    dict(id="plot-08", farm="farm-04", name="Groundnut Strip", crop="Groundnut", variety="TMV-7",
         area_ha=3.1, sown_days_ago=64, irrigation="Sprinkler", stress=0.44),
    dict(id="plot-09", farm="farm-05", name="Kuttanad Punja Field", crop="Rice", variety="Jaya",
         area_ha=4.2, sown_days_ago=88, irrigation="Flood", stress=0.22),
    dict(id="plot-10", farm="farm-05", name="Backwater Coconut", crop="Coconut", variety="Kuttiyadi",
         area_ha=3.2, sown_days_ago=355, irrigation="Basin", stress=0.15),
    dict(id="plot-11", farm="farm-06", name="Coastal Banana Grove", crop="Banana", variety="Robusta",
         area_ha=1.3, sown_days_ago=215, irrigation="Drip", stress=0.30),
    dict(id="plot-12", farm="farm-06", name="Shoreline Groundnut", crop="Groundnut", variety="VRI-2",
         area_ha=1.3, sown_days_ago=52, irrigation="Sprinkler", stress=0.38),
]

MARKET_SPECS = [
    ("Rice", "Thrissur Mandi", 2380, 0.9), ("Banana", "Chalakudy Mandi", 4150, 2.4),
    ("Coconut", "Pollachi Mandi", 3420, 1.6), ("Maize", "Coimbatore Mandi", 2210, 1.1),
    ("Groundnut", "Nagercoil Mandi", 6180, 2.0), ("Black Pepper", "Kochi Spice Mkt", 62500, 3.1),
    ("Tapioca", "Alappuzha Mandi", 1780, 1.4),
]


# --------------------------------------------------------------------------- #
#  Helpers
# --------------------------------------------------------------------------- #
def _rng(offset: int = 0) -> np.random.Generator:
    return np.random.default_rng(SEED + offset)


def growth_stage(days_after_sowing: int, crop: str) -> str:
    duration = CROP_LIBRARY[crop]["duration_days"]
    frac = min(days_after_sowing / duration, 1.0)
    if frac < 0.20:
        return "initial"
    if frac < 0.45:
        return "development"
    if frac < 0.80:
        return "mid"
    return "late"


def _ndvi_curve(dap: int, crop: str, stress: float) -> float:
    """Double-logistic phenology curve, damped by a plot-level stress factor."""
    d = CROP_LIBRARY[crop]["duration_days"]
    x = max(dap, 0) / d
    green_up = 1 / (1 + math.exp(-14 * (x - 0.18)))
    senescence = 1 / (1 + math.exp(14 * (x - 0.86)))
    peak = 0.88 if crop in ("Rice", "Maize", "Banana", "Tapioca") else 0.78
    base = 0.14
    return round(max(0.05, min(0.95, base + (peak - base) * green_up * senescence * (1 - 0.45 * stress))), 4)


# --------------------------------------------------------------------------- #
#  Table builders
# --------------------------------------------------------------------------- #
def build_farms() -> List[Dict[str, Any]]:
    return [
        dict(id=f["id"], name=f["name"], owner_name=f["owner"], phone=f["phone"],
             village=f["village"], district=f["district"], state=f["state"],
             lat=f["lat"], lon=f["lon"], area_ha=f["area_ha"],
             soil_type=f["soil"], language=f["lang"])
        for f in FARM_SPECS
    ]


def build_plots() -> List[Dict[str, Any]]:
    farms = {f["id"]: f for f in FARM_SPECS}
    out = []
    for i, p in enumerate(PLOT_SPECS):
        farm = farms[p["farm"]]
        sowing = TODAY - timedelta(days=p["sown_days_ago"])
        dur = CROP_LIBRARY[p["crop"]]["duration_days"]
        # Small deterministic polygon around the farm centroid (~an actual field).
        jitter = 0.0032 + 0.0011 * (i % 3)
        clat = farm["lat"] + 0.0045 * ((i % 4) - 1.5)
        clon = farm["lon"] + 0.0045 * ((i % 3) - 1.0)
        ring = [
            [round(clon - jitter, 6), round(clat - jitter, 6)],
            [round(clon + jitter, 6), round(clat - jitter * 0.7, 6)],
            [round(clon + jitter * 1.1, 6), round(clat + jitter, 6)],
            [round(clon - jitter * 0.8, 6), round(clat + jitter * 0.9, 6)],
            [round(clon - jitter, 6), round(clat - jitter, 6)],
        ]
        out.append(dict(
            id=p["id"], farm_id=p["farm"], name=p["name"], crop=p["crop"], variety=p["variety"],
            area_ha=p["area_ha"], sowing_date=sowing.isoformat(),
            expected_harvest_date=(sowing + timedelta(days=dur)).isoformat(),
            days_after_sowing=p["sown_days_ago"],
            growth_stage=growth_stage(p["sown_days_ago"], p["crop"]),
            irrigation_type=p["irrigation"], soil_type=farm["soil"],
            centroid_lat=round(clat, 6), centroid_lon=round(clon, 6),
            geometry={"type": "Polygon", "coordinates": [ring]},
            stress_index=p["stress"],
        ))
    return out


def build_sensor_readings(plots: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Daily aggregated IoT node readings for the last HISTORY_DAYS days."""
    rows: List[Dict[str, Any]] = []
    for pi, plot in enumerate(plots):
        rng = _rng(100 + pi)
        soil = SOIL_LIBRARY[plot["soil_type"]]
        stress = plot["stress_index"]
        base_ph = float(np.mean(soil["ideal_ph"]) + rng.normal(0, 0.35) - 0.55 * stress)
        moisture = soil["fc"] * (0.95 - 0.25 * stress)
        for d in range(HISTORY_DAYS, 0, -1):
            day = TODAY - timedelta(days=d)
            doy = day.timetuple().tm_yday
            # South-west monsoon signal, weaker for the rain-shadow (Pollachi) plots
            monsoon = max(0.0, math.sin((doy - 150) / 365 * 2 * math.pi))
            shadow = 0.35 if plot["farm_id"] == "farm-04" else 1.0
            rain = float(max(0.0, rng.gamma(1.6, 9.0) * monsoon * shadow - 1.2))
            tmax = 30.5 + 3.6 * math.cos((doy - 120) / 365 * 2 * math.pi) - 0.05 * rain + rng.normal(0, 0.9)
            tmin = tmax - (7.5 + 2.0 * (1 - monsoon)) + rng.normal(0, 0.6)
            hum = float(np.clip(66 + 22 * monsoon + 0.35 * rain + rng.normal(0, 3.5), 38, 99))
            et0 = float(np.clip(0.0023 * (((tmax + tmin) / 2) + 17.8) * math.sqrt(max(tmax - tmin, 1)) * 15.5,
                                1.2, 8.0))
            moisture += rain * 0.0032 - et0 * 0.0042 * (1 + 0.5 * stress)
            moisture = float(np.clip(moisture, soil["pwp"] * 0.72, soil["fc"] * 1.04))
            rows.append(dict(
                plot_id=plot["id"], ts=day.isoformat(),
                soil_moisture=round(moisture, 4),
                soil_ph=round(float(np.clip(base_ph + rng.normal(0, 0.05), 4.2, 8.6)), 2),
                soil_temp=round(float(tmax - 3.2 + rng.normal(0, 0.5)), 2),
                soil_ec=round(float(np.clip(0.42 + 0.25 * stress + rng.normal(0, 0.05), 0.1, 2.4)), 3),
                air_temp_max=round(float(tmax), 2), air_temp_min=round(float(tmin), 2),
                humidity=round(hum, 1), rainfall_mm=round(rain, 2),
                wind_kph=round(float(np.clip(rng.gamma(2.0, 4.2) + 4 * monsoon, 1, 46)), 1),
                et0_mm=round(et0, 2),
                leaf_wetness_hr=round(float(np.clip(2 + 0.16 * hum - 6 + 0.25 * rain, 0, 24)), 1),
            ))
    return rows


def build_satellite_scenes(plots: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Sentinel-2 style 5-day revisit multispectral scenes with vegetation indices."""
    rows: List[Dict[str, Any]] = []
    for pi, plot in enumerate(plots):
        rng = _rng(300 + pi)
        for d in range(HISTORY_DAYS, -1, -5):
            day = TODAY - timedelta(days=d)
            dap = plot["days_after_sowing"] - d
            ndvi = _ndvi_curve(dap, plot["crop"], plot["stress_index"]) + float(rng.normal(0, 0.012))
            ndvi = round(float(np.clip(ndvi, 0.04, 0.95)), 4)
            # Surface reflectance consistent with the NDVI we just produced
            red = round(float(np.clip(0.30 * (1 - ndvi) + rng.normal(0, 0.006), 0.01, 0.4)), 4)
            nir = round(float(red * (1 + ndvi) / max(1 - ndvi, 0.05)), 4)
            blue = round(float(np.clip(red * 0.72 + rng.normal(0, 0.004), 0.005, 0.35)), 4)
            swir = round(float(np.clip(0.34 - 0.19 * ndvi + 0.09 * plot["stress_index"], 0.03, 0.45)), 4)
            evi = round(float(np.clip(2.5 * (nir - red) / (nir + 6 * red - 7.5 * blue + 1), -0.2, 1.2)), 4)
            savi = round(float((nir - red) / (nir + red + 0.5) * 1.5), 4)
            ndwi = round(float((nir - swir) / (nir + swir)), 4)
            ndre = round(float(np.clip(ndvi * 0.62 + rng.normal(0, 0.01), 0.02, 0.8)), 4)
            rows.append(dict(
                plot_id=plot["id"], capture_date=day.isoformat(), platform="Sentinel-2 L2A",
                tile_id=f"T43PGQ_{day.strftime('%Y%m%d')}",
                band_blue=blue, band_red=red, band_nir=nir, band_swir=swir,
                ndvi=ndvi, evi=evi, savi=savi, ndwi=ndwi, ndre=ndre,
                lai=round(float(np.clip(-2.0 * math.log(max(1 - ndvi, 0.02)) * 0.72, 0.05, 6.5)), 3),
                chlorophyll_index=round(float(np.clip(nir / max(red, 0.01) - 1, 0, 12)), 3),
                cloud_pct=round(float(np.clip(rng.gamma(1.4, 7.0), 0, 78)), 1),
                resolution_m=10,
            ))
    return rows


def build_weather_forecast(plots: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for pi, plot in enumerate(plots):
        rng = _rng(500 + pi)
        shadow = 0.30 if plot["farm_id"] == "farm-04" else 1.0
        for d in range(FORECAST_DAYS):
            day = TODAY + timedelta(days=d)
            doy = day.timetuple().tm_yday
            monsoon = max(0.0, math.sin((doy - 150) / 365 * 2 * math.pi))
            rain = float(max(0.0, rng.gamma(1.7, 8.5) * monsoon * shadow - 1.0))
            tmax = 30.8 + 3.4 * math.cos((doy - 120) / 365 * 2 * math.pi) - 0.05 * rain + rng.normal(0, 0.8)
            tmin = tmax - 7.8 + rng.normal(0, 0.5)
            hum = float(np.clip(66 + 21 * monsoon + 0.32 * rain + rng.normal(0, 3), 38, 99))
            rows.append(dict(
                plot_id=plot["id"], forecast_date=day.isoformat(),
                temp_max=round(float(tmax), 1), temp_min=round(float(tmin), 1),
                rainfall_mm=round(rain, 1), rain_probability=round(float(np.clip(monsoon * 88 + rng.normal(0, 9), 2, 97)), 0),
                humidity=round(hum, 1),
                wind_kph=round(float(np.clip(rng.gamma(2.1, 4.0) + 4 * monsoon, 1, 52)), 1),
                wind_dir="SW" if monsoon > 0.4 else "NE",
                et0_mm=round(float(np.clip(0.0023 * (((tmax + tmin) / 2) + 17.8) * math.sqrt(max(tmax - tmin, 1)) * 15.5, 1.2, 8.0)), 2),
                source="IMD + ECMWF blend (downscaled 1 km)",
            ))
    return rows


def build_cultivation_history(plots: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for pi, plot in enumerate(plots):
        rng = _rng(700 + pi)
        pot = CROP_LIBRARY[plot["crop"]]["potential_yield"]
        npk = CROP_LIBRARY[plot["crop"]]["n_p_k"]
        for back in range(6, 0, -1):
            year = TODAY.year - back
            factor = float(np.clip(rng.normal(0.80, 0.09) - 0.05 * (back == 3), 0.42, 0.99))
            rows.append(dict(
                plot_id=plot["id"], season="Kharif" if pi % 2 == 0 else "Rabi", year=year,
                crop=plot["crop"], variety=plot["variety"],
                yield_t_ha=round(pot * factor, 3),
                season_rainfall_mm=round(float(rng.normal(640 if plot["farm_id"] == "farm-04" else 1720, 230)), 1),
                fertilizer_n_kg_ha=round(float(npk[0] * rng.normal(0.92, 0.1)), 1),
                fertilizer_p_kg_ha=round(float(npk[1] * rng.normal(0.9, 0.12)), 1),
                fertilizer_k_kg_ha=round(float(npk[2] * rng.normal(0.9, 0.12)), 1),
                irrigation_mm=round(float(rng.normal(420, 90)), 1),
                mean_ndvi=round(float(np.clip(rng.normal(0.62 * (0.7 + 0.4 * factor), 0.04), 0.2, 0.9)), 4),
                pest_incidence=int(rng.integers(0, 3)),
            ))
    return rows


def build_market_prices() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for ci, (crop, mandi, base, vol) in enumerate(MARKET_SPECS):
        rng = _rng(900 + ci)
        price = base
        for d in range(90, -1, -1):
            day = TODAY - timedelta(days=d)
            price = float(price * (1 + rng.normal(0.0006, vol / 100)))
            rows.append(dict(crop=crop, mandi=mandi, price_date=day.isoformat(),
                             modal_price_qtl=round(price, 2),
                             min_price_qtl=round(price * 0.94, 2),
                             max_price_qtl=round(price * 1.07, 2),
                             arrivals_tonnes=round(float(np.clip(rng.gamma(3, 22), 4, 260)), 1)))
    return rows


def build_all() -> Dict[str, List[Dict[str, Any]]]:
    farms = build_farms()
    plots = build_plots()
    return {
        "farms": farms,
        "plots": plots,
        "sensor_readings": build_sensor_readings(plots),
        "satellite_scenes": build_satellite_scenes(plots),
        "weather_forecast": build_weather_forecast(plots),
        "cultivation_history": build_cultivation_history(plots),
        "market_prices": build_market_prices(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
