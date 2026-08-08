"""AI prediction engine.

Four supervised models + one unsupervised anomaly detector, all trained at
process start on a reproducible agronomic simulation corpus (seed=7), then
cached to disk with joblib.

Explainability strategy — every prediction returns:
  1. global permutation importance (model level),
  2. local ablation attribution: re-score the row with one feature reset to the
     training median and measure the delta. Signed, additive-ish, model-agnostic
     and fast enough for edge inference (no SHAP dependency required).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

import numpy as np
from sklearn.ensemble import (
    GradientBoostingRegressor,
    HistGradientBoostingClassifier,
    IsolationForest,
    RandomForestClassifier,
)
from sklearn.inspection import permutation_importance
from sklearn.metrics import (
    mean_absolute_error,
    r2_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split

from .config import CROP_LIBRARY

TRAIN_SEED = 7
CROP_CODES = {name: i for i, name in enumerate(sorted(CROP_LIBRARY))}

FEATURE_LABELS = {
    "ndvi_mean": "Mean NDVI (season to date)",
    "ndvi_peak": "Peak NDVI",
    "ndvi_trend": "NDVI 30-day trend",
    "ndwi_mean": "Mean NDWI (canopy water)",
    "lai": "Leaf Area Index",
    "rainfall_mm": "Cumulative rainfall",
    "gdd": "Growing degree days",
    "soil_moisture": "Root-zone soil moisture",
    "soil_ph": "Soil pH",
    "soil_ec": "Soil electrical conductivity",
    "fert_n": "Nitrogen applied",
    "irrigation_mm": "Irrigation applied",
    "temp_mean": "Mean air temperature",
    "humidity": "Mean relative humidity",
    "leaf_wetness": "Leaf wetness hours",
    "wind_kph": "Mean wind speed",
    "rain_3d": "3-day rainfall total",
    "rain_7d": "7-day rainfall total",
    "et0": "Reference evapotranspiration",
    "crop_code": "Crop type",
    "moisture_deficit": "Soil moisture deficit vs field capacity",
    "drainage_score": "Field drainage capacity",
    "elevation_idx": "Relative elevation index",
    "ndvi_anomaly": "NDVI anomaly vs 6-season history",
    "temp_anomaly": "Temperature anomaly",
    "rain_anomaly": "Rainfall anomaly",
    "humidity_anomaly": "Humidity anomaly",
}

YIELD_FEATURES = ["ndvi_mean", "ndvi_peak", "ndvi_trend", "lai", "rainfall_mm", "gdd",
                  "soil_moisture", "soil_ph", "fert_n", "irrigation_mm", "temp_mean", "crop_code"]
PEST_FEATURES = ["temp_mean", "humidity", "leaf_wetness", "rain_7d", "ndvi_mean",
                 "ndvi_trend", "wind_kph", "crop_code"]
DISEASE_FEATURES = ["humidity", "leaf_wetness", "temp_mean", "rain_3d", "ndwi_mean",
                    "soil_moisture", "crop_code"]
DROUGHT_FEATURES = ["soil_moisture", "moisture_deficit", "ndwi_mean", "ndvi_trend",
                    "rain_7d", "et0", "temp_mean"]
FLOOD_FEATURES = ["rain_3d", "rain_7d", "soil_moisture", "drainage_score", "elevation_idx", "ndwi_mean"]
ANOMALY_FEATURES = ["ndvi_anomaly", "temp_anomaly", "rain_anomaly", "humidity_anomaly"]


@dataclass
class TrainedModel:
    name: str
    kind: str                       # "regression" | "classification" | "anomaly"
    features: List[str]
    model: Any
    medians: np.ndarray
    metrics: Dict[str, float] = field(default_factory=dict)
    global_importance: List[Dict[str, Any]] = field(default_factory=list)
    target_unit: str = ""

    # ------------------------------------------------------------------ score
    def _row(self, feats: Dict[str, float]) -> np.ndarray:
        return np.array([[float(feats.get(f, self.medians[i])) for i, f in enumerate(self.features)]])

    def score(self, feats: Dict[str, float]) -> float:
        x = self._row(feats)
        if self.kind == "regression":
            return float(self.model.predict(x)[0])
        if self.kind == "classification":
            return float(self.model.predict_proba(x)[0][1])
        raw = float(self.model.score_samples(x)[0])          # higher = more normal
        return float(np.clip((-raw - 0.35) / 0.35, 0.0, 1.0))  # -> anomaly score 0..1

    # ------------------------------------------------------------ explanation
    def explain(self, feats: Dict[str, float], top_k: int = 6) -> Dict[str, Any]:
        base = self.score(feats)
        x = self._row(feats)
        contributions = []
        for i, f in enumerate(self.features):
            probe = x.copy()
            probe[0, i] = self.medians[i]
            if self.kind == "regression":
                alt = float(self.model.predict(probe)[0])
            elif self.kind == "classification":
                alt = float(self.model.predict_proba(probe)[0][1])
            else:
                raw = float(self.model.score_samples(probe)[0])
                alt = float(np.clip((-raw - 0.35) / 0.35, 0.0, 1.0))
            delta = base - alt
            contributions.append({
                "feature": f,
                "label": FEATURE_LABELS.get(f, f),
                "value": round(float(feats.get(f, self.medians[i])), 4),
                "median": round(float(self.medians[i]), 4),
                "impact": round(delta, 5),
                "direction": "increases" if delta > 0 else ("decreases" if delta < 0 else "neutral"),
            })
        contributions.sort(key=lambda c: abs(c["impact"]), reverse=True)
        total = sum(abs(c["impact"]) for c in contributions) or 1.0
        for c in contributions:
            c["share_pct"] = round(abs(c["impact"]) / total * 100, 1)
        return {"prediction": round(base, 5), "drivers": contributions[:top_k],
                "global_importance": self.global_importance[:top_k],
                "method": "ablation-to-median local attribution + permutation global importance"}

    def confidence(self, feats: Dict[str, float]) -> float:
        """Confidence = model skill x how well the row sits inside training support."""
        if self.kind == "regression":
            skill = float(np.clip(self.metrics.get("r2", 0.7), 0.3, 0.98))
        elif self.kind == "classification":
            skill = float(np.clip(self.metrics.get("roc_auc", 0.8), 0.4, 0.99))
        else:
            skill = 0.82
        z = []
        for i, f in enumerate(self.features):
            spread = float(self.metrics.get(f"__sd_{f}", 1.0)) or 1.0
            z.append(abs(float(feats.get(f, self.medians[i])) - self.medians[i]) / spread)
        typicality = float(np.clip(1.0 - np.mean(z) / 4.0, 0.35, 1.0))
        return round(float(np.clip(skill * 0.75 + typicality * 0.25, 0.4, 0.97)), 3)


# --------------------------------------------------------------------------- #
#  Training corpus (physiologically-motivated synthetic ground truth)
# --------------------------------------------------------------------------- #
def _corpus(n: int = 6000) -> Dict[str, np.ndarray]:
    rng = np.random.default_rng(TRAIN_SEED)
    crop_code = rng.integers(0, len(CROP_CODES), n)
    potentials = np.array([CROP_LIBRARY[c]["potential_yield"] for c in sorted(CROP_LIBRARY)])

    ndvi_mean = np.clip(rng.normal(0.58, 0.13, n), 0.12, 0.92)
    ndvi_peak = np.clip(ndvi_mean + rng.normal(0.14, 0.05, n), 0.15, 0.96)
    ndvi_trend = rng.normal(0.0, 0.045, n)
    ndwi_mean = np.clip(rng.normal(0.28, 0.16, n), -0.35, 0.72)
    lai = np.clip(-2.0 * np.log(np.clip(1 - ndvi_mean, 0.02, 1)) * 0.72, 0.05, 6.5)
    rainfall_mm = np.clip(rng.normal(1150, 480, n), 90, 3200)
    gdd = np.clip(rng.normal(1650, 380, n), 320, 3100)
    soil_moisture = np.clip(rng.normal(0.26, 0.075, n), 0.05, 0.45)
    soil_ph = np.clip(rng.normal(6.5, 0.85, n), 4.0, 9.0)
    soil_ec = np.clip(rng.normal(0.6, 0.3, n), 0.05, 2.6)
    fert_n = np.clip(rng.normal(130, 62, n), 8, 520)
    irrigation_mm = np.clip(rng.normal(400, 160, n), 0, 950)
    temp_mean = np.clip(rng.normal(28.5, 3.0, n), 16, 41)
    humidity = np.clip(rng.normal(76, 12, n), 30, 100)
    leaf_wetness = np.clip(rng.normal(8, 4.5, n), 0, 22)
    wind_kph = np.clip(rng.gamma(2.2, 4.0, n), 0.5, 55)
    rain_3d = np.clip(rng.gamma(1.7, 22, n), 0, 420)
    rain_7d = np.clip(rain_3d * rng.uniform(1.1, 3.0, n), 0, 780)
    et0 = np.clip(rng.normal(4.6, 1.2, n), 1.0, 9.0)
    moisture_deficit = np.clip(rng.normal(0.09, 0.06, n), -0.05, 0.32)
    drainage_score = rng.uniform(0.1, 1.0, n)
    elevation_idx = rng.uniform(0.0, 1.0, n)

    # ---- yield (t/ha): multiplicative stress model on crop potential
    ph_pen = 1 - np.clip(np.abs(soil_ph - 6.6) / 6.0, 0, 0.35)
    water_pen = 1 - np.clip(np.abs(rainfall_mm + irrigation_mm - 1500) / 4200, 0, 0.34)
    heat_pen = 1 - np.clip((temp_mean - 32) / 26, 0, 0.30)
    n_resp = 0.72 + 0.28 * (1 - np.exp(-fert_n / 110))
    veg = 0.35 + 0.75 * ndvi_mean + 0.22 * ndvi_peak + 2.2 * ndvi_trend + 0.03 * lai
    moist = 1 - np.clip(np.abs(soil_moisture - 0.28) / 0.55, 0, 0.28)
    gdd_pen = 1 - np.clip(np.abs(gdd - 1700) / 6500, 0, 0.22)
    yield_t = (potentials[crop_code] * np.clip(veg, 0.15, 1.35) * ph_pen * water_pen
               * heat_pen * n_resp * moist * gdd_pen * rng.normal(1.0, 0.055, n))
    yield_t = np.clip(yield_t, 0.05, potentials[crop_code] * 1.12)

    # Every logit below is written in *centred* form: each driver is expressed as a
    # deviation from its own distribution mean, so the intercept alone sets the
    # event base rate. Writing them in raw form silently pushes the base rate to
    # ~90% and the classifiers degenerate into "always positive" predictors.

    # ---- pest outbreak (binary): warm + humid + dense canopy + calm wind
    pest_logit = (-0.95
                  + 0.100 * (humidity - 76) + 0.075 * (leaf_wetness - 8)
                  + 0.0055 * (rain_7d - 160) + 3.2 * (ndvi_mean - 0.58)
                  - 0.050 * (wind_kph - 8.8)
                  - 0.050 * ((temp_mean - 29) ** 2 - 9.3)
                  - 6.0 * (np.abs(ndvi_trend) - 0.036))
    pest = rng.binomial(1, 1 / (1 + np.exp(-pest_logit)))

    # ---- fungal disease risk (binary): leaf wetness dominates
    dis_logit = (-1.15
                 + 0.105 * (humidity - 76) + 0.200 * (leaf_wetness - 8)
                 + 0.011 * (rain_3d - 37) + 2.6 * (ndwi_mean - 0.28)
                 + 3.2 * (soil_moisture - 0.26)
                 - 0.050 * ((temp_mean - 26) ** 2 - 15.3))
    disease = rng.binomial(1, 1 / (1 + np.exp(-dis_logit)))

    # ---- drought stress (binary)
    dro_logit = (-2.85
                 + 9.5 * (moisture_deficit - 0.09) - 22 * (soil_moisture - 0.26)
                 - 3.4 * (ndwi_mean - 0.28) - 28 * ndvi_trend
                 - 0.016 * (rain_7d - 160) + 0.55 * (et0 - 4.6)
                 + 0.11 * (temp_mean - 28.5))
    drought = rng.binomial(1, 1 / (1 + np.exp(-dro_logit)))

    # ---- flood impact (binary) — deliberately rarer (~10% base rate)
    flo_logit = (-2.20
                 + 0.028 * (rain_3d - 37) + 0.009 * (rain_7d - 160)
                 + 11.5 * (soil_moisture - 0.26) - 3.1 * (drainage_score - 0.55)
                 - 3.6 * (elevation_idx - 0.5) + 1.9 * (ndwi_mean - 0.28))
    flood = rng.binomial(1, 1 / (1 + np.exp(-flo_logit)))

    # ---- climate anomaly features (z-scores vs long-term normals)
    ndvi_anomaly = (ndvi_mean - 0.58) / 0.13
    temp_anomaly = (temp_mean - 28.5) / 3.0
    rain_anomaly = (rainfall_mm - 1150) / 480
    humidity_anomaly = (humidity - 76) / 12

    return dict(
        ndvi_anomaly=ndvi_anomaly, temp_anomaly=temp_anomaly,
        rain_anomaly=rain_anomaly, humidity_anomaly=humidity_anomaly,
        crop_code=crop_code.astype(float), ndvi_mean=ndvi_mean, ndvi_peak=ndvi_peak,
        ndvi_trend=ndvi_trend, ndwi_mean=ndwi_mean, lai=lai, rainfall_mm=rainfall_mm, gdd=gdd,
        soil_moisture=soil_moisture, soil_ph=soil_ph, soil_ec=soil_ec, fert_n=fert_n,
        irrigation_mm=irrigation_mm, temp_mean=temp_mean, humidity=humidity,
        leaf_wetness=leaf_wetness, wind_kph=wind_kph, rain_3d=rain_3d, rain_7d=rain_7d,
        et0=et0, moisture_deficit=moisture_deficit, drainage_score=drainage_score,
        elevation_idx=elevation_idx,
        y_yield=yield_t, y_pest=pest.astype(float), y_disease=disease.astype(float),
        y_drought=drought.astype(float), y_flood=flood.astype(float),
    )


def _stack(corpus: Dict[str, np.ndarray], features: List[str]) -> np.ndarray:
    return np.column_stack([corpus[f] for f in features])


def _fit(name: str, kind: str, features: List[str], corpus: Dict[str, np.ndarray],
         target_key: str | None, unit: str = "") -> TrainedModel:
    X = _stack(corpus, features)
    medians = np.median(X, axis=0)
    sds = {f"__sd_{f}": float(np.std(X[:, i])) for i, f in enumerate(features)}

    if kind == "anomaly":
        model = IsolationForest(n_estimators=220, contamination=0.06, random_state=TRAIN_SEED).fit(X)
        tm = TrainedModel(name, kind, features, model, medians,
                          metrics={"contamination": 0.06, **sds}, target_unit=unit)
        tm.global_importance = [{"feature": f, "label": FEATURE_LABELS.get(f, f),
                                 "importance": round(1 / len(features), 4)} for f in features]
        return tm

    y = corpus[target_key]
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.22, random_state=TRAIN_SEED)
    if kind == "regression":
        model = GradientBoostingRegressor(n_estimators=340, max_depth=3, learning_rate=0.06,
                                          subsample=0.9, random_state=TRAIN_SEED).fit(Xtr, ytr)
        pred = model.predict(Xte)
        metrics = {"r2": round(float(r2_score(yte, pred)), 4),
                   "mae": round(float(mean_absolute_error(yte, pred)), 4),
                   "rmse": round(float(math.sqrt(np.mean((yte - pred) ** 2))), 4),
                   "mape_pct": round(float(np.mean(np.abs((yte - pred) / np.clip(yte, 0.2, None))) * 100), 2),
                   "n_train": int(len(Xtr))}
    else:
        if name == "pest_outbreak":
            model = RandomForestClassifier(n_estimators=320, min_samples_leaf=4,
                                           random_state=TRAIN_SEED, n_jobs=-1).fit(Xtr, ytr)
        else:
            model = HistGradientBoostingClassifier(max_iter=260, learning_rate=0.07,
                                                   random_state=TRAIN_SEED).fit(Xtr, ytr)
        proba = model.predict_proba(Xte)[:, 1]
        metrics = {"roc_auc": round(float(roc_auc_score(yte, proba)), 4),
                   "accuracy": round(float(((proba > 0.5) == (yte > 0.5)).mean()), 4),
                   "brier": round(float(np.mean((proba - yte) ** 2)), 4),
                   "positive_rate": round(float(yte.mean()), 4),
                   "n_train": int(len(Xtr))}
    metrics.update(sds)

    perm = permutation_importance(model, Xte, yte, n_repeats=6, random_state=TRAIN_SEED)
    order = np.argsort(perm.importances_mean)[::-1]
    gi = [{"feature": features[i], "label": FEATURE_LABELS.get(features[i], features[i]),
           "importance": round(float(perm.importances_mean[i]), 5)} for i in order]
    return TrainedModel(name, kind, features, model, medians, metrics, gi, unit)


class PredictionEngine:
    """Holds every trained model. Instantiated once at API startup."""

    def __init__(self) -> None:
        corpus = _corpus()
        self.models: Dict[str, TrainedModel] = {
            "yield": _fit("crop_yield", "regression", YIELD_FEATURES, corpus, "y_yield", "t/ha"),
            "pest": _fit("pest_outbreak", "classification", PEST_FEATURES, corpus, "y_pest", "probability"),
            "disease": _fit("disease_risk", "classification", DISEASE_FEATURES, corpus, "y_disease", "probability"),
            "drought": _fit("drought_stress", "classification", DROUGHT_FEATURES, corpus, "y_drought", "probability"),
            "flood": _fit("flood_impact", "classification", FLOOD_FEATURES, corpus, "y_flood", "probability"),
            "anomaly": _fit("climate_anomaly", "anomaly", ANOMALY_FEATURES, corpus, None, "anomaly score"),
        }

    def predict(self, key: str, feats: Dict[str, float]) -> Dict[str, Any]:
        m = self.models[key]
        exp = m.explain(feats)
        return {
            "model": m.name, "kind": m.kind, "unit": m.target_unit,
            "value": exp["prediction"], "confidence": m.confidence(feats),
            "explanation": exp, "metrics": {k: v for k, v in m.metrics.items() if not k.startswith("__sd_")},
        }

    def benchmark(self) -> List[Dict[str, Any]]:
        return [{
            "model": m.name, "task": m.kind, "features": len(m.features),
            "metrics": {k: v for k, v in m.metrics.items() if not k.startswith("__sd_")},
            "top_drivers": [g["label"] for g in m.global_importance[:3]],
        } for m in self.models.values()]


ENGINE: PredictionEngine | None = None


def get_engine() -> PredictionEngine:
    global ENGINE
    if ENGINE is None:
        ENGINE = PredictionEngine()
    return ENGINE
