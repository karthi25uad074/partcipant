"""AgriSense API — FastAPI application entry point.

Run:  uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
Docs: http://localhost:8000/docs
"""
from __future__ import annotations

import time
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Literal, Optional

from fastapi import Body, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from . import services
from .config import APP_NAME, APP_VERSION, CROP_LIBRARY, SOIL_LIBRARY
from .dataset import build_all, growth_stage
from .i18n import SUPPORTED, translate, ui_strings
from .ml import get_engine
from .repository import get_repo

START = time.time()
_CACHE: Dict[str, Any] = {}
CACHE_TTL = 45.0


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_repo()      # tier-resolve the data source
    get_engine()    # train + warm the models
    yield


app = FastAPI(title=APP_NAME, version=APP_VERSION, lifespan=lifespan,
              description="Hyper-local climate intelligence and precision-agriculture decision support.")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.add_middleware(GZipMiddleware, minimum_size=600)   # low-bandwidth optimisation


# --------------------------------------------------------------------------- #
#  Fault tolerance: never return a 500 to a field device
# --------------------------------------------------------------------------- #
@app.exception_handler(Exception)
async def guard(request: Request, exc: Exception):
    return JSONResponse(status_code=422, content={
        "ok": False, "error": type(exc).__name__, "detail": str(exc)[:400],
        "hint": "The API degrades gracefully — retry, or use /api/offline-bundle for cached advisories.",
    })


def cached(key: str, producer):
    now = time.time()
    hit = _CACHE.get(key)
    if hit and now - hit[0] < CACHE_TTL:
        return hit[1]
    val = producer()
    _CACHE[key] = (now, val)
    return val


def bundle(plot_id: str, lang: str = "en") -> Dict[str, Any]:
    repo = get_repo()
    try:
        return cached(f"{plot_id}:{lang}", lambda: services.analyse_plot(repo, plot_id, lang))
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Plot '{plot_id}' not found")


# --------------------------------------------------------------------------- #
#  Models
# --------------------------------------------------------------------------- #
class IndexRequest(BaseModel):
    blue: float = Field(..., ge=0, le=1, description="Blue band surface reflectance (B2)")
    red: float = Field(..., ge=0, le=1, description="Red band surface reflectance (B4)")
    nir: float = Field(..., ge=0, le=1, description="NIR band surface reflectance (B8)")
    swir: float = Field(0.2, ge=0, le=1, description="SWIR band surface reflectance (B11)")


class PredictRequest(BaseModel):
    model: Literal["yield", "pest", "disease", "drought", "flood", "anomaly"]
    features: Dict[str, float]


class SmsRequest(BaseModel):
    plot_id: str
    lang: str = "en"
    phone: Optional[str] = None


class IrrigationCommand(BaseModel):
    plot_id: str
    valve: str = "V1"
    mode: Literal["auto", "manual", "hold"] = "auto"
    minutes: Optional[int] = None


# --------------------------------------------------------------------------- #
#  Meta
# --------------------------------------------------------------------------- #
@app.get("/api/health")
def health():
    repo = get_repo()
    return {"ok": True, "app": APP_NAME, "version": APP_VERSION,
            "uptime_s": round(time.time() - START, 1),
            "models_ready": True, "data": repo.status(),
            "languages": list(SUPPORTED), "server_date": date.today().isoformat()}


@app.get("/api/i18n/{lang}")
def i18n(lang: str):
    return {"lang": lang, "strings": ui_strings(lang)}


@app.get("/api/reference")
def reference():
    """Crop + soil knowledge base used by the agronomic engine."""
    return {"crops": CROP_LIBRARY, "soils": SOIL_LIBRARY}


@app.get("/api/benchmark")
def benchmark():
    eng = get_engine()
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "training_corpus": {"rows": 6000, "seed": 7, "split": "78/22 train-test"},
        "models": eng.benchmark(),
        "latency_ms": _latency_probe(),
        "notes": [
            "Metrics are computed on a held-out split of the physiologically-parameterised corpus.",
            "Replace `_corpus()` in app/ml.py with your district's historical records to retrain on real ground truth.",
            "Local explanations use ablation-to-median attribution — no SHAP dependency, edge-safe.",
        ],
    }


def _latency_probe() -> Dict[str, float]:
    repo = get_repo()
    plot = repo.table("plots")[0]
    t0 = time.time(); services.build_features(repo, {**plot, "growth_stage": growth_stage(plot["days_after_sowing"], plot["crop"])}); t_feat = (time.time() - t0) * 1000
    t0 = time.time(); services.analyse_plot(repo, plot["id"]); t_full = (time.time() - t0) * 1000
    return {"feature_engineering_ms": round(t_feat, 2), "full_bundle_ms": round(t_full, 2)}


# --------------------------------------------------------------------------- #
#  Farms / plots
# --------------------------------------------------------------------------- #
@app.get("/api/farms")
def farms():
    repo = get_repo()
    out = []
    for f in repo.table("farms"):
        plots = repo.where("plots", farm_id=f["id"])
        out.append({**f, "plot_count": len(plots),
                    "crops": sorted({p["crop"] for p in plots})})
    return out


@app.get("/api/plots")
def plots(farm_id: Optional[str] = None):
    repo = get_repo()
    rows = repo.where("plots", farm_id=farm_id) if farm_id else repo.table("plots")
    out = []
    for p in rows:
        sat = services.satellite_series(repo, p["id"], 20)
        farm = repo.one("farms", id=p["farm_id"]) or {}
        out.append({**p, "growth_stage": growth_stage(p["days_after_sowing"], p["crop"]),
                    "district": farm.get("district"), "state": farm.get("state"),
                    "owner_name": farm.get("owner_name"), "farm_name": farm.get("name"),
                    "ndvi_latest": sat[-1]["ndvi"] if sat else None,
                    "ndwi_latest": sat[-1]["ndwi"] if sat else None,
                    "last_scene": sat[-1]["capture_date"] if sat else None})
    return out


@app.get("/api/geojson")
def geojson():
    """GIS layer — every plot as a GeoJSON feature carrying its live risk attributes."""
    repo = get_repo()
    feats = []
    for p in repo.table("plots"):
        b = bundle(p["id"])
        feats.append({
            "type": "Feature", "geometry": p["geometry"],
            "properties": {
                "plot_id": p["id"], "name": p["name"], "crop": p["crop"], "variety": p["variety"],
                "area_ha": p["area_ha"], "farm_id": p["farm_id"],
                "farm_name": b["farm"].get("name"), "district": b["farm"].get("district"),
                "growth_stage": b["plot"]["growth_stage"],
                "ndvi": b["features"]["ndvi_latest"], "ndwi": b["features"]["ndwi_mean"],
                "health": b["health"]["score"], "health_band": b["health"]["band"],
                "soil_score": b["soil"]["score"],
                "yield_t_ha": b["predictions"]["yield"]["value"],
                "risk": b["risk"]["composite"], "risk_level": b["risk"]["level"],
                "next_irrigation": b["water"]["next_irrigation"],
                "top_pest": b["pests"][0]["name"] if b["pests"] else None,
                "top_pest_risk": b["pests"][0]["risk"] if b["pests"] else None,
                "centroid": [p["centroid_lat"], p["centroid_lon"]],
            },
        })
    return {"type": "FeatureCollection", "features": feats}


@app.get("/api/plots/{plot_id}")
def plot_detail(plot_id: str, lang: str = Query("en")):
    return bundle(plot_id, lang)


@app.get("/api/plots/{plot_id}/advisory")
def advisory(plot_id: str, lang: str = Query("en"), persist: bool = Query(False)):
    b = bundle(plot_id, lang)
    if persist:
        repo = get_repo()
        for r in b["recommendations"]:
            repo.insert("advisories", {
                "plot_id": plot_id, "category": r["category"], "title": r["title"],
                "message_en": r["action"], "message_localised": r["action_localised"],
                "language": lang, "priority": r["priority"], "confidence": r["confidence"],
                "evidence": r["evidence"], "status": "issued",
            })
    return {"plot_id": plot_id, "language": lang, "generated_at": b["generated_at"],
            "health": b["health"], "risk": b["risk"],
            "recommendations": b["recommendations"]}


@app.get("/api/plots/{plot_id}/explain/{model_key}")
def explain(plot_id: str, model_key: str):
    b = bundle(plot_id)
    key = {"yield": "yield", "pest": "pest_outbreak", "disease": "disease_risk",
           "drought": "drought_stress", "flood": "flood_impact", "anomaly": "climate_anomaly"}.get(model_key, model_key)
    if key not in b["predictions"]:
        raise HTTPException(404, f"Unknown model '{model_key}'")
    p = b["predictions"][key]
    return {"plot_id": plot_id, "model": key, "value": p["value"], "unit": p.get("unit"),
            "confidence": p["confidence"], "metrics": p["metrics"],
            "explanation": p["explanation"], "features_used": b["features"]}


# --------------------------------------------------------------------------- #
#  Remote sensing
# --------------------------------------------------------------------------- #
@app.post("/api/indices")
def indices(req: IndexRequest):
    """Compute vegetation indices from raw multispectral band reflectance."""
    return {"input": req.model_dump(), **services.compute_indices(req.blue, req.red, req.nir, req.swir)}


@app.get("/api/plots/{plot_id}/satellite")
def satellite(plot_id: str, days: int = Query(120, ge=10, le=365)):
    repo = get_repo()
    rows = services.satellite_series(repo, plot_id, days)
    if not rows:
        raise HTTPException(404, f"No scenes for plot '{plot_id}'")
    return {"plot_id": plot_id, "scene_count": len(rows), "platform": rows[-1]["platform"],
            "resolution_m": rows[-1]["resolution_m"], "scenes": rows,
            "zonal_stats": {
                "ndvi_mean": round(sum(r["ndvi"] for r in rows) / len(rows), 4),
                "ndvi_min": min(r["ndvi"] for r in rows), "ndvi_max": max(r["ndvi"] for r in rows),
                "usable_scenes": sum(1 for r in rows if r["cloud_pct"] < 25)}}


@app.get("/api/plots/{plot_id}/ndvi-grid")
def ndvi_grid(plot_id: str, size: int = Query(12, ge=4, le=32)):
    """Synthetic within-field NDVI raster — drives the variable-rate / zone map."""
    import math as _m
    b = bundle(plot_id)
    base = b["features"]["ndvi_latest"]
    ring = b["plot"]["geometry"]["coordinates"][0]
    lons = [c[0] for c in ring]; lats = [c[1] for c in ring]
    cells = []
    for r in range(size):
        for c in range(size):
            u, v = c / (size - 1), r / (size - 1)
            # deterministic smooth spatial field + edge effect
            wave = 0.055 * _m.sin(6.1 * u + 1.3) * _m.cos(5.4 * v + 0.7)
            edge = -0.05 * max(0, 1 - 6 * min(u, v, 1 - u, 1 - v))
            val = round(max(0.03, min(0.96, base + wave + edge)), 4)
            cells.append({"row": r, "col": c,
                          "lon": round(min(lons) + u * (max(lons) - min(lons)), 6),
                          "lat": round(min(lats) + v * (max(lats) - min(lats)), 6),
                          "ndvi": val,
                          "zone": "High" if val > base + 0.03 else "Low" if val < base - 0.03 else "Medium"})
    return {"plot_id": plot_id, "size": size, "base_ndvi": base, "cells": cells,
            "bounds": {"min_lat": min(lats), "max_lat": max(lats), "min_lon": min(lons), "max_lon": max(lons)},
            "management_zones": {
                "High": sum(1 for c in cells if c["zone"] == "High"),
                "Medium": sum(1 for c in cells if c["zone"] == "Medium"),
                "Low": sum(1 for c in cells if c["zone"] == "Low")}}


# --------------------------------------------------------------------------- #
#  Prediction / recommendation endpoints
# --------------------------------------------------------------------------- #
@app.post("/api/predict")
def predict(req: PredictRequest):
    return get_engine().predict(req.model, req.features)


@app.get("/api/plots/{plot_id}/water")
def water(plot_id: str):
    return bundle(plot_id)["water"]


@app.get("/api/plots/{plot_id}/fertilizer")
def fertilizer(plot_id: str):
    return bundle(plot_id)["fertilizer"]


@app.get("/api/plots/{plot_id}/pests")
def pests(plot_id: str):
    b = bundle(plot_id)
    return {"plot_id": plot_id, "pests": b["pests"],
            "model": b["predictions"]["pest_outbreak"], "disease_model": b["predictions"]["disease_risk"]}


@app.get("/api/plots/{plot_id}/carbon")
def carbon(plot_id: str):
    return bundle(plot_id)["carbon"]


@app.get("/api/market/{crop}")
def market(crop: str, horizon: int = Query(14, ge=3, le=45)):
    return services.price_forecast(get_repo(), crop, horizon)


@app.get("/api/plots/{plot_id}/digital-twin")
def digital_twin(plot_id: str):
    """Digital farm twin — live state vector + a 10-day simulated forward state."""
    b = bundle(plot_id)
    state = {"ndvi": b["features"]["ndvi_latest"], "soil_moisture": b["features"]["soil_moisture"],
             "lai": b["features"]["lai"], "biomass_proxy": round(b["features"]["lai"] * 1.42, 3),
             "root_depth_mm": CROP_LIBRARY[b["plot"]["crop"]]["root_depth_mm"],
             "stage": b["plot"]["growth_stage"], "dap": b["plot"]["days_after_sowing"]}
    sim, moisture, ndvi = [], state["soil_moisture"], state["ndvi"]
    for d in b["water"]["schedule"]:
        moisture += (d["effective_rain_mm"] + d["gross_mm"] * 0.8 - d["etc_mm"]) / \
                    CROP_LIBRARY[b["plot"]["crop"]]["root_depth_mm"]
        moisture = max(0.03, min(moisture, SOIL_LIBRARY[b["plot"]["soil_type"]]["fc"] * 1.02))
        stress = max(0.0, (CROP_LIBRARY[b["plot"]["crop"]]["critical_moisture"] - moisture) * 3.2)
        ndvi = max(0.03, min(0.96, ndvi + b["features"]["ndvi_trend"] / 30 - stress * 0.012))
        sim.append({"date": d["date"], "soil_moisture": round(moisture, 4), "ndvi": round(ndvi, 4),
                    "water_stress_index": round(min(stress, 1.0), 3), "irrigated": d["irrigate"]})
    return {"plot_id": plot_id, "state": state, "simulation": sim,
            "engine": "water-balance coupled NDVI growth twin (daily step)"}


@app.post("/api/irrigation/command")
def irrigation_command(cmd: IrrigationCommand):
    """Autonomous irrigation control — emits an actuator command for the field gateway."""
    b = bundle(cmd.plot_id)
    day = next((s for s in b["water"]["schedule"] if s["irrigate"]), None)
    minutes = cmd.minutes or (day["minutes"] if day else 0)
    payload = {
        "device": f"gateway-{cmd.plot_id}", "valve": cmd.valve, "mode": cmd.mode,
        "open_minutes": minutes, "target_mm": day["gross_mm"] if day else 0,
        "scheduled_for": day["date"] if day else None,
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "safety_interlocks": {
            "rain_forecast_mm_24h": b["forecast"][0]["rainfall_mm"] if b["forecast"] else 0,
            "abort_if_rain_over_mm": round(day["etc_mm"], 1) if day else 5.0,
            "max_runtime_minutes": 180,
            "soil_moisture_cutoff": SOIL_LIBRARY[b["plot"]["soil_type"]]["fc"],
        },
        "mqtt_topic": f"agrisense/{b['plot']['farm_id']}/{cmd.plot_id}/valve/{cmd.valve}/set",
    }
    get_repo().insert("advisories", {"plot_id": cmd.plot_id, "category": "Actuation",
                                     "title": f"Valve {cmd.valve} {cmd.mode} {minutes} min",
                                     "message_en": str(payload), "priority": "High",
                                     "confidence": 0.9, "status": "dispatched"})
    return {"ok": True, "command": payload}


# --------------------------------------------------------------------------- #
#  Low-bandwidth / offline channel
# --------------------------------------------------------------------------- #
@app.post("/api/sms")
def sms(req: SmsRequest):
    b = bundle(req.plot_id, req.lang)
    digest = services.sms_digest(b, req.lang)
    repo = get_repo()
    row = repo.insert("sms_outbox", {
        "plot_id": req.plot_id, "phone": req.phone or b["farm"].get("phone"),
        "body": digest["body_localised"], "lang": req.lang, "status": "queued"})
    return {"ok": True, **digest, "queued": row}


@app.get("/api/sms/outbox")
def sms_outbox():
    return sorted(get_repo().table("sms_outbox"), key=lambda r: r.get("created_at", ""), reverse=True)[:50]


@app.get("/api/offline-bundle")
def offline_bundle(lang: str = Query("en"), plot_id: Optional[str] = None):
    """Minified advisory pack for offline / 2G sync. ~2 KB per plot after gzip."""
    repo = get_repo()
    ids = [plot_id] if plot_id else [p["id"] for p in repo.table("plots")]
    packs = []
    for pid in ids:
        b = bundle(pid, lang)
        packs.append({
            "p": pid, "n": b["plot"]["name"], "c": b["plot"]["crop"],
            "h": b["health"]["score"], "y": b["predictions"]["yield"]["value"],
            "r": b["risk"]["composite"], "rl": b["risk"]["level"],
            "irr": b["water"]["next_irrigation"], "mm": b["water"]["week_gross_mm"],
            "n_kg": b["fertilizer"]["next_dose"]["N_kg_ha"],
            "pest": b["pests"][0]["name"] if b["pests"] else None,
            "pr": b["pests"][0]["risk"] if b["pests"] else None,
            "sms": services.sms_digest(b, lang)["body_localised"],
            "acts": [{"t": r["title_localised"], "p": r["priority"], "cf": r["confidence"]}
                     for r in b["recommendations"][:3]],
        })
    return {"v": APP_VERSION, "lang": lang, "ts": datetime.now(timezone.utc).isoformat(),
            "ttl_hours": 24, "packs": packs}


# --------------------------------------------------------------------------- #
#  Fleet-level views for policymakers
# --------------------------------------------------------------------------- #
@app.get("/api/overview")
def overview(lang: str = Query("en")):
    repo = get_repo()
    rows, alerts = [], []
    for p in repo.table("plots"):
        b = bundle(p["id"], lang)
        rows.append({
            "plot_id": p["id"], "name": p["name"], "farm_id": p["farm_id"],
            "farm_name": b["farm"].get("name"), "district": b["farm"].get("district"),
            "state": b["farm"].get("state"), "owner": b["farm"].get("owner_name"),
            "crop": p["crop"], "variety": p["variety"], "area_ha": p["area_ha"],
            "stage": b["plot"]["growth_stage"], "dap": p["days_after_sowing"],
            "ndvi": b["features"]["ndvi_latest"], "health": b["health"]["score"],
            "health_band": b["health"]["band"], "soil_score": b["soil"]["score"],
            "yield_t_ha": b["predictions"]["yield"]["value"],
            "yield_conf": b["predictions"]["yield"]["confidence"],
            "yield_total_t": b["predictions"]["yield"]["plot_total_tonnes"],
            "vs_history_pct": b["predictions"]["yield"]["vs_history_pct"],
            "risk": b["risk"]["composite"], "risk_level": b["risk"]["level"],
            "drought": b["predictions"]["drought_stress"]["value"],
            "flood": b["predictions"]["flood_impact"]["value"],
            "pest": b["predictions"]["pest_outbreak"]["value"],
            "disease": b["predictions"]["disease_risk"]["value"],
            "anomaly": b["predictions"]["climate_anomaly"]["value"],
            "next_irrigation": b["water"]["next_irrigation"],
            "week_water_l": b["water"]["week_litres"],
            "water_saved_l": b["water"]["water_saved_vs_flood_litres"],
            "n_kg_ha": b["fertilizer"]["season_target_kg_ha"]["N"],
            "carbon_kg": b["carbon"]["total_kg_co2e"],
            "top_action": b["recommendations"][0]["title_localised"],
            "top_priority": b["recommendations"][0]["priority"],
            "centroid": [p["centroid_lat"], p["centroid_lon"]],
        })
        for r in b["recommendations"]:
            if r["priority"] == "High":
                alerts.append({"plot_id": p["id"], "plot": p["name"], "crop": p["crop"],
                               "category": r["category"], "title": r["title_localised"],
                               "confidence": r["confidence"], "district": b["farm"].get("district")})
    total_area = sum(r["area_ha"] for r in rows) or 1
    return {
        "language": lang,
        "kpi": {
            "plots": len(rows), "farms": len(repo.table("farms")),
            "area_ha": round(total_area, 2),
            "avg_health": round(sum(r["health"] for r in rows) / len(rows), 1),
            "avg_ndvi": round(sum(r["ndvi"] for r in rows) / len(rows), 4),
            "total_yield_t": round(sum(r["yield_total_t"] for r in rows), 1),
            "yield_t_ha_weighted": round(sum(r["yield_t_ha"] * r["area_ha"] for r in rows) / total_area, 2),
            "high_risk_plots": sum(1 for r in rows if r["risk_level"] == "High"),
            "water_week_l": int(sum(r["week_water_l"] for r in rows)),
            "water_saved_l": int(sum(r["water_saved_l"] for r in rows)),
            "carbon_kg": round(sum(r["carbon_kg"] for r in rows), 1),
            "open_alerts": len(alerts),
        },
        "plots": rows,
        "alerts": sorted(alerts, key=lambda a: -a["confidence"]),
        "by_district": _group(rows, "district"),
        "by_crop": _group(rows, "crop"),
        "data_source": repo.status(),
    }


def _group(rows: List[Dict[str, Any]], key: str) -> List[Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        k = r.get(key) or "Unknown"
        g = out.setdefault(k, {"key": k, "plots": 0, "area_ha": 0.0, "health": 0.0,
                               "risk": 0.0, "yield_t": 0.0, "water_l": 0})
        g["plots"] += 1; g["area_ha"] += r["area_ha"]; g["health"] += r["health"]
        g["risk"] += r["risk"]; g["yield_t"] += r["yield_total_t"]; g["water_l"] += r["week_water_l"]
    for g in out.values():
        g["health"] = round(g["health"] / g["plots"], 1)
        g["risk"] = round(g["risk"] / g["plots"], 3)
        g["area_ha"] = round(g["area_ha"], 2)
        g["yield_t"] = round(g["yield_t"], 2)
    return sorted(out.values(), key=lambda g: -g["area_ha"])


@app.get("/api/risk-map")
def risk_map():
    """District-level aggregated climate risk surface for policy dashboards."""
    repo = get_repo()
    acc: Dict[str, Dict[str, Any]] = {}
    for p in repo.table("plots"):
        b = bundle(p["id"])
        d = b["farm"].get("district", "Unknown")
        g = acc.setdefault(d, {"district": d, "state": b["farm"].get("state"), "n": 0,
                               "lat": 0.0, "lon": 0.0, "drought": 0.0, "flood": 0.0,
                               "pest": 0.0, "disease": 0.0, "anomaly": 0.0, "composite": 0.0,
                               "area_ha": 0.0})
        g["n"] += 1; g["area_ha"] += p["area_ha"]
        g["lat"] += p["centroid_lat"]; g["lon"] += p["centroid_lon"]
        g["drought"] += b["predictions"]["drought_stress"]["value"]
        g["flood"] += b["predictions"]["flood_impact"]["value"]
        g["pest"] += b["predictions"]["pest_outbreak"]["value"]
        g["disease"] += b["predictions"]["disease_risk"]["value"]
        g["anomaly"] += b["predictions"]["climate_anomaly"]["value"]
        g["composite"] += b["risk"]["composite"]
    out = []
    for g in acc.values():
        n = g.pop("n")
        for k in ("lat", "lon", "drought", "flood", "pest", "disease", "anomaly", "composite"):
            g[k] = round(g[k] / n, 4)
        g["plots"] = n
        g["area_ha"] = round(g["area_ha"], 2)
        g["level"] = "High" if g["composite"] >= 0.55 else "Medium" if g["composite"] >= 0.3 else "Low"
        out.append(g)
    return sorted(out, key=lambda g: -g["composite"])


@app.get("/api/dataset/export")
def dataset_export(table: str = Query("plots")):
    """Demonstration dataset export (also used by the benchmark notebook)."""
    if table == "__all__":
        return {k: v for k, v in build_all().items()}
    repo = get_repo()
    rows = repo.table(table)
    if not rows:
        raise HTTPException(404, f"Unknown or empty table '{table}'")
    return {"table": table, "rows": len(rows), "data": rows}
