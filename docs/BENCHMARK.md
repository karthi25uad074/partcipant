# Model Benchmark

## Scope and provenance

The live `GET /api/benchmark` capture used for this document was generated at `2026-08-07T17:31:26.871129+00:00`. It reports a 6,000-row corpus with seed 7 and a 78/22 train-test split. The supervised models train on 4,680 rows; the anomaly detector is fit on the full feature matrix.

## Model inventory

| Model | Algorithm in `app/ml.py` | Task | Feature count | Held-out / fit metrics from `/api/benchmark` |
|---|---|---:|---:|---|
| `crop_yield` | `GradientBoostingRegressor` | Regression, t/ha | 12 | R² 0.9826; MAE 0.9026 t/ha; RMSE 1.4868 t/ha; MAPE 15.65%; training rows 4,680 |
| `pest_outbreak` | `RandomForestClassifier` | Binary classification | 8 | ROC-AUC 0.8103; accuracy 0.8000; Brier 0.1432; positive rate 0.2515; training rows 4,680 |
| `disease_risk` | `HistGradientBoostingClassifier` | Binary classification | 7 | ROC-AUC 0.8159; accuracy 0.7568; Brier 0.1675; positive rate 0.3333; training rows 4,680 |
| `drought_stress` | `HistGradientBoostingClassifier` | Binary classification | 7 | ROC-AUC 0.8779; accuracy 0.8182; Brier 0.1325; positive rate 0.2985; training rows 4,680 |
| `flood_impact` | `HistGradientBoostingClassifier` | Binary classification | 6 | ROC-AUC 0.8765; accuracy 0.8886; Brier 0.0819; positive rate 0.1295; training rows 4,680 |
| `climate_anomaly` | `IsolationForest` with 220 estimators | Unsupervised anomaly score | 4 | Contamination 0.06 |

The implementation therefore serves five supervised outputs and one unsupervised anomaly output.

## Training corpus and split

`_corpus(n=6000)` in `app/ml.py` uses `numpy.random.default_rng(7)` to generate a physiologically parameterised synthetic dataset. It contains values for crop code; satellite/canopy variables; rainfall, GDD, soil, fertility, irrigation, temperature, humidity, leaf wetness, wind, ET0; hydrologic factors; and anomaly features.

Target generation is explicitly encoded in the same function:

- Yield is generated from crop potential yield, vegetation condition, pH, seasonal water supply, temperature, nitrogen response, soil moisture, GDD, and multiplicative random noise.
- Pest probability is driven by centred humidity, leaf wetness, seven-day rain, canopy state, wind, temperature fit, and NDVI trend.
- Disease probability gives large weight to humidity, leaf wetness, three-day rain, canopy water, soil moisture, and temperature fit.
- Drought probability responds to moisture deficit, soil moisture, NDWI, NDVI trend, rain, ET0, and temperature.
- Flood probability responds to three- and seven-day rain, soil moisture, drainage, elevation, and NDWI.
- Anomaly inputs are standardized deviations of NDVI, temperature, rainfall, and humidity against the corpus normal values.

For each supervised model, `train_test_split(..., test_size=0.22, random_state=7)` creates the 78/22 split. The code does not pass a `stratify` argument. Regression metrics are calculated on the held-out rows with `r2_score`, MAE, RMSE, and MAPE. Classification metrics are calculated from held-out positive-class probabilities with ROC-AUC, thresholded accuracy at 0.5, Brier score, and held-out positive rate.

## Feature sets and top global drivers

| Model | Feature set | Top three global drivers returned by `/api/benchmark` |
|---|---|---|
| `crop_yield` | `ndvi_mean`, `ndvi_peak`, `ndvi_trend`, `lai`, `rainfall_mm`, `gdd`, `soil_moisture`, `soil_ph`, `fert_n`, `irrigation_mm`, `temp_mean`, `crop_code` | Crop type; NDVI 30-day trend; Soil pH |
| `pest_outbreak` | `temp_mean`, `humidity`, `leaf_wetness`, `rain_7d`, `ndvi_mean`, `ndvi_trend`, `wind_kph`, `crop_code` | Mean relative humidity; Leaf wetness hours; Mean air temperature |
| `disease_risk` | `humidity`, `leaf_wetness`, `temp_mean`, `rain_3d`, `ndwi_mean`, `soil_moisture`, `crop_code` | Mean relative humidity; Leaf wetness hours; Mean air temperature |
| `drought_stress` | `soil_moisture`, `moisture_deficit`, `ndwi_mean`, `ndvi_trend`, `rain_7d`, `et0`, `temp_mean` | Root-zone soil moisture; NDVI 30-day trend; 7-day rainfall total |
| `flood_impact` | `rain_3d`, `rain_7d`, `soil_moisture`, `drainage_score`, `elevation_idx`, `ndwi_mean` | 3-day rainfall total; Relative elevation index; Root-zone soil moisture |
| `climate_anomaly` | `ndvi_anomaly`, `temp_anomaly`, `rain_anomaly`, `humidity_anomaly` | NDVI anomaly vs 6-season history; Temperature anomaly; Rainfall anomaly |

## Live latency capture

The same live benchmark response measured:

| Operation | Captured latency |
|---|---:|
| Feature engineering for the first plot | 1.49 ms |
| Full plot analysis bundle | 495.23 ms |

These are a point-in-time in-process probe, not a service-level objective. The full bundle runs feature engineering, all prediction calls and explanations, agronomic calculations, recommendations, and related dossier content, so it is affected by machine load and cache state.

## Explainability methodology

Every model response returns the method label **“ablation-to-median local attribution + permutation global importance.”**

### Local attribution

For the current row, the engine:

1. Scores the unmodified feature vector.
2. Replaces one feature at a time with that feature’s training median.
3. Re-scores the modified vector.
4. Records the signed difference between original and modified output as `impact`, labels it as increasing/decreasing/neutral, and normalises absolute impacts into `share_pct`.

This is model-agnostic and uses no SHAP dependency. For a live `plot-01` yield explanation, the captured top local driver was crop type: value 5.0 versus median 3.0, impact 2.40426, and 43.2% of the absolute local impact share.

### Global importance

For supervised models, the engine calls scikit-learn `permutation_importance` on the held-out set with 6 repeats and seed 7, then sorts mean importances descending. The anomaly model has no held-out supervised target, so its global importance response assigns equal importance, 0.25, to each of its 4 features.

## Mapping to the evaluation metrics

| Evaluation need | Metric reported by the implementation | Interpretation within this benchmark |
|---|---|---|
| Yield-estimate quality | R², MAE, RMSE, MAPE | Agreement between predicted and held-out synthetic yield in t/ha; R² reflects explained variance, MAE/RMSE the synthetic-yield error, and MAPE the relative error. |
| Pest, disease, drought, flood discrimination | ROC-AUC | Ranking ability between positive and negative labels in held-out synthetic rows. |
| Operational classification accuracy | Accuracy at probability threshold 0.5 | Fraction of held-out synthetic labels correctly classified by the fixed threshold. |
| Probability calibration | Brier score | Mean squared error of the predicted probability relative to the synthetic binary outcome; lower is better. |
| Event prevalence | Positive rate | Proportion of positive outcomes in that model’s held-out synthetic test rows. |
| Rare/unusual climate conditions | IsolationForest contamination | Configured fraction used by the unsupervised detector; it is not an accuracy metric. |
| Decision transparency | Local impact shares and permutation ranking | Why a specific score moved and which held-out inputs the model depends on most. |
| Runtime feasibility | Feature and full-bundle latency probes | Point measurements of serving work on the running process. |

## Honest limitations

1. **The corpus is physiologically-parameterised synthetic data, not field-measured ground truth.** The reported R², ROC-AUC, accuracy, Brier, MAE, RMSE, and MAPE therefore measure recovery of the generative process written in `_corpus()`; they are not field-validated agronomic accuracy.
2. The demonstration satellite scenes, sensor records, forecasts, cultivation history, and prices are deterministic generated data. They are useful for exercising response shapes and decision logic, not for claiming live observations.
3. The classification outputs represent modelled favourable-condition probability. The advisory engine therefore includes scouting instructions; the output is not confirmation of an infestation or disease diagnosis.
4. The anomaly output is an IsolationForest-derived score transformed from `score_samples`; its configured 0.06 contamination is a model setting, not a validated detection rate.
5. Price forecasting uses Holt linear trend on the stored modal-price series and has no explicit exogenous policy, logistics, demand, or market-shock inputs.
6. The full-bundle latency is measured inside the live API process and should be repeated on the target deployment hardware and workload before making an edge performance claim.

## Retraining on real records

The explicit replacement point is `_corpus()` in `backend/app/ml.py`.

1. Assemble real, aligned historical records at a consistent plot/season or event time grain. Keep feature names used by the model lists: `YIELD_FEATURES`, `PEST_FEATURES`, `DISEASE_FEATURES`, `DROUGHT_FEATURES`, `FLOOD_FEATURES`, and `ANOMALY_FEATURES`.
2. Replace the body of `_corpus()` so it returns a dictionary of NumPy arrays with all required feature keys and the supervised target keys `y_yield`, `y_pest`, `y_disease`, `y_drought`, and `y_flood`. Preserve numeric arrays and compatible units; `crop_code` must remain compatible with `CROP_CODES` or be recoded consistently.
3. Replace synthetic target construction with field-measured yield and properly defined/quality-controlled incident labels. Decide and document label windows before splitting data to avoid temporal leakage.
4. Keep or revise the `train_test_split` logic in `_fit()` for the required validation design. For real deployment data, a time-based or farm/plot-group holdout is usually more informative than the current random split; this is a required code change if selected.
5. Restart the backend. `get_engine()` creates a new `PredictionEngine` at application startup, calls the replacement corpus function, refits all models, recalculates metrics and permutation importance, and exposes the updated results through `/api/benchmark`.
6. Validate by location, crop, season, and event prevalence before using the results operationally. The existing confidence score combines nominal model skill with distance from training medians; it does not substitute for external field validation.
