# REST API Reference

**Base URL:** `http://localhost:8000`  
**Interactive schema:** `/docs` (Swagger UI) and `/redoc`

All routes below are implemented in `backend/app/main.py`. The response snippets are trimmed from `curl -s` captures against the local server on 2026-08-07; dynamic fields such as timestamps, uptime, queue length, and latency can change between requests.

## Transport, cache, and errors

- `GZipMiddleware` compresses responses whose body is at least 600 bytes.
- Full per-plot analysis bundles are cached in-process for 45 seconds by plot and language. Routes that read a bundle can therefore return the cached result during that window.
- An unhandled application exception is converted to HTTP `422`, never HTTP `500`. Its typed body has `ok: false`, the exception class in `error`, a `detail` string truncated to 400 characters, and the hint `The API degrades gracefully — retry, or use /api/offline-bundle for cached advisories.`

- Request-body validation is also `422`, using FastAPI/Pydantic's `detail` array. Expected missing plots, scenes, models, and tables are `404` responses, for example `{"detail":"Plot 'not-a-plot' not found"}`.

---

## System

### `GET /api/health`

**Parameters:** none.  
**Purpose:** service status, active data tier, row counts, languages, and server date.

```json
{"ok":true,"version":"1.0.0","models_ready":true,"data":{"source":"sqlite-cache","row_counts":{"farms":6,"plots":12,"sensor_readings":1440,"satellite_scenes":300,"weather_forecast":120,"cultivation_history":72,"market_prices":637,"advisories":0,"predictions":0,"sms_outbox":8}},"languages":["en","ta","ml","hi"],"server_date":"2026-08-07"}
```

### `GET /api/benchmark`

**Parameters:** none.  
**Purpose:** training-corpus metadata, metrics/top drivers for every model, and a live latency probe.

```json
{"training_corpus":{"rows":6000,"seed":7,"split":"78/22 train-test"},"models":[{"model":"crop_yield","task":"regression","features":12,"metrics":{"r2":0.9826,"mae":0.9026,"rmse":1.4868,"mape_pct":15.65,"n_train":4680}},{"model":"pest_outbreak","task":"classification","features":8,"metrics":{"roc_auc":0.8103,"accuracy":0.8,"brier":0.1432,"positive_rate":0.2515,"n_train":4680}}],"latency_ms":{"feature_engineering_ms":1.49,"full_bundle_ms":495.23}}
```

---

## Fleet

### `GET /api/overview`

**Query parameters:** `lang` (optional, default `en`).  
**Purpose:** fleet KPIs, per-plot intelligence, high-priority alert list, district/crop aggregates, and data-source status.

```json
{"language":"en","kpi":{"plots":12,"farms":6,"area_ha":29.6,"avg_health":70.0,"avg_ndvi":0.6455,"total_yield_t":278.5,"yield_t_ha_weighted":9.41,"high_risk_plots":3,"water_week_l":9188100,"water_saved_l":4747599,"carbon_kg":112973.2,"open_alerts":24},"plots":[{"plot_id":"plot-01","name":"North Paddy A1","crop":"Rice","health":87.8,"yield_t_ha":6.769,"risk":0.473,"risk_level":"Medium"}],"data_source":{"source":"sqlite-cache"}}
```

### `GET /api/farms`

**Parameters:** none.  
**Purpose:** farms enriched with `plot_count` and distinct crop names.

```json
[{"id":"farm-01","name":"Chalakudy River Farm","owner_name":"Karthikeyan Y","district":"Thrissur","state":"Kerala","lat":10.3062,"lon":76.3341,"area_ha":3.2,"soil_type":"Alluvial","language":"ml","plot_count":2,"crops":["Banana","Rice"]}]
```

### `GET /api/plots`

**Query parameters:** `farm_id` (optional).  
**Purpose:** plot register, optionally scoped to one farm, enriched with owner/farm/location and latest spectral fields.

```json
[{"id":"plot-01","farm_id":"farm-01","name":"North Paddy A1","crop":"Rice","variety":"Jyothi","area_ha":1.4,"sowing_date":"2026-05-31","expected_harvest_date":"2026-10-13","growth_stage":"mid","irrigation_type":"Flood","ndvi_latest":0.8461,"ndwi_latest":0.4402,"last_scene":"2026-08-07"}]
```

### `GET /api/risk-map`

**Parameters:** none.  
**Purpose:** district-level averages of drought, flood, pest, disease, anomaly, composite risk, centroid, area, and level.

```json
[{"district":"Alappuzha","state":"Kerala","lat":9.4345,"lon":76.386,"drought":0.0164,"flood":0.9398,"pest":0.5289,"disease":0.8795,"anomaly":0.6866,"composite":0.5715,"area_ha":7.4,"plots":2,"level":"High"}]
```

---

## GIS and remote sensing

### `GET /api/geojson`

**Parameters:** none.  
**Purpose:** plot boundaries as a GeoJSON `FeatureCollection` with live analytical properties.

```json
{"type":"FeatureCollection","features":[{"type":"Feature","geometry":{"type":"Polygon","coordinates":[[[76.3264,10.29625],[76.3328,10.29721],[76.33312,10.30265],[76.32704,10.30233],[76.3264,10.29625]]]},"properties":{"plot_id":"plot-01","crop":"Rice","health":87.8,"risk":0.473,"risk_level":"Medium"}}]}
```

### `POST /api/indices`

**Body:** `blue`, `red`, `nir` required reflectance values in `[0,1]`; `swir` optional in `[0,1]`, default `0.2`.  
**Purpose:** calculate vegetation indices from raw multispectral surface reflectance.

```json
{"input":{"blue":0.06,"red":0.09,"nir":0.42,"swir":0.21},"ndvi":0.6471,"evi":0.5464,"savi":0.4901,"ndwi":0.3333,"msavi":0.4883,"chlorophyll_index":3.667,"lai":1.5}
```

### `GET /api/plots/{plot_id}/satellite`

**Path parameters:** `plot_id`.  
**Query parameters:** `days` (optional, integer 10–365, default `120`).  
**Purpose:** satellite-scene series and zonal NDVI summary for a plot.

```json
{"plot_id":"plot-01","scene_count":5,"platform":"Sentinel-2 L2A","resolution_m":10,"zonal_stats":{"ndvi_mean":0.8317,"ndvi_min":0.7848,"ndvi_max":0.8688,"usable_scenes":5},"scenes":[{"capture_date":"2026-08-07","tile_id":"T43PGQ_20260807","band_blue":0.0302,"band_red":0.0394,"band_nir":0.4726,"band_swir":0.1837,"ndvi":0.8461,"evi":0.7305,"savi":0.6421,"ndwi":0.4402,"ndre":0.5328,"lai":2.695,"cloud_pct":6.7}]}
```

### `GET /api/plots/{plot_id}/ndvi-grid`

**Path parameters:** `plot_id`.  
**Query parameters:** `size` (optional, integer 4–32, default `12`).  
**Purpose:** deterministic within-field NDVI cells, bounds, and high/medium/low management-zone counts.

```json
{"plot_id":"plot-01","size":4,"base_ndvi":0.8461,"bounds":{"min_lat":10.29625,"max_lat":10.30265,"min_lon":76.3264,"max_lon":76.33312},"management_zones":{"High":1,"Medium":7,"Low":8},"cells":[{"row":0,"col":0,"lon":76.3264,"lat":10.29625,"ndvi":0.8366,"zone":"Medium"}]}
```

---

## Plot dossier and agronomy

### `GET /api/plots/{plot_id}`

**Path parameters:** `plot_id`.  
**Query parameters:** `lang` (optional, default `en`).  
**Purpose:** complete plot dossier: identities, fused features, health, soil, water, fertilizer, pests, six predictions, risk, recommendations, carbon, satellite/sensor/forecast/history/market series.

```json
{"plot":{"id":"plot-01","name":"North Paddy A1","crop":"Rice","area_ha":1.4,"growth_stage":"mid"},"features":{"ndvi_mean":0.8059,"soil_moisture":0.3744,"rain_fc_7d":51.3},"health":{"score":87.8,"band":"Excellent"},"risk":{"composite":0.473,"level":"Medium"},"predictions":{"yield":{"value":6.769,"unit":"t/ha","confidence":0.917}}}
```

### `GET /api/plots/{plot_id}/explain/{model_key}`

**Path parameters:** `plot_id`; `model_key` is `yield`, `pest`, `disease`, `drought`, `flood`, or `anomaly`.  
**Purpose:** selected model output, metrics, feature vector, local drivers, and global permutation importance.

```json
{"plot_id":"plot-01","model":"yield","value":6.769,"unit":"t/ha","confidence":0.917,"metrics":{"r2":0.9826,"mae":0.9026,"rmse":1.4868,"mape_pct":15.65,"n_train":4680},"explanation":{"method":"ablation-to-median local attribution + permutation global importance","drivers":[{"feature":"crop_code","label":"Crop type","value":5.0,"median":3.0,"impact":2.40426,"direction":"increases","share_pct":43.2}],"global_importance":[{"feature":"crop_code","label":"Crop type","importance":1.77911}]}}
```

### `GET /api/plots/{plot_id}/water`

**Path parameters:** `plot_id`.  
**Purpose:** FAO-56-style water-plan summary and daily schedule.

```json
{"kc":1.15,"growth_stage":"mid","method":"Drip","application_efficiency":0.9,"next_irrigation":"2026-08-07","week_gross_mm":151.8,"week_litres":5161200,"water_saved_pct":38.9,"schedule":[{"date":"2026-08-07","etc_mm":5.16,"effective_rain_mm":0.0,"depletion_mm":113.8,"irrigate":true,"gross_mm":50.6,"litres":1720400,"minutes":108}]}
```

### `GET /api/plots/{plot_id}/fertilizer`

**Path parameters:** `plot_id`.  
**Purpose:** N/P2O5/K2O target, product conversion, split plan, and next application window.

```json
{"season_target_kg_ha":{"N":145.2,"P2O5":62.5,"K2O":67.5},"products_kg_ha":{"Urea (46-0-0)":262.5,"DAP (18-46-0)":135.9,"MOP (0-0-60)":112.5},"next_dose":{"stage":"mid","share_pct":30.0,"N_kg_ha":43.6,"urea_kg_plot":110.2,"window":"2026-08-09 to 2026-08-13"}}
```

### `GET /api/plots/{plot_id}/pests`

**Path parameters:** `plot_id`.  
**Purpose:** crop-specific pest/disease envelope assessments plus pest and disease model results.

```json
{"plot_id":"plot-01","pests":[{"name":"Brown Plant Hopper","type":"Insect pest","risk":0.611,"level":"High","window":"2026-08-07 to 2026-08-17","envelope":{"temp_c":[25,32],"humidity_pct":[80,100],"favoured_stage":"mid"},"fit":{"temperature":1.0,"humidity":1.0,"stage":1.0}}],"model":{"model":"pest_outbreak","value":0.61069,"confidence":0.776,"metrics":{"roc_auc":0.8103,"accuracy":0.8,"brier":0.1432}}}
```

### `GET /api/plots/{plot_id}/digital-twin`

**Path parameters:** `plot_id`.  
**Purpose:** current state vector plus the water-balance coupled NDVI forward simulation.

```json
{"plot_id":"plot-07","state":{"ndvi":0.6997,"soil_moisture":0.0648,"lai":1.732,"biomass_proxy":2.459,"root_depth_mm":700,"stage":"mid","dap":58},"simulation":[{"date":"2026-08-07","soil_moisture":0.1153,"ndvi":0.7001,"water_stress_index":0.271,"irrigated":true}],"engine":"water-balance coupled NDVI growth twin (daily step)"}
```

---

## Prediction

### `POST /api/predict`

**Body:** `model` is one of `yield`, `pest`, `disease`, `drought`, `flood`, `anomaly`; `features` is an object of numeric feature values. Missing feature keys fall back to that model's training median.  
**Purpose:** score an arbitrary feature vector without retrieving a plot dossier.

```json
{"model":"crop_yield","kind":"regression","unit":"t/ha","value":4.07781,"confidence":0.957,"metrics":{"r2":0.9826,"mae":0.9026,"rmse":1.4868,"mape_pct":15.65,"n_train":4680},"explanation":{"method":"ablation-to-median local attribution + permutation global importance","drivers":[{"feature":"lai","label":"Leaf Area Index","value":2.4,"median":1.2485,"impact":0.24525,"direction":"increases","share_pct":36.3}]}}
```

---

## Advisory and i18n

### `GET /api/i18n/{lang}`

**Path parameters:** `lang`; supported values are `en`, `ta`, `ml`, and `hi`. Unsupported values fall back to English strings.  
**Purpose:** return the compact UI dictionary for a language.

```json
{"lang":"ml","strings":{"dashboard":"ഡാഷ്ബോർഡ്","advisory":"ഉപദേശം","risk":"അപകടസാധ്യത"}}
```

### `GET /api/plots/{plot_id}/advisory`

**Path parameters:** `plot_id`.  
**Query parameters:** `lang` (optional, default `en`); `persist` (optional boolean, default `false`).  
**Purpose:** advisory-only projection of a plot dossier. `persist=true` queues each recommendation into `advisories`.

```json
{"plot_id":"plot-01","language":"ml","health":{"score":87.8,"band":"Excellent"},"risk":{"composite":0.473,"level":"Medium"},"recommendations":[{"id":"plot-01-climate-adaptation-4","category":"Climate adaptation","title":"Fungal disease is the dominant risk (90%)","title_localised":"പ്രധാന അപകടസാധ്യത കുമിൾ രോഗം (90%)","confidence":0.797,"priority":"High","model":"disease_risk"}]}
```

### `POST /api/irrigation/command`

**Body:** `plot_id` required; `valve` optional (default `V1`); `mode` is `auto`, `manual`, or `hold` (default `auto`); `minutes` optional.  
**Purpose:** construct an actuator command using the next irrigation event and persist an actuation advisory.

```json
{"ok":true,"command":{"device":"gateway-plot-07","valve":"V2","mode":"manual","open_minutes":12,"target_mm":50.6,"scheduled_for":"2026-08-07","mqtt_topic":"agrisense/farm-04/plot-07/valve/V2/set"}}
```

### `POST /api/sms`

**Body:** `plot_id` required; `lang` optional (default `en`); `phone` optional and otherwise taken from the farm record.  
**Purpose:** create and queue a localised SMS/IVR/USSD digest in `sms_outbox`.

```json
{"ok":true,"lang":"ta","chars":232,"segments":2,"payload_bytes":540,"channel":"SMS / IVR / USSD — works on a 2G feature phone","body_localised":"அக்ரிசென்ஸ் North Paddy A1 (நெல்) | பயிர் ஆரோக்கியம் 87.8/100 மிகச் சிறந்தது | விளைச்சல் 6.769 டன்/ஹெ (நம்பகம் 91%) | 7 நாள் நீர்ப்பாசனம் தேவையில்லை | பச்சைத் தத்துப்பூச்சி அபாயம் அதிகம் | செய்யவும்: முதன்மை அபாயம் பூஞ்சை நோய் (90%)","queued":{"plot_id":"plot-01","phone":"+919000000001","status":"queued"}}
```

### `GET /api/sms/outbox`

**Parameters:** none.  
**Purpose:** up to 50 queued SMS rows, newest first.

```json
[{"plot_id":"plot-01","phone":"+919000000001","lang":"ta","status":"queued","created_at":"2026-08-07T17:31:28.472295+00:00"}]
```

### `GET /api/offline-bundle`

**Query parameters:** `lang` (optional, default `en`); `plot_id` (optional; omit for all plots).  
**Purpose:** compact advisory packs for offline/2G synchronisation.

```json
{"v":"1.0.0","lang":"en","ttl_hours":24,"packs":[{"p":"plot-01","n":"North Paddy A1","c":"Rice","h":87.8,"y":6.769,"r":0.473,"rl":"Medium","irr":null,"mm":0.0,"n_kg":43.6,"pest":"Brown Plant Hopper","pr":0.611}]}
```

---

## Market and carbon

### `GET /api/market/{crop}`

**Path parameters:** `crop`.  
**Query parameters:** `horizon` (optional, integer 3–45, default `14`).  
**Purpose:** modal-price history and Holt linear trend forecast for a crop.

```json
{"crop":"Rice","mandi":"Thrissur Mandi","model":"Holt linear trend (alpha=0.42, beta=0.18)","latest_price":2379.7,"trend_per_day":4.32,"forecast":[{"date":"2026-08-08","price":2379.79,"low":2365.72,"high":2393.87}],"signal":"Hold — prices trending up, sell after the forecast window"}
```

### `GET /api/plots/{plot_id}/carbon`

**Path parameters:** `plot_id`.  
**Purpose:** plot carbon estimate, component breakdown, mitigation list, and factor provenance label.

```json
{"total_kg_co2e":7471.4,"per_hectare":5336.7,"breakdown":[{"source":"Soil N2O from fertilizer N","kg_co2e":872.2},{"source":"Urea manufacturing (embedded)","kg_co2e":1139.2}],"factors_source":"IPCC 2019 Refinement Vol.4 Ch.11; CEA India grid emission factor 0.71 kg CO2/kWh"}
```

---

## Reference and export

### `GET /api/reference`

**Parameters:** none.  
**Purpose:** crop and soil libraries used by the agronomic services.

```json
{"crops":{"Rice":{"kc":{"initial":1.05,"development":1.1,"mid":1.2,"late":0.9},"duration_days":135,"base_temp":10.0,"n_p_k":[120,60,60],"potential_yield":6.5,"root_depth_mm":400}},"soils":{"Alluvial":{"fc":0.36,"pwp":0.16,"infiltration":12,"ideal_ph":[6.0,7.5]}}}
```

### `GET /api/dataset/export`

**Query parameters:** `table` (optional, default `plots`); use `__all__` for a fresh full demonstration build.  
**Purpose:** export a selected active-repository table, or the whole deterministic demo dataset.

```json
{"table":"plots","rows":12,"data":[{"id":"plot-01","farm_id":"farm-01","name":"North Paddy A1","crop":"Rice","variety":"Jyothi","area_ha":1.4,"sowing_date":"2026-05-31","expected_harvest_date":"2026-10-13","days_after_sowing":68,"growth_stage":"mid","irrigation_type":"Flood","soil_type":"Alluvial"}]}
```
