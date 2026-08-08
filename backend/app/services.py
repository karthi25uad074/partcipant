"""Domain services: feature engineering, agronomic maths and the recommendation engine."""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone
from statistics import mean, pstdev
from typing import Any, Dict, List, Optional

import numpy as np

from .config import CROP_LIBRARY, PEST_LIBRARY, SOIL_LIBRARY
from .dataset import growth_stage
from .i18n import translate, ui
from .ml import CROP_CODES, get_engine
from .repository import Repository

TODAY = date(2026, 8, 7)


# --------------------------------------------------------------------------- #
#  Series helpers
# --------------------------------------------------------------------------- #
def _sorted(rows: List[Dict[str, Any]], key: str) -> List[Dict[str, Any]]:
    return sorted(rows, key=lambda r: r.get(key) or "")


def sensor_series(repo: Repository, plot_id: str, days: int = 60) -> List[Dict[str, Any]]:
    return _sorted(repo.where("sensor_readings", plot_id=plot_id), "ts")[-days:]


def satellite_series(repo: Repository, plot_id: str, days: int = 120) -> List[Dict[str, Any]]:
    rows = _sorted(repo.where("satellite_scenes", plot_id=plot_id), "capture_date")
    return [r for r in rows if r["capture_date"] >= (TODAY - timedelta(days=days)).isoformat()]


def forecast_series(repo: Repository, plot_id: str) -> List[Dict[str, Any]]:
    return _sorted(repo.where("weather_forecast", plot_id=plot_id), "forecast_date")


def _slope_per_day(dates: List[str], values: List[float]) -> float:
    if len(values) < 3:
        return 0.0
    x = np.array([(datetime.fromisoformat(d).date() - TODAY).days for d in dates], dtype=float)
    y = np.array(values, dtype=float)
    return float(np.polyfit(x, y, 1)[0])


# --------------------------------------------------------------------------- #
#  Vegetation indices — computed from raw band reflectance (auditable)
# --------------------------------------------------------------------------- #
def compute_indices(blue: float, red: float, nir: float, swir: float) -> Dict[str, float]:
    ndvi = (nir - red) / max(nir + red, 1e-6)
    evi = 2.5 * (nir - red) / max(nir + 6 * red - 7.5 * blue + 1, 1e-6)
    savi = 1.5 * (nir - red) / max(nir + red + 0.5, 1e-6)
    ndwi = (nir - swir) / max(nir + swir, 1e-6)
    msavi = (2 * nir + 1 - math.sqrt(max((2 * nir + 1) ** 2 - 8 * (nir - red), 0))) / 2
    gci = nir / max(red, 1e-6) - 1
    lai = -2.0 * math.log(max(1 - min(ndvi, 0.97), 0.02)) * 0.72
    return {
        "ndvi": round(float(np.clip(ndvi, -1, 1)), 4),
        "evi": round(float(np.clip(evi, -1, 1.5)), 4),
        "savi": round(float(np.clip(savi, -1, 1.5)), 4),
        "ndwi": round(float(np.clip(ndwi, -1, 1)), 4),
        "msavi": round(float(np.clip(msavi, -1, 1.5)), 4),
        "chlorophyll_index": round(float(np.clip(gci, 0, 20)), 3),
        "lai": round(float(np.clip(lai, 0, 8)), 3),
        "formulas": {
            "ndvi": "(NIR - RED) / (NIR + RED)",
            "evi": "2.5 * (NIR - RED) / (NIR + 6*RED - 7.5*BLUE + 1)",
            "savi": "1.5 * (NIR - RED) / (NIR + RED + 0.5)",
            "ndwi": "(NIR - SWIR) / (NIR + SWIR)",
            "msavi": "(2*NIR + 1 - sqrt((2*NIR+1)^2 - 8*(NIR-RED))) / 2",
            "lai": "-2 * ln(1 - NDVI) * 0.72  (Beer-Lambert approximation)",
        },
    }


# --------------------------------------------------------------------------- #
#  Feature vector for every model
# --------------------------------------------------------------------------- #
def build_features(repo: Repository, plot: Dict[str, Any]) -> Dict[str, Any]:
    sens = sensor_series(repo, plot["id"], 90)
    sat = satellite_series(repo, plot["id"], 120)
    fc = forecast_series(repo, plot["id"])
    soil = SOIL_LIBRARY[plot["soil_type"]]
    crop = CROP_LIBRARY[plot["crop"]]
    hist = repo.where("cultivation_history", plot_id=plot["id"])

    ndvi_vals = [s["ndvi"] for s in sat] or [0.4]
    ndvi_dates = [s["capture_date"] for s in sat] or [TODAY.isoformat()]
    recent = [(d, v) for d, v in zip(ndvi_dates, ndvi_vals)
              if d >= (TODAY - timedelta(days=30)).isoformat()]
    # `ndvi_mean` must describe *current canopy condition* (the definition the
    # models were trained on), not the whole-season average, which is dragged
    # down by bare-soil scenes from before emergence.
    recent_ndvi = [v for _, v in recent] or ndvi_vals[-3:]

    last30 = sens[-30:] or sens
    last7 = sens[-7:] or sens
    last3 = sens[-3:] or sens
    tmean = mean([(r["air_temp_max"] + r["air_temp_min"]) / 2 for r in last30]) if last30 else 28.0
    gdd = sum(max(((r["air_temp_max"] + r["air_temp_min"]) / 2) - crop["base_temp"], 0) for r in sens)

    moisture = last7[-1]["soil_moisture"] if last7 else soil["fc"] * 0.8
    deficit = max(soil["fc"] - moisture, 0.0)
    drainage = float(np.clip(soil["infiltration"] / 35.0, 0.05, 1.0))
    elevation_idx = float(np.clip((plot["centroid_lat"] - 8.0) / 3.0 + (0.25 if "Hill" in plot["name"] else 0.0), 0, 1))
    if "Kuttanad" in plot["name"] or "Backwater" in plot["name"]:
        elevation_idx = 0.04
    hist_ndvi = [h["mean_ndvi"] for h in hist] or [0.6]

    feats = {
        "crop_code": float(CROP_CODES[plot["crop"]]),
        "ndvi_mean": round(float(mean(recent_ndvi)), 4),
        "ndvi_peak": round(float(max(ndvi_vals)), 4),
        "ndvi_latest": round(float(ndvi_vals[-1]), 4),
        "ndvi_trend": round(_slope_per_day([d for d, _ in recent], [v for _, v in recent]) * 30, 4),
        "ndwi_mean": round(float(mean([s["ndwi"] for s in sat])) if sat else 0.25, 4),
        "lai": round(float(sat[-1]["lai"]) if sat else 1.5, 3),
        # Season-equivalent rainfall: to-date total extrapolated across the full
        # crop duration so it is comparable with training data and with the
        # season totals stored in cultivation_history.
        "rainfall_mm": round(float(sum(r["rainfall_mm"] for r in sens))
                             * crop["duration_days"]
                             / max(plot.get("days_after_sowing") or 1, 20), 1),
        "rain_3d": round(float(sum(r["rainfall_mm"] for r in last3)), 1),
        "rain_7d": round(float(sum(r["rainfall_mm"] for r in last7)), 1),
        "rain_fc_3d": round(float(sum(r["rainfall_mm"] for r in fc[:3])), 1),
        "rain_fc_7d": round(float(sum(r["rainfall_mm"] for r in fc[:7])), 1),
        "gdd": round(float(gdd), 1),
        "soil_moisture": round(float(moisture), 4),
        "moisture_deficit": round(float(deficit), 4),
        "soil_ph": round(float(last7[-1]["soil_ph"]) if last7 else 6.5, 2),
        "soil_ec": round(float(last7[-1]["soil_ec"]) if last7 else 0.5, 3),
        "temp_mean": round(float(tmean), 2),
        "humidity": round(float(mean([r["humidity"] for r in last7])) if last7 else 75.0, 1),
        "leaf_wetness": round(float(mean([r["leaf_wetness_hr"] for r in last7])) if last7 else 8.0, 1),
        "wind_kph": round(float(mean([r["wind_kph"] for r in last7])) if last7 else 8.0, 1),
        "et0": round(float(mean([r["et0_mm"] for r in last7])) if last7 else 4.5, 2),
        "fert_n": round(float(mean([h["fertilizer_n_kg_ha"] for h in hist])) if hist else crop["n_p_k"][0], 1),
        "irrigation_mm": round(float(mean([h["irrigation_mm"] for h in hist])) if hist else 400.0, 1),
        "drainage_score": round(drainage, 3),
        "elevation_idx": round(elevation_idx, 3),
    }
    hist_sd = pstdev(hist_ndvi) if len(hist_ndvi) > 1 else 0.05
    feats.update({
        "ndvi_anomaly": round(float(np.clip(
            (feats["ndvi_mean"] - mean(hist_ndvi)) / max(hist_sd, 0.04), -4.0, 4.0)), 3),
        "temp_anomaly": round((feats["temp_mean"] - 28.5) / 3.0, 3),
        "rain_anomaly": round((feats["rainfall_mm"] - 1150) / 480, 3),
        "humidity_anomaly": round((feats["humidity"] - 76) / 12, 3),
    })
    return feats


# --------------------------------------------------------------------------- #
#  Crop health & soil quality
# --------------------------------------------------------------------------- #
def crop_health(plot: Dict[str, Any], f: Dict[str, Any]) -> Dict[str, Any]:
    stage = plot["growth_stage"]
    expected = {"initial": 0.30, "development": 0.58, "mid": 0.76, "late": 0.55}[stage]
    vigour = float(np.clip(f["ndvi_latest"] / expected, 0.25, 1.25))
    water = float(np.clip((f["ndwi_mean"] + 0.2) / 0.6, 0, 1))
    canopy = float(np.clip(f["lai"] / 4.0, 0, 1))
    trend = float(np.clip((f["ndvi_trend"] + 0.08) / 0.16, 0, 1))
    score = 100 * (0.42 * min(vigour, 1.0) + 0.20 * water + 0.20 * canopy + 0.18 * trend)
    score = round(float(np.clip(score, 4, 99)), 1)
    band = ("Excellent" if score >= 78 else "Good" if score >= 62
            else "Moderate" if score >= 45 else "Poor" if score >= 30 else "Critical")
    return {
        "score": score, "band": band,
        "vigour_ratio": round(vigour, 3),
        "expected_ndvi_for_stage": expected,
        "components": [
            {"name": "Canopy vigour (NDVI vs stage norm)", "value": round(min(vigour, 1.0) * 100, 1), "weight": 42},
            {"name": "Canopy water status (NDWI)", "value": round(water * 100, 1), "weight": 20},
            {"name": "Leaf area development (LAI)", "value": round(canopy * 100, 1), "weight": 20},
            {"name": "30-day greenness trend", "value": round(trend * 100, 1), "weight": 18},
        ],
    }


def soil_quality(plot: Dict[str, Any], f: Dict[str, Any]) -> Dict[str, Any]:
    soil = SOIL_LIBRARY[plot["soil_type"]]
    lo, hi = soil["ideal_ph"]
    ph = f["soil_ph"]
    ph_score = 100.0 if lo <= ph <= hi else max(0.0, 100 - abs(ph - (lo if ph < lo else hi)) * 42)
    avail_water = max(f["soil_moisture"] - soil["pwp"], 0) / max(soil["fc"] - soil["pwp"], 1e-6)
    moisture_score = float(np.clip(avail_water, 0, 1) * 100)
    ec_score = 100.0 if f["soil_ec"] <= 1.0 else max(0.0, 100 - (f["soil_ec"] - 1.0) * 62)
    score = round(0.36 * ph_score + 0.40 * moisture_score + 0.24 * ec_score, 1)
    notes: List[str] = []
    if ph < lo:
        notes.append(f"Soil is acidic (pH {ph} vs ideal {lo}-{hi}). Apply agricultural lime "
                     f"{round((lo - ph) * 1.6, 1)} t/ha, 3 weeks before the next top-dress.")
    elif ph > hi:
        notes.append(f"Soil is alkaline (pH {ph} vs ideal {lo}-{hi}). Apply gypsum "
                     f"{round((ph - hi) * 1.2, 1)} t/ha and add organic matter.")
    else:
        notes.append(f"pH {ph} is inside the ideal {lo}-{hi} band for {plot['soil_type']} soil.")
    if f["soil_ec"] > 1.0:
        notes.append(f"EC {f['soil_ec']} dS/m indicates salt build-up — schedule a leaching irrigation.")
    notes.append(f"Plant-available water is {round(avail_water * 100)}% of the field capacity range "
                 f"({soil['pwp']:.2f}-{soil['fc']:.2f} v/v).")
    return {"score": score, "ph": ph, "ec": f["soil_ec"], "texture": plot["soil_type"],
            "field_capacity": soil["fc"], "wilting_point": soil["pwp"],
            "available_water_fraction": round(float(np.clip(avail_water, 0, 1)), 3),
            "sub_scores": {"ph": round(ph_score, 1), "moisture": round(moisture_score, 1), "salinity": round(ec_score, 1)},
            "notes": notes}


# --------------------------------------------------------------------------- #
#  Water requirement (FAO-56 dual water balance)
# --------------------------------------------------------------------------- #
def water_plan(repo: Repository, plot: Dict[str, Any], f: Dict[str, Any]) -> Dict[str, Any]:
    crop = CROP_LIBRARY[plot["crop"]]
    soil = SOIL_LIBRARY[plot["soil_type"]]
    kc = crop["kc"][plot["growth_stage"]]
    fc = forecast_series(repo, plot["id"])
    eff = {"Drip": 0.90, "Micro-sprinkler": 0.82, "Sprinkler": 0.75, "Basin": 0.65, "Flood": 0.55, "Rainfed": 1.0}
    app_eff = eff.get(plot["irrigation_type"], 0.7)

    taw = (soil["fc"] - soil["pwp"]) * crop["root_depth_mm"]          # total available water, mm
    raw = taw * 0.5                                                   # readily available water
    depletion = max((soil["fc"] - f["soil_moisture"]), 0) * crop["root_depth_mm"]

    schedule, running = [], depletion
    for day in fc:
        etc = round(day["et0_mm"] * kc, 2)
        p_eff = round(max(day["rainfall_mm"] * 0.78 - 2.0, 0.0), 2)    # USDA-SCS effective rainfall
        running = max(running + etc - p_eff, 0.0)
        irrigate = running >= raw
        # One event refills at most RAW (FAO-56 practice) — a deep deficit is
        # recovered over consecutive events instead of one unrealistic flood.
        net = round(min(running, raw), 1) if irrigate else 0.0
        gross = round(net / app_eff, 1) if irrigate else 0.0
        schedule.append({
            "date": day["forecast_date"], "etc_mm": etc, "et0_mm": day["et0_mm"], "kc": kc,
            "effective_rain_mm": p_eff, "depletion_mm": round(running, 1),
            "irrigate": irrigate, "net_mm": net, "gross_mm": gross,
            "litres": int(gross * 10_000 * plot["area_ha"]) if irrigate else 0,
            "minutes": min(int(gross / max(soil["infiltration"], 1) * 60), 180) if irrigate else 0,
            "reason": ("Root-zone depletion crosses the readily-available-water threshold"
                       if irrigate else "Depletion still below threshold — rainfall covers demand"),
        })
        if irrigate:
            running = max(running - net, 0.0)

    total_gross = round(sum(s["gross_mm"] for s in schedule), 1)
    flood_gross = round(total_gross * app_eff / 0.55, 1)
    return {
        "kc": kc, "growth_stage": plot["growth_stage"], "method": plot["irrigation_type"],
        "application_efficiency": app_eff,
        "total_available_water_mm": round(taw, 1), "readily_available_water_mm": round(raw, 1),
        "current_depletion_mm": round(depletion, 1),
        "next_irrigation": next((s["date"] for s in schedule if s["irrigate"]), None),
        "week_gross_mm": total_gross,
        "week_litres": int(total_gross * 10_000 * plot["area_ha"]),
        "water_saved_vs_flood_litres": int(max(flood_gross - total_gross, 0) * 10_000 * plot["area_ha"]),
        "water_saved_pct": round(max(flood_gross - total_gross, 0) / max(flood_gross, 1e-6) * 100, 1),
        "schedule": schedule,
    }


# --------------------------------------------------------------------------- #
#  Fertilizer engine
# --------------------------------------------------------------------------- #
def fertilizer_plan(plot: Dict[str, Any], f: Dict[str, Any], predicted_yield: float) -> Dict[str, Any]:
    crop = CROP_LIBRARY[plot["crop"]]
    n_t, p_t, k_t = crop["n_p_k"]
    yield_ratio = float(np.clip(predicted_yield / max(crop["potential_yield"], 1e-6), 0.35, 1.15))

    lo, hi = SOIL_LIBRARY[plot["soil_type"]]["ideal_ph"]
    ph_factor = 1.0 if lo <= f["soil_ph"] <= hi else 1 + min(abs(f["soil_ph"] - (lo if f["soil_ph"] < lo else hi)) * 0.09, 0.28)
    leach_factor = 1 + min(f["rainfall_mm"] / 4200, 0.22)          # monsoon nitrate leaching
    n_status = float(np.clip(f["ndvi_latest"] / max(0.01, {"initial": 0.30, "development": 0.58,
                                                           "mid": 0.76, "late": 0.55}[plot["growth_stage"]]), 0.4, 1.2))
    n_adj = 1 + (1 - n_status) * 0.42

    n = round(n_t * yield_ratio * n_adj * leach_factor, 1)
    p = round(p_t * yield_ratio * ph_factor, 1)
    k = round(k_t * yield_ratio * (1.08 if f["soil_ec"] < 0.5 else 1.0), 1)

    splits = {"initial": 0.25, "development": 0.35, "mid": 0.30, "late": 0.10}
    urea = round(n / 0.46, 1)
    dap = round(p / 0.46, 1)
    mop = round(k / 0.60, 1)
    urea_from_dap = round(dap * 0.18 / 0.46, 1)
    return {
        "season_target_kg_ha": {"N": n, "P2O5": p, "K2O": k},
        "plot_total_kg": {"N": round(n * plot["area_ha"], 1), "P2O5": round(p * plot["area_ha"], 1),
                          "K2O": round(k * plot["area_ha"], 1)},
        "products_kg_ha": {"Urea (46-0-0)": max(round(urea - urea_from_dap, 1), 0),
                           "DAP (18-46-0)": dap, "MOP (0-0-60)": mop},
        "next_dose": {
            "stage": plot["growth_stage"],
            "share_pct": round(splits[plot["growth_stage"]] * 100, 0),
            "N_kg_ha": round(n * splits[plot["growth_stage"]], 1),
            "urea_kg_plot": round(max(urea - urea_from_dap, 0) * splits[plot["growth_stage"]] * plot["area_ha"], 1),
            "window": f"{(TODAY + timedelta(days=2)).isoformat()} to {(TODAY + timedelta(days=6)).isoformat()}",
        },
        "adjustments": [
            {"factor": "Yield-goal scaling", "multiplier": round(yield_ratio, 3),
             "why": f"AI-predicted yield {predicted_yield} t/ha against {crop['potential_yield']} t/ha potential"},
            {"factor": "Soil pH correction", "multiplier": round(ph_factor, 3),
             "why": f"pH {f['soil_ph']} vs ideal {lo}-{hi} changes phosphorus availability"},
            {"factor": "Monsoon leaching allowance", "multiplier": round(leach_factor, 3),
             "why": f"{f['rainfall_mm']} mm cumulative rain leaches nitrate below the root zone"},
            {"factor": "Canopy nitrogen status", "multiplier": round(n_adj, 3),
             "why": f"NDVI {f['ndvi_latest']} is {round(n_status * 100)}% of the stage norm"},
        ],
        "organic_substitution": {
            "farmyard_manure_t_ha": round(n * 0.20 / 5.0, 2),
            "note": "Substituting 20% of N through FYM (0.5% N) improves soil carbon and cuts fertilizer cost.",
        },
        "split_plan": [{"stage": s.title(), "share_pct": round(v * 100),
                        "N_kg_ha": round(n * v, 1), "K2O_kg_ha": round(k * v, 1)} for s, v in splits.items()],
    }


# --------------------------------------------------------------------------- #
#  Pest & disease
# --------------------------------------------------------------------------- #
def pest_assessment(plot: Dict[str, Any], f: Dict[str, Any], base_prob: float,
                    disease_prob: float) -> List[Dict[str, Any]]:
    out = []
    for pest in PEST_LIBRARY.get(plot["crop"], []):
        t_lo, t_hi = pest["temp"]
        h_lo, h_hi = pest["humidity"]
        t_fit = 1.0 if t_lo <= f["temp_mean"] <= t_hi else max(0.0, 1 - min(abs(f["temp_mean"] - (t_lo if f["temp_mean"] < t_lo else t_hi)) / 7, 1))
        h_fit = 1.0 if h_lo <= f["humidity"] <= h_hi else max(0.0, 1 - min(abs(f["humidity"] - (h_lo if f["humidity"] < h_lo else h_hi)) / 22, 1))
        stage_fit = 1.0 if pest["stage"] == plot["growth_stage"] else 0.55
        is_disease = any(k in pest["name"] for k in ("Spot", "Wilt", "Mosaic", "Blight"))
        prob = (disease_prob if is_disease else base_prob) * (0.32 + 0.68 * t_fit * h_fit * stage_fit)
        prob = round(float(np.clip(prob, 0.01, 0.98)), 3)
        out.append({
            "name": pest["name"], "type": "Disease" if is_disease else "Insect pest",
            "risk": prob,
            "level": "High" if prob >= 0.6 else "Medium" if prob >= 0.32 else "Low",
            "window": f"{TODAY.isoformat()} to {(TODAY + timedelta(days=10)).isoformat()}",
            "control": pest["control"],
            "envelope": {"temp_c": list(pest["temp"]), "humidity_pct": list(pest["humidity"]),
                         "favoured_stage": pest["stage"]},
            "fit": {"temperature": round(t_fit, 2), "humidity": round(h_fit, 2), "stage": round(stage_fit, 2)},
        })
    return sorted(out, key=lambda p: p["risk"], reverse=True)


# --------------------------------------------------------------------------- #
#  Bonus modules
# --------------------------------------------------------------------------- #
def carbon_footprint(plot: Dict[str, Any], fert: Dict[str, Any], water: Dict[str, Any]) -> Dict[str, Any]:
    n_kg = fert["plot_total_kg"]["N"]
    # IPCC 2019 refinement: 1% of applied N -> N2O-N; GWP100 of N2O = 273
    n2o = n_kg * 0.01 * 44 / 28 * 273
    urea_mfg = fert["products_kg_ha"]["Urea (46-0-0)"] * plot["area_ha"] * 3.1
    pump_kwh = water["week_litres"] / 1000 * 0.35 * 20                    # season proxy
    pump_co2 = pump_kwh * 0.71                                            # CEA India grid factor
    ch4 = 1.30 * plot["area_ha"] * 120 * 25 if plot["crop"] == "Rice" else 0.0
    total = n2o + urea_mfg + pump_co2 + ch4
    return {
        "total_kg_co2e": round(total, 1),
        "per_hectare": round(total / max(plot["area_ha"], 1e-6), 1),
        "breakdown": [
            {"source": "Soil N2O from fertilizer N", "kg_co2e": round(n2o, 1)},
            {"source": "Urea manufacturing (embedded)", "kg_co2e": round(urea_mfg, 1)},
            {"source": "Irrigation pumping electricity", "kg_co2e": round(pump_co2, 1)},
            {"source": "Paddy CH4 (anaerobic soil)", "kg_co2e": round(ch4, 1)},
        ],
        "mitigation": [
            "Alternate wetting and drying in paddy cuts CH4 by 30-48%.",
            "Split nitrogen into 4 doses with a leaf-colour chart to lower N2O.",
            "Shift pumping to a solar day-time window to remove grid emissions.",
        ],
        "factors_source": "IPCC 2019 Refinement Vol.4 Ch.11; CEA India grid emission factor 0.71 kg CO2/kWh",
    }


def price_forecast(repo: Repository, crop: str, horizon: int = 14) -> Dict[str, Any]:
    rows = _sorted([r for r in repo.table("market_prices") if r["crop"] == crop], "price_date")
    if not rows:
        return {"crop": crop, "history": [], "forecast": []}
    series = [r["modal_price_qtl"] for r in rows]
    # Holt's linear trend (double exponential smoothing)
    alpha, beta = 0.42, 0.18
    level, trend = series[0], series[1] - series[0]
    for v in series[1:]:
        prev = level
        level = alpha * v + (1 - alpha) * (level + trend)
        trend = beta * (level - prev) + (1 - beta) * trend
    resid = pstdev(series[-30:]) if len(series) > 30 else pstdev(series) or 1.0
    fc = []
    for h in range(1, horizon + 1):
        point = level + h * trend
        band = resid * math.sqrt(h) * 0.6
        fc.append({"date": (TODAY + timedelta(days=h)).isoformat(),
                   "price": round(point, 2), "low": round(point - band, 2), "high": round(point + band, 2)})
    return {
        "crop": crop, "mandi": rows[-1]["mandi"], "model": "Holt linear trend (alpha=0.42, beta=0.18)",
        "latest_price": rows[-1]["modal_price_qtl"],
        "trend_per_day": round(trend, 2),
        "history": [{"date": r["price_date"], "price": r["modal_price_qtl"]} for r in rows[-60:]],
        "forecast": fc,
        "signal": ("Hold — prices trending up, sell after the forecast window"
                   if trend > 0 else "Sell early — prices trending down"),
    }


# --------------------------------------------------------------------------- #
#  The orchestrator: full intelligence bundle for one plot
# --------------------------------------------------------------------------- #
def analyse_plot(repo: Repository, plot_id: str, lang: str = "en") -> Dict[str, Any]:
    plot = repo.one("plots", id=plot_id)
    if not plot:
        raise KeyError(plot_id)
    plot = {**plot, "growth_stage": growth_stage(plot["days_after_sowing"], plot["crop"])}
    farm = repo.one("farms", id=plot["farm_id"]) or {}
    eng = get_engine()
    f = build_features(repo, plot)

    y = eng.predict("yield", f)
    pest_p = eng.predict("pest", f)
    dis_p = eng.predict("disease", f)
    dro_p = eng.predict("drought", f)
    flo_p = eng.predict("flood", f)
    ano_p = eng.predict("anomaly", f)

    health = crop_health(plot, f)
    soil = soil_quality(plot, f)
    water = water_plan(repo, plot, f)
    fert = fertilizer_plan(plot, f, y["value"])
    pests = pest_assessment(plot, f, pest_p["value"], dis_p["value"])

    hist = _sorted(repo.where("cultivation_history", plot_id=plot_id), "year")
    hist_yields = [h["yield_t_ha"] for h in hist]
    hist_avg = round(mean(hist_yields), 2) if hist_yields else None
    sat = satellite_series(repo, plot_id)
    latest = sat[-1] if sat else {}

    predictions = {
        "yield": {**y, "value": round(y["value"], 3), "unit": "t/ha",
                  "plot_total_tonnes": round(y["value"] * plot["area_ha"], 2),
                  "historical_avg_t_ha": hist_avg,
                  "vs_history_pct": round((y["value"] - hist_avg) / hist_avg * 100, 1) if hist_avg else None,
                  "range": [round(y["value"] * (1 - (1 - y["confidence"]) * 1.6), 2),
                            round(y["value"] * (1 + (1 - y["confidence"]) * 1.6), 2)]},
        "pest_outbreak": pest_p, "disease_risk": dis_p,
        "drought_stress": dro_p, "flood_impact": flo_p, "climate_anomaly": ano_p,
    }

    risks = [
        {"key": "drought_stress", "label": "Drought stress", "score": dro_p["value"], "confidence": dro_p["confidence"]},
        {"key": "flood_impact", "label": "Flood / waterlogging", "score": flo_p["value"], "confidence": flo_p["confidence"]},
        {"key": "pest_outbreak", "label": "Pest outbreak", "score": pest_p["value"], "confidence": pest_p["confidence"]},
        {"key": "disease_risk", "label": "Fungal disease", "score": dis_p["value"], "confidence": dis_p["confidence"]},
        {"key": "climate_anomaly", "label": "Climate anomaly", "score": ano_p["value"], "confidence": ano_p["confidence"]},
    ]
    for r in risks:
        r["level"] = "High" if r["score"] >= 0.6 else "Medium" if r["score"] >= 0.32 else "Low"
    composite = round(float(np.average([r["score"] for r in risks], weights=[0.26, 0.22, 0.2, 0.18, 0.14])), 3)

    recs = build_recommendations(plot, f, health, soil, water, fert, pests, predictions, risks, lang)
    carbon = carbon_footprint(plot, fert, water)

    return {
        "plot": plot, "farm": farm, "features": f,
        "health": health, "soil": soil, "water": water, "fertilizer": fert,
        "pests": pests, "predictions": predictions,
        "risk": {"composite": composite,
                 "level": "High" if composite >= 0.55 else "Medium" if composite >= 0.3 else "Low",
                 "items": risks},
        "recommendations": recs,
        "carbon": carbon,
        "satellite": {"latest": latest, "series": [
            {"date": s["capture_date"], "ndvi": s["ndvi"], "evi": s["evi"], "savi": s["savi"],
             "ndwi": s["ndwi"], "lai": s["lai"], "cloud_pct": s["cloud_pct"]} for s in sat]},
        "sensors": [{"ts": s["ts"], "soil_moisture": s["soil_moisture"], "soil_ph": s["soil_ph"],
                     "air_temp_max": s["air_temp_max"], "air_temp_min": s["air_temp_min"],
                     "humidity": s["humidity"], "rainfall_mm": s["rainfall_mm"],
                     "et0_mm": s["et0_mm"], "soil_ec": s["soil_ec"]}
                    for s in sensor_series(repo, plot_id, 60)],
        "forecast": forecast_series(repo, plot_id),
        "history": hist,
        "market": price_forecast(repo, plot["crop"]),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "language": lang,
    }


# --------------------------------------------------------------------------- #
#  Recommendation engine (explainable, ranked, translatable)
# --------------------------------------------------------------------------- #
def build_recommendations(plot, f, health, soil, water, fert, pests, predictions, risks,
                          lang: str = "en") -> List[Dict[str, Any]]:
    recs: List[Dict[str, Any]] = []

    # Rule-based (deterministic agronomic) recommendations still declare the
    # method behind them, so the UI can always show provenance for every card.
    DEFAULT_METHOD = {
        "Irrigation": "FAO-56 dual-Kc water balance",
        "Fertilizer": "Yield-goal NPK balance",
        "Crop rotation": "Rotation rule base + N credit",
        "Harvest planning": "crop_yield",
        "Pest management": "pest_outbreak",
        "Climate adaptation": "disease_risk",
    }

    def add(category, title, action, confidence, drivers, evidence, priority, impact, model=None):
        recs.append({
            "id": f"{plot['id']}-{category.lower().replace(' ', '-')}-{len(recs) + 1}",
            "category": category, "title": title, "action": action,
            "action_localised": translate(action, lang),
            "title_localised": translate(title, lang),
            "confidence": round(float(confidence), 3),
            "priority": priority,
            "expected_impact": impact,
            "model": model or DEFAULT_METHOD.get(category, "rule base"),
            "supporting_indicators": drivers,
            "evidence": evidence,
        })

    # 1 -------------------------------------------------------- irrigation
    nxt = water["next_irrigation"]
    if nxt:
        day = next(s for s in water["schedule"] if s["date"] == nxt)
        add("Irrigation",
            f"Irrigate on {nxt} — {day['gross_mm']} mm ({day['litres']:,} L)",
            f"Run {plot['irrigation_type'].lower()} irrigation for about {day['minutes']} minutes on {nxt}, "
            f"applying {day['gross_mm']} mm gross. Skip if more than {round(day['etc_mm'], 1)} mm of rain falls first.",
            0.88,
            [f"Root-zone depletion {day['depletion_mm']} mm vs {water['readily_available_water_mm']} mm threshold",
             f"Crop coefficient Kc {water['kc']} at {plot['growth_stage']} stage",
             f"7-day forecast rainfall {f['rain_fc_7d']} mm"],
            {"method": "FAO-56 dual crop-coefficient soil water balance",
             "soil_moisture": f["soil_moisture"], "et0": f["et0"],
             "water_saved_vs_flood_litres": water["water_saved_vs_flood_litres"]},
            "High" if day["depletion_mm"] > water["readily_available_water_mm"] * 1.25 else "Medium",
            f"Saves {water['water_saved_pct']}% water versus flood irrigation")
    else:
        add("Irrigation", "No irrigation needed this week",
            f"Forecast rainfall of {f['rain_fc_7d']} mm covers crop water demand. Keep drains clear instead.",
            0.84,
            [f"Soil moisture {f['soil_moisture']} v/v is above the stress threshold",
             f"Forecast rainfall {f['rain_fc_7d']} mm over 7 days"],
            {"method": "FAO-56 water balance", "depletion_mm": water["current_depletion_mm"]},
            "Low", "Avoids over-irrigation and nutrient leaching")

    # 2 -------------------------------------------------------- fertilizer
    nd = fert["next_dose"]
    add("Fertilizer",
        f"Apply {nd['N_kg_ha']} kg N/ha ({nd['urea_kg_plot']} kg urea for this plot)",
        f"Top-dress {nd['urea_kg_plot']} kg urea across {plot['area_ha']} ha between {nd['window']}. "
        f"Band it 5 cm beside the plant row and irrigate lightly within 24 hours.",
        0.82,
        [a["why"] for a in fert["adjustments"]],
        {"season_target": fert["season_target_kg_ha"], "products": fert["products_kg_ha"],
         "organic_substitution": fert["organic_substitution"]},
        "High" if health["score"] < 62 else "Medium",
        f"Closes the gap to the {predictions['yield']['value']} t/ha yield goal")

    # 3 --------------------------------------------------- pest management
    if pests:
        top = pests[0]
        add("Pest management",
            f"{top['name']} risk is {top['level']} ({round(top['risk'] * 100)}%)",
            f"Scout 10 random plants per acre within 48 hours. If the threshold is crossed: {top['control']}",
            predictions["pest_outbreak"]["confidence"],
            [f"Mean temperature {f['temp_mean']} C sits in the {top['envelope']['temp_c']} C outbreak envelope",
             f"Relative humidity {f['humidity']}% vs favourable {top['envelope']['humidity_pct']}%",
             f"Leaf wetness {f['leaf_wetness']} hours/day",
             f"Wind {f['wind_kph']} kph (low wind favours hopper build-up)"],
            {"model": "RandomForest pest-outbreak classifier",
             "roc_auc": predictions["pest_outbreak"]["metrics"].get("roc_auc"),
             "all_pests": pests,
             "top_drivers": predictions["pest_outbreak"]["explanation"]["drivers"][:4]},
            "High" if top["risk"] >= 0.6 else "Medium" if top["risk"] >= 0.32 else "Low",
            "Protects 8-22% of yield when acted on inside the risk window",
            model="pest_outbreak")

    # 4 ------------------------------------------------- climate adaptation
    worst = max(risks, key=lambda r: r["score"])
    adapt = {
        "drought_stress": "Mulch the inter-row with 5 cm of crop residue, shift irrigation to pre-dawn, "
                          "and apply a 2% KNO3 foliar spray to keep stomata regulated.",
        "flood_impact": "Open 45 cm field drains on the lower boundary, delay the nitrogen top-dress "
                        "until 48 hours after water recedes, and raise nursery beds.",
        "pest_outbreak": "Install pheromone traps and conserve natural enemies before any chemical spray.",
        "disease_risk": "Improve canopy airflow by removing lower leaves and switch to a protectant fungicide schedule.",
        "climate_anomaly": "Re-check the sowing window for the next season and keep a short-duration "
                           "contingency variety ready.",
    }[worst["key"]]
    add("Climate adaptation", f"{worst['label']} is the dominant risk ({round(worst['score'] * 100)}%)",
        adapt, worst["confidence"],
        [f"{d['label']}: {d['value']} ({d['direction']} risk, {d['share_pct']}% of the decision)"
         for d in predictions[worst["key"]]["explanation"]["drivers"][:4]],
        {"composite_risk": risks, "anomaly_z_scores": {
            "ndvi": f["ndvi_anomaly"], "temperature": f["temp_anomaly"],
            "rainfall": f["rain_anomaly"], "humidity": f["humidity_anomaly"]}},
        "High" if worst["score"] >= 0.55 else "Medium", "Reduces exposure to the leading seasonal risk",
        model=worst["key"])

    # 5 ------------------------------------------------- harvest planning
    harvest = plot["expected_harvest_date"]
    add("Harvest planning", f"Target harvest around {harvest}",
        f"Plan {math.ceil(plot['area_ha'] / 1.2)} labour-days or one combine slot for {harvest}. "
        f"Expected output {predictions['yield']['plot_total_tonnes']} tonnes.",
        predictions["yield"]["confidence"],
        [f"{plot['days_after_sowing']} days after sowing, currently {plot['growth_stage']} stage",
         f"Predicted yield {predictions['yield']['value']} t/ha "
         f"(range {predictions['yield']['range'][0]}-{predictions['yield']['range'][1]})",
         f"Historical plot average {predictions['yield']['historical_avg_t_ha']} t/ha"],
        {"model": "GradientBoosting yield regressor",
         "r2": predictions["yield"]["metrics"].get("r2"),
         "mae_t_ha": predictions["yield"]["metrics"].get("mae"),
         "top_drivers": predictions["yield"]["explanation"]["drivers"][:5]},
        "Medium", "Aligns labour and transport with the AI yield estimate", model="crop_yield")

    # 6 --------------------------------------------------- crop rotation
    rot = CROP_LIBRARY[plot["crop"]]["rotation"]
    add("Crop rotation", f"Follow {plot['crop']} with {rot[0]}",
        f"After harvest, sow {rot[0]} (alternatives: {', '.join(rot[1:])}). It breaks the "
        f"{pests[0]['name'] if pests else 'pest'} cycle and restores soil nitrogen.",
        0.76,
        [f"Same crop has occupied this plot for {len(set(h['crop'] for h in [{'crop': plot['crop']}]))} recorded seasons",
         f"Soil pH {f['soil_ph']} suits the suggested rotation crop",
         f"Soil EC {f['soil_ec']} dS/m indicates {'salt stress' if f['soil_ec'] > 1 else 'no salinity constraint'}"],
        {"rotation_options": rot, "soil": soil["sub_scores"]},
        "Low", "Breaks pest cycles and adds 15-30 kg N/ha biologically")

    order = {"High": 0, "Medium": 1, "Low": 2}
    recs.sort(key=lambda r: (order[r["priority"]], -r["confidence"]))
    return recs


# --------------------------------------------------------------------------- #
#  SMS / IVR compression for low-bandwidth delivery
# --------------------------------------------------------------------------- #
def sms_digest(bundle: Dict[str, Any], lang: str = "en") -> Dict[str, Any]:
    plot, water = bundle["plot"], bundle["water"]
    top = bundle["recommendations"][0]
    y = bundle["predictions"]["yield"]
    pest = bundle["pests"][0] if bundle["pests"] else None
    lines = [
        f"AgriSense {plot['name']} ({plot['crop']})",
        f"Health {bundle['health']['score']}/100 {bundle['health']['band']}",
        f"Yield {y['value']} t/ha (conf {int(y['confidence'] * 100)}%)",
        (f"Irrigate {water['next_irrigation']} {water['schedule'][0]['gross_mm']}mm"
         if water["next_irrigation"] else "No irrigation needed 7d"),
        f"{pest['name']} risk is {pest['level']}" if pest else "No pest alert",
    ]
    action_en, action_local = top["title"], translate(top["title"], lang)
    body = " | ".join(lines + [f"{ui('action', 'en')}: {action_en}"])
    # The action line is translated on its own so the "Do:" prefix never gets
    # captured by a sentence pattern and reordered into the middle of the text.
    localised = " | ".join([translate(l, lang) for l in lines]
                          + [f"{ui('action', lang)}: {action_local}"])
    return {"lang": lang, "body": body, "body_localised": localised,
            "chars": len(localised), "segments": max(1, math.ceil(len(localised) / 160)),
            "payload_bytes": len(localised.encode("utf-8")),
            "channel": "SMS / IVR / USSD — works on a 2G feature phone"}
