import { useEffect, useMemo, useState } from 'react';
import {
  Bar, BarChart, CartesianGrid, Cell, PolarAngleAxis, PolarGrid, Radar, RadarChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import { Beaker, Calculator, Code2, Cpu, Database, Gauge, Timer } from 'lucide-react';
import { api, API_BASE } from '../lib/api';
import { Badge, cx, fmt, fmtInt, Loading, Meter, Panel } from '../lib/ui';

const ENDPOINTS: [string, string, string][] = [
  ['GET', '/api/health', 'Liveness + active data tier + row counts'],
  ['GET', '/api/overview', 'Fleet KPIs, ranked plots, alert queue, district/crop rollups'],
  ['GET', '/api/geojson', 'FeatureCollection of plot boundaries with live properties'],
  ['GET', '/api/risk-map', 'District-level composite risk surface'],
  ['GET', '/api/plots/{id}', 'Full plot dossier — features, health, soil, water, NPK, pests, 6 predictions, recommendations'],
  ['GET', '/api/plots/{id}/advisory', 'Recommendation set only, localised'],
  ['GET', '/api/plots/{id}/explain/{model}', 'Local attribution + global permutation importance'],
  ['GET', '/api/plots/{id}/satellite', 'Cloud-filtered scene series with all indices'],
  ['GET', '/api/plots/{id}/ndvi-grid', 'Sub-plot NDVI raster and management zones'],
  ['GET', '/api/plots/{id}/water', 'FAO-56 dual-Kc irrigation schedule'],
  ['GET', '/api/plots/{id}/fertilizer', 'Yield-goal NPK prescription with split plan'],
  ['GET', '/api/plots/{id}/pests', 'Pest and disease envelope assessment'],
  ['GET', '/api/plots/{id}/carbon', 'IPCC-factor carbon footprint breakdown'],
  ['GET', '/api/plots/{id}/digital-twin', 'Water-balance coupled growth simulation'],
  ['GET', '/api/market/{crop}', 'Mandi price history + Holt linear forecast'],
  ['GET', '/api/benchmark', 'Model metrics, latency and corpus provenance'],
  ['GET', '/api/i18n/{lang}', 'Localised UI dictionary'],
  ['GET', '/api/reference', 'Crop and soil libraries (Kc, NPK, ideal pH…)'],
  ['GET', '/api/offline-bundle', 'Compact multi-plot payload for offline use'],
  ['GET', '/api/dataset/export', 'Full demonstration dataset export'],
  ['POST', '/api/indices', 'Compute NDVI/EVI/SAVI/NDWI/MSAVI/LAI from raw bands'],
  ['POST', '/api/predict', 'Run any model on an arbitrary feature vector'],
  ['POST', '/api/irrigation/command', 'Issue a gateway valve command with interlocks'],
  ['POST', '/api/sms', 'Generate and queue a localised SMS advisory'],
];

export default function Models() {
  const [b, setB] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [bands, setBands] = useState({ blue: 0.06, red: 0.09, nir: 0.42, swir: 0.21 });
  const [idx, setIdx] = useState<any>(null);

  useEffect(() => { api.benchmark().then(setB).catch((e) => setErr(e.message)); }, []);
  useEffect(() => {
    const t = setTimeout(() => { api.indices(bands).then(setIdx).catch(() => setIdx(null)); }, 180);
    return () => clearTimeout(t);
  }, [bands]);

  const chart = useMemo(() => {
    if (!b) return [];
    return b.models.map((m: any) => ({
      name: m.model.replace(/_/g, ' '),
      score: m.metrics.roc_auc ?? m.metrics.r2 ?? 0,
      kind: m.task,
    })).filter((m: any) => m.score > 0);
  }, [b]);

  const radar = useMemo(() => chart.map((c: any) => ({
    metric: c.name, value: +(c.score * 100).toFixed(1),
  })), [chart]);

  if (err) return <Panel title="Benchmark unavailable"><p className="text-[12px] text-rose">{err}</p></Panel>;
  if (!b) return <div className="panel p-6"><Loading rows={6} label="Loading benchmark report…" /></div>;

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {[
          ['Training rows', fmtInt(b.training_corpus.rows), `seed ${b.training_corpus.seed} · ${b.training_corpus.split}`],
          ['Models in service', b.models.length, 'GBM · RF · HGB · IsolationForest'],
          ['Feature engineering', `${fmt(b.latency_ms?.feature_engineering_ms ?? 0, 2)} ms`, 'per plot, 12-feature vector'],
          ['Full dossier', `${fmt(b.latency_ms?.full_bundle_ms ?? 0, 0)} ms`, 'all 6 models + advisory, single CPU'],
        ].map(([l, v, s]: any) => (
          <div key={l} className="panel px-4 py-3.5">
            <p className="label">{l}</p>
            <p className="num mt-1.5 text-[20px] font-bold leading-none text-ink">{v}</p>
            <p className="mt-1.5 text-[10.5px] leading-snug text-faint">{s}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
        <Panel className="xl:col-span-2" title="Model accuracy benchmark"
          subtitle="ROC-AUC for classifiers, R² for the yield regressor — held-out test split, never seen in training"
          bodyClass="p-0">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[680px] text-left">
              <thead><tr className="border-b border-line">
                {['Model', 'Task', 'Feat.', 'Headline metric', 'Secondary', 'Top drivers'].map((h) => (
                  <th key={h} className="label px-5 py-2.5 font-semibold">{h}</th>
                ))}
              </tr></thead>
              <tbody>
                {b.models.map((m: any) => {
                  const headline = m.metrics.roc_auc ?? m.metrics.r2;
                  const isAuc = m.metrics.roc_auc !== undefined;
                  return (
                    <tr key={m.model} className="border-b border-line/60 last:border-0">
                      <td className="px-5 py-3 text-[12.5px] font-semibold text-ink">{m.model.replace(/_/g, ' ')}</td>
                      <td className="px-5 py-3"><Badge tone={m.task === 'regression' ? 'sky' : m.task === 'anomaly' ? 'violet' : 'leaf'}>{m.task}</Badge></td>
                      <td className="num px-5 py-3 text-[12px] text-muted">{m.features}</td>
                      <td className="px-5 py-3">
                        {headline !== undefined ? (
                          <div className="min-w-[112px]">
                            <p className="num text-[12.5px] font-bold text-ink">
                              {isAuc ? 'ROC-AUC' : 'R²'} {fmt(headline, 4)}
                            </p>
                            <div className="mt-1"><Meter value={headline * 100} tone={headline >= 0.85 ? 'leaf' : 'amber'} height={4} /></div>
                          </div>
                        ) : <span className="num text-[11.5px] text-faint">unsupervised</span>}
                      </td>
                      <td className="num px-5 py-3 text-[11px] leading-relaxed text-muted">
                        {Object.entries(m.metrics)
                          .filter(([k]) => !['roc_auc', 'r2'].includes(k))
                          .map(([k, v]: any) => `${k.replace(/_/g, ' ')} ${typeof v === 'number' ? (v > 100 ? fmtInt(v) : fmt(v, 4)) : v}`)
                          .join(' · ')}
                      </td>
                      <td className="px-5 py-3 text-[11px] leading-relaxed text-faint">
                        {m.top_drivers.join(', ')}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="h-[220px] px-3 pb-4 pt-2">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chart} margin={{ top: 6, right: 10, left: -22, bottom: 0 }}>
                <CartesianGrid stroke="hsl(var(--line))" vertical={false} />
                <XAxis dataKey="name" tickLine={false} axisLine={false} tick={{ fontSize: 9.5 }}
                  angle={-16} textAnchor="end" height={46} interval={0} />
                <YAxis domain={[0, 1]} tickLine={false} axisLine={false} />
                <Tooltip contentStyle={{ background: 'hsl(var(--surface))', border: '1px solid hsl(var(--line))', borderRadius: 12, fontSize: 12 }}
                  formatter={(v: any) => [fmt(v, 4), 'score']} />
                <Bar dataKey="score" radius={[6, 6, 0, 0]} maxBarSize={54}>
                  {chart.map((c: any, i: number) => (
                    <Cell key={i} fill={c.score >= 0.85 ? 'hsl(88 62% 55%)' : 'hsl(36 92% 58%)'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Panel>

        <div className="space-y-5">
          <Panel title="Skill profile" subtitle="Normalised headline score per model" bodyClass="p-3">
            <div className="h-[230px]">
              <ResponsiveContainer width="100%" height="100%">
                <RadarChart data={radar} outerRadius="72%">
                  <PolarGrid stroke="hsl(var(--line))" />
                  <PolarAngleAxis dataKey="metric" tick={{ fontSize: 9, fill: 'hsl(var(--faint))' }} />
                  <Radar dataKey="value" stroke="hsl(88 62% 55%)" strokeWidth={2}
                    fill="hsl(88 62% 55%)" fillOpacity={0.24} />
                  <Tooltip contentStyle={{ background: 'hsl(var(--surface))', border: '1px solid hsl(var(--line))', borderRadius: 12, fontSize: 12 }} />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          </Panel>

          <Panel title="Index calculator" subtitle="Live NDVI/EVI/SAVI from raw surface reflectance"
            bodyClass="p-4">
            <div className="space-y-2.5">
              {(['blue', 'red', 'nir', 'swir'] as const).map((k) => (
                <div key={k}>
                  <div className="flex items-baseline justify-between">
                    <span className="label">{k === 'nir' ? 'NIR B8' : k === 'swir' ? 'SWIR B11' : k === 'red' ? 'Red B4' : 'Blue B2'}</span>
                    <span className="num text-[11px] font-semibold text-ink">{fmt(bands[k], 3)}</span>
                  </div>
                  <input type="range" min={0.01} max={0.7} step={0.005} value={bands[k]}
                    data-testid={`slider-${k}`}
                    onChange={(e) => setBands((s) => ({ ...s, [k]: +e.target.value }))}
                    className="mt-1 h-1.5 w-full cursor-pointer appearance-none rounded-full bg-raised accent-leaf" />
                </div>
              ))}
            </div>
            {idx && (
              <div className="mt-3 grid grid-cols-3 gap-2 border-t border-line pt-3">
                {['ndvi', 'evi', 'savi', 'ndwi', 'msavi', 'lai'].map((k) => (
                  <div key={k} className="rounded-xl border border-line bg-raised/40 px-2 py-1.5">
                    <p className="label">{k}</p>
                    <p className="num mt-0.5 text-[12.5px] font-bold text-ink">{fmt(idx[k], 3)}</p>
                  </div>
                ))}
              </div>
            )}
            {idx?.formulas && (
              <div className="mt-2.5 space-y-1 rounded-xl border border-line bg-raised/40 p-2.5">
                {Object.entries(idx.formulas).slice(0, 4).map(([k, v]: any) => (
                  <p key={k} className="num text-[9.5px] leading-relaxed text-faint">
                    <span className="uppercase text-muted">{k}</span> = {v}
                  </p>
                ))}
              </div>
            )}
          </Panel>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        <Panel title="REST API reference" subtitle={`${ENDPOINTS.length} endpoints · base ${API_BASE}`}
          bodyClass="p-0">
          <table className="w-full text-left">
            <tbody>
              {ENDPOINTS.map(([m, path, desc]) => (
                <tr key={path + m} className="row-hover border-b border-line/50 last:border-0">
                  <td className="px-5 py-2.5 align-top">
                    <span className={cx('num rounded px-1.5 py-0.5 text-[9.5px] font-bold',
                      m === 'GET' ? 'bg-leaf/15 text-leaf' : 'bg-violet/15 text-violet')}>{m}</span>
                  </td>
                  <td className="num px-2 py-2.5 align-top text-[11px] font-semibold text-ink">{path}</td>
                  <td className="px-5 py-2.5 align-top text-[10.5px] leading-snug text-faint">{desc}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>

        <div className="space-y-5">
          <Panel title="Methodology & provenance" bodyClass="space-y-3 p-4"
            subtitle="What is modelled, and with which published method">
            {[
              { icon: Calculator, tone: 'leaf', t: 'Water balance', b: 'FAO-56 dual crop coefficient with stage-wise Kc, USDA-SCS effective rainfall, and root-zone depletion triggered at readily-available water. One event refills at most RAW.' },
              { icon: Beaker, tone: 'violet', t: 'Nutrient prescription', b: 'Yield-goal targeting against crop NPK removal, modulated by soil pH, EC, predicted-vs-potential yield and organic-matter substitution. Split across four phenological windows.' },
              { icon: Gauge, tone: 'sky', t: 'Spectral indices', b: 'NDVI (Rouse 1974), EVI (Huete 1997), SAVI (Huete 1988), NDWI (Gao 1996), MSAVI (Qi 1994). LAI from Beer-Lambert canopy inversion.' },
              { icon: Cpu, tone: 'amber', t: 'Explainability', b: 'Local attribution by ablating each feature to the training median and measuring output displacement; global ranking by permutation importance on held-out data. Deterministic and cheap enough for edge inference.' },
              { icon: Database, tone: 'rose', t: 'Emission factors', b: 'IPCC 2019 Refinement Vol.4 Ch.11 for direct soil N₂O, CEA India grid factor 0.71 kg CO₂/kWh for pumping energy, and paddy CH₄ scaling for flooded rice.' },
            ].map((s) => (
              <div key={s.t} className="rounded-xl border border-line bg-raised/40 p-3">
                <Badge tone={s.tone}><s.icon size={11} /> {s.t}</Badge>
                <p className="mt-2 text-[11px] leading-relaxed text-muted">{s.b}</p>
              </div>
            ))}
          </Panel>

          <Panel title="Honest limitations" bodyClass="p-4"
            subtitle="What a judge should know before trusting the numbers">
            <ul className="space-y-2">
              {[
                'Models are trained on a physiologically-parameterised synthetic corpus, not on field-measured ground truth. The reported R² and ROC-AUC measure how well the learner recovers that generative process — they are not field-validated accuracy.',
                'Satellite scenes in the demonstration tier are simulated with realistic phenology, cloud gaps and band relationships. Swapping in a real Sentinel-2 fetch only changes the ingest adapter, not the pipeline.',
                'Pest and disease models predict favourable-condition probability, not confirmed infestation. Scouting confirmation is required before any chemical application, which is why every pest card ships a scouting threshold.',
                'Price forecasts use a Holt linear trend on modal mandi prices and carry no exogenous drivers (policy, export bans, festival demand), so the band widens quickly beyond a fortnight.',
              ].map((t, i) => (
                <li key={i} className="flex gap-2 text-[11px] leading-relaxed text-muted">
                  <span className="num mt-0.5 shrink-0 text-faint">{String(i + 1).padStart(2, '0')}</span>{t}
                </li>
              ))}
            </ul>
          </Panel>

          <Panel title="Stack" bodyClass="p-4">
            <div className="flex flex-wrap gap-2">
              {['React 18', 'Vite', 'TypeScript', 'Tailwind CSS', 'Recharts', 'Leaflet', 'FastAPI',
                'Pydantic v2', 'scikit-learn', 'NumPy', 'Supabase Postgres', 'SQLite mirror', 'Uvicorn'].map((t) => (
                <span key={t} className="chip border-line text-muted">{t}</span>
              ))}
            </div>
            <p className="mt-3 flex items-start gap-1.5 text-[10.5px] leading-relaxed text-faint">
              <Code2 size={12} className="mt-0.5 shrink-0 text-leaf" />
              {/* One span keeps the sentence as a single flex item, otherwise each text
                  node and each URL becomes its own flex child and the line breaks apart. */}
              <span className="min-w-0 break-words">
                Interactive OpenAPI docs are served by the backend itself at{' '}
                <span className="num text-muted">{API_BASE}/docs</span> (Swagger UI) and{' '}
                <span className="num text-muted">{API_BASE}/redoc</span>.
              </span>
            </p>
            <p className="mt-2 flex items-start gap-1.5 text-[10.5px] leading-relaxed text-faint">
              <Timer size={12} className="mt-0.5 shrink-0 text-leaf" />
              <span className="min-w-0">
                Benchmark generated {String(b.generated_at).slice(0, 19).replace('T', ' ')} UTC.
              </span>
            </p>
            {b.notes?.length > 0 && (
              <ul className="mt-3 space-y-1.5 border-t border-line pt-3">
                {b.notes.map((n: string, i: number) => (
                  <li key={i} className="text-[10.5px] leading-relaxed text-faint">· {n}</li>
                ))}
              </ul>
            )}
          </Panel>
        </div>
      </div>
    </div>
  );
}
