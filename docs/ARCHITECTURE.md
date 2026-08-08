# Architecture

## System view

```text
                                  ┌──────────────────────────────────┐
                                  │ React + Vite frontend             │
                                  │ Overview · GIS · Plot dossier     │
                                  │ Advisory/SMS · Benchmark          │
                                  └───────────────┬──────────────────┘
                                                  │ HTTPS / JSON
                                                  ▼
┌───────────────────────────────────────────────────────────────────────────────┐
│ FastAPI application (`app.main`)                                                │
│ CORS · GZip (>600 B) · 45 s in-process bundle cache · typed exception guard   │
├───────────────┬───────────────────┬──────────────────────┬─────────────────────┤
│ API routes    │ Repository        │ Feature + advisory   │ Prediction engine   │
│ system/GIS    │ Supabase →        │ services             │ scikit-learn        │
│ plot/actions  │ SQLite → demo     │ water/NPK/risk/SMS   │ 6 model entries     │
└───────┬───────┴─────────┬─────────┴──────────┬───────────┴──────────┬──────────┘
        │                 │                    │                      │
        │                 │                    │                      │
        │                 ▼                    ▼                      ▼
        │       ┌────────────────┐   ┌────────────────────┐  ┌──────────────────┐
        │       │ Supabase       │   │ SQLite mirror       │  │ In-process demo  │
        │       │ PostgreSQL     │   │ snapshot/write queue│  │ `dataset.build`  │
        │       └────────────────┘   └────────────────────┘  └──────────────────┘
        │
        ▼
  JSON responses, offline bundle, SMS/IVR/USSD payload, and irrigation command
```

## Data flow: ingest to advisory

1. **Populate data.** `dataset.build_all()` creates deterministic farm, plot, sensor, satellite, forecast, cultivation-history, and market-price rows. `app.seed` sends those read tables to Supabase in batches. In a production integration, these builders are the natural adapter boundary for external telemetry, satellite, forecast, and market feeds.
2. **Resolve the source.** `Repository` first attempts Supabase. A successful remote load is copied into SQLite; an existing SQLite snapshot is used when remote data is unavailable; otherwise the in-process dataset is generated and persisted.
3. **Build plot features.** `services.build_features()` selects recent sensor and satellite records, forecast rows, soil/crop parameters, and plot history. It derives canopy, hydrologic, weather, nutrient, drainage, elevation, and anomaly inputs.
4. **Score the models.** `PredictionEngine` returns crop yield, pest outbreak, disease risk, drought stress, flood impact, and climate anomaly scores with confidence, local drivers, and global feature importance.
5. **Calculate agronomy.** The services layer computes crop health, soil quality, FAO-56-style water balance, yield-goal NPK prescription, crop-specific pest envelopes, a price outlook, and carbon estimate.
6. **Rank and localise actions.** `build_recommendations()` ranks irrigation, fertilizer, pest, climate, harvest, and rotation advisories. `i18n.translate()` localises supported advisory patterns and then performs a glossary substitution fallback.
7. **Deliver.** The API returns full plot dossiers, compact offline packs, and SMS/IVR/USSD digest payloads. The frontend renders the results as fleet, map, per-plot, advisory, and benchmark views.

## Multimodal fusion layer

| Input modality | Stored/derived values used by the implementation | Role in decisions |
|---|---|---|
| Satellite indices | Blue, red, NIR, SWIR; NDVI, EVI, SAVI, NDWI, NDRE, LAI, chlorophyll index, cloud percentage | Canopy state, recent NDVI mean/peak/trend, water index, plot health, yield, risk, management zones |
| IoT-style sensor telemetry | Soil moisture, pH, temperature, EC; air temperature; humidity; rainfall; wind; ET0; leaf wetness | Root-zone water state, disease and pest conditions, weather aggregates, growing degree days |
| Weather forecast | Temperature, rainfall, rain probability, humidity, wind, ET0 | Seven-day rainfall, irrigation scheduling, decision windows, actuator rain interlock |
| Soil library | Field capacity, permanent wilting point, infiltration, ideal pH range | Water availability, depletion/RAW trigger, drainage score, pH and salinity interpretation |
| Crop library | Stage-specific Kc, duration, base temperature, potential yield, nutrient targets, root depth, rotation | GDD, ETc, water plan, yield reference, fertilizer prescription, crop-rotation action |
| Cultivation history | Yield, seasonal rain, N/P/K, irrigation, mean NDVI, pest incidence | Historical yield comparator, N/irrigation features, NDVI baseline for anomaly score |
| Market prices | Historical modal/min/max prices and arrivals | Holt linear trend forecast and harvest-timing signal |

The service code computes the vegetation indices from raw reflectance and exposes the formulas via `POST /api/indices`; the demonstration dataset stores compatible synthetic scenes. The current demo does not fetch live imagery or telemetry itself.

## Module responsibilities

| Module | Responsibility |
|---|---|
| `app/config.py` | Environment parsing, API identity, local data paths, crop/soil/pest libraries, language list |
| `app/dataset.py` | Seeded, deterministic builders for demo farms, plots, sensor records, satellite-style scenes, forecast, history, and prices |
| `app/repository.py` | Three-tier reads, SQLite snapshot persistence, local write queue, and Supabase replay |
| `app/ml.py` | Synthetic training corpus, feature schemas, model fitting, scoring, confidence, and explainability |
| `app/services.py` | Feature engineering, index calculation, health/soil scoring, irrigation, fertilizer, pests, carbon, price, digital twin, recommendations, SMS digest |
| `app/i18n.py` | Offline pattern-based localisation with glossary fallback for English, Tamil, Malayalam, and Hindi |
| `app/main.py` | Lifespan initialisation, API models/routes, cache, middleware, typed unhandled-exception response |
| `app/seed.py` | Idempotent Supabase demo-data load in 500-row batches |
| `supabase/schema.sql` | PostgreSQL tables, indexes, views, RLS enablement, and read policies |
| `frontend/src/lib/api.ts` | Browser API base selection and typed-agnostic GET/POST client functions |
| `frontend/src/App.tsx` and `frontend/src/pages/` | Page routing/state and dashboard, GIS, dossier, advisory, and model benchmark views |

## Database schema

| Table | Purpose and key structure |
|---|---|
| `farms` | Farm identity, owner/contact, village/district/state, location, area, soil type, language, and creation time. `id` is the text primary key. |
| `plots` | Plot identity and `farm_id` foreign key, crop/variety, area, sowing and harvest dates, stage, irrigation/soil, centroid, GeoJSON geometry, stress index. Deleting a farm cascades to plots. |
| `sensor_readings` | Daily plot telemetry: soil, air, rainfall, wind, ET0, and leaf-wetness variables. Unique on `(plot_id, ts)` and indexed by plot/date descending. |
| `satellite_scenes` | Per-plot scene metadata, raw bands, vegetation indices, LAI/chlorophyll, cloud percentage, and resolution. Unique on `(plot_id, capture_date)` and indexed by plot/date descending. |
| `weather_forecast` | Per-plot daily forecast with temperature, rain, humidity, wind, ET0, and source. Unique on `(plot_id, forecast_date)`. |
| `cultivation_history` | Seasonal plot outcomes and inputs: crop, variety, yield, rainfall, N/P/K, irrigation, mean NDVI, and pest incidence. Unique on `(plot_id, year, season)`. |
| `market_prices` | Crop/mandi/date market observations with modal/min/max prices and arrivals. Unique on `(crop, mandi, price_date)`. |
| `predictions` | Persistable AI outputs: model, kind, value, unit, confidence, JSON features/explanation, and timestamp. It is indexed by plot and creation time. |
| `advisories` | Persistable advisory category, messages, language, priority, confidence, JSON evidence, status, and timestamp. It is indexed by plot and creation time. |
| `sms_outbox` | Queued farmer-delivery rows with plot, phone, body, language, status, and timestamp. |

`v_latest_scene` selects the most recent satellite scene per plot. `v_plot_dashboard` joins plot/farm data with that scene and latest soil moisture/pH readings.

## Offline and low-bandwidth design

- **Data resilience:** the repository's resolution order is Supabase, then SQLite snapshot, then the deterministic demo corpus. A snapshot is written after a successful remote bootstrap and after building the demo tier.
- **Write queue and replay:** `Repository.insert()` appends writes to the local `write_queue` before attempting Supabase. At a successful Supabase bootstrap, `_flush_queue()` iterates pending rows and marks each successfully pushed row.
- **Offline advisory pack:** `GET /api/offline-bundle` returns a compact key-based packet with a 24-hour TTL, per-plot metrics, top actions, and a localised SMS digest. GZip middleware compresses responses at or above 600 bytes.
- **Feature-phone fallback:** `POST /api/sms` creates a localised digest tagged `SMS / IVR / USSD — works on a 2G feature phone` and queues it to `sms_outbox`. The code provides the payload and persistence queue; it does not implement an external SMS, IVR, USSD, or SMPP provider.
- **Network-efficient recomputation:** the FastAPI process caches each plot/language full analysis bundle for 45 seconds.

## Edge-inference posture

The backend has no network call in the prediction path: it builds features from the active repository and scores in-process scikit-learn estimators initialised at startup. Localisation is also offline and rule/glossary based. This makes the computation suitable for a gateway deployment when the data mirror is present. The repository does not currently serialise or ship a model artifact, and no hardware size or latency guarantee is encoded in the backend; deployment sizing should therefore be measured on the intended gateway.

## Fault tolerance and security

### Fault tolerance

- Startup resolves the data tier and trains/warms the prediction engine once through the FastAPI lifespan handler.
- The global `Exception` handler converts otherwise unhandled exceptions to a typed JSON `422` body with `ok`, `error`, `detail`, and a cached-advisory hint instead of an HTTP `500`.
- Expected resource misses deliberately remain FastAPI `404` responses, and Pydantic request validation uses its standard `422` validation body.
- SQLite writes are protected with a process lock; failed remote writes remain locally queued.

### Security posture

- `schema.sql` enables row-level security on all ten base tables and creates a `SELECT` policy for each table.
- There is no anonymous insert/update policy in the supplied schema. A Supabase service-role key bypasses RLS for backend-side seeding and writes; direct anon-key writes are denied by RLS.
- The frontend calls FastAPI rather than Supabase directly. Keep `SUPABASE_SERVICE_ROLE_KEY` only in `backend/.env` and never expose it to the browser.
- The current API enables permissive CORS (`allow_origins=["*"]`). A production deployment should replace that with explicit trusted origins and add authentication/authorisation before exposing farm data or actuator commands.

## Scalability notes

- The API's route handlers are largely stateless with respect to request payloads, while each worker owns its in-memory repository, model engine, and 45-second cache.
- Supabase/PostgreSQL has foreign keys plus indexes for farm/plot joins and time-series plot reads; the demo repository preloads read tables into memory rather than issuing per-feature database queries.
- The current SQLite mirror and in-process cache are per-process, so multi-worker or multi-node deployments need a shared queue/cache and explicit model/version distribution for consistent replay and cache behavior.
- `seed.py` batches records in groups of 500. For sustained production ingestion, replace demo builders with durable ingest jobs and retain the existing repository interface as the serving boundary.
