import { useEffect, useMemo, useState } from 'react';
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, ComposedChart, Legend, Line,
  ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import {
  Beaker, Bug, CalendarClock, CircleDollarSign, Cpu, Droplets, FlaskConical,
  Gauge, History, Leaf, Radio, Satellite, Sprout, Waves, Wind, Zap,
} from 'lucide-react';
import { api } from '../lib/api';
import {
  Badge, Confidence, cx, ErrorState, fmt, fmtInt, healthColor, levelTone,
  litres, Loading, Meter, ndviColor, Panel, pct,
} from '../lib/ui';

const MODEL_KEYS = [
  { key: 'yield', api: 'yield', label: 'Crop yield', icon: Sprout },
  { key: 'pest_outbreak', api: 'pest', label: 'Pest outbreak', icon: Bug },
  { key: 'disease_risk', api: 'disease', label: 'Disease risk', icon: FlaskConical },
  { key: 'drought_stress', api: 'drought', label: 'Drought stress', icon: Waves },
  { key: 'flood_impact', api: 'flood', label: 'Flood impact', icon: Droplets },
  { key: 'climate_anomaly', api: 'anomaly', label: 'Climate anomaly', icon: Wind },
];

const SECTIONS = [
  { id: 'vitals', label: 'Vitals & imagery', icon: Satellite },
  { id: 'inputs', label: 'Water & nutrients', icon: Droplets },
  { id: 'risk', label: 'Risk & explainability', icon: Cpu },
  { id: 'twin', label: 'Twin, market & carbon', icon: CircleDollarSign },
];

export default function PlotIntel({
  plots, plotId, lang, onSelect,
}: { plots: any[]; plotId: string | null; lang: string; onSelect: (id: string) => void }) {
  const [d, setD] = useState<any>(null);
  const [busy, setBusy] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [section, setSection] = useState('vitals');
  const [xai, setXai] = useState('yield');
  const [cmd, setCmd] = useState<any>(null);

  useEffect(() => {
    if (!plotId) return;
    setBusy(true); setErr(null); setCmd(null);
    api.plot(plotId, lang).then(setD).catch((e) => setErr(e.message)).finally(() => setBusy(false));
  }, [plotId, lang]);

  const ndviSeries = useMemo(() => {
    if (!d) return [];
    return d.satellite.series.map((s: any) => ({
      date: s.date.slice(5),
      NDVI: s.ndvi, EVI: s.evi, SAVI: s.savi, NDWI: s.ndwi, cloud: s.cloud_pct,
    }));
  }, [d]);

  const sensorSeries = useMemo(() => {
    if (!d) return [];
    return d.sensors.map((s: any) => ({
      date: s.ts.slice(5),
      moisture: +(s.soil_moisture * 100).toFixed(1),
      rain: s.rainfall_mm,
      tmax: s.air_temp_max,
      humidity: s.humidity,
      et0: s.et0_mm,
    }));
  }, [d]);

  const waterSeries = useMemo(() => {
    if (!d) return [];
    return d.water.schedule.map((s: any) => ({
      date: s.date.slice(5),
      depletion: s.depletion_mm,
      etc: s.etc_mm,
      rain: s.effective_rain_mm,
      irrigation: s.gross_mm,
    }));
  }, [d]);

  const priceSeries = useMemo(() => {
    if (!d) return [];
    return [
      ...d.market.history.slice(-30).map((h: any) => ({ date: h.date.slice(5), actual: h.price })),
      ...d.market.forecast.map((f: any) => ({ date: f.date.slice(5), forecast: f.price, low: f.low, high: f.high })),
    ];
  }, [d]);

  const [twin, setTwin] = useState<any>(null);
  useEffect(() => {
    if (!plotId) return;
    setTwin(null);
    api.twin(plotId).then(setTwin).catch(() => setTwin(null));
  }, [plotId]);

  const [explain, setExplain] = useState<any>(null);
  useEffect(() => {
    if (!plotId) return;
    setExplain(null);
    const m = MODEL_KEYS.find((k) => k.key === xai)!;
    api.explain(plotId, m.api).then(setExplain).catch(() => setExplain(null));
  }, [plotId, xai]);

  const twinChart = useMemo(() => {
    if (!twin) return [];
    return twin.simulation.map((s: any) => ({
      date: s.date.slice(5),
      moisture: +(s.soil_moisture * 100).toFixed(1),
      ndvi: s.ndvi,
      stress: +(s.water_stress_index * 100).toFixed(1),
    }));
  }, [twin]);

  if (err) return <ErrorState error={err} />;

  return (
    <div className="space-y-5">
      {/* -------------------------------------------------------- selector */}
      <div className="flex gap-2 overflow-x-auto pb-1">
        {plots.map((p) => (
          <button key={p.plot_id} onClick={() => onSelect(p.plot_id)}
            data-testid={`chip-plot-${p.plot_id}`}
            className={cx(
              'flex shrink-0 items-center gap-2 rounded-xl border px-3 py-2 text-left transition-all duration-200',
              plotId === p.plot_id
                ? 'border-leaf/60 bg-leaf/12 shadow-glow'
                : 'border-line bg-surface hover:border-leaf/40',
            )}>
            <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: ndviColor(p.ndvi) }} />
            <span>
              <span className={cx('block text-[12px] font-semibold', plotId === p.plot_id ? 'text-leaf' : 'text-ink')}>
                {p.name}
              </span>
              <span className="num block text-[10px] text-faint">{p.crop} · {fmt(p.ndvi, 2)} · {p.risk_level}</span>
            </span>
          </button>
        ))}
      </div>

      {busy && <div className="panel p-6"><Loading rows={7} label="Fusing layers and running six models…" /></div>}

      {!busy && d && (
        <>
          {/* ------------------------------------------------------ header */}
          <div className="panel overflow-hidden">
            <div className="flex flex-wrap items-start gap-x-8 gap-y-4 border-b border-line px-5 py-4">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="text-[17px] font-black tracking-tight text-ink">{d.plot.name}</h2>
                  <Badge tone={levelTone(d.risk.level)}>{d.risk.level} risk · {Math.round(d.risk.composite * 100)}</Badge>
                  <Badge tone="neutral">{d.plot.growth_stage} stage</Badge>
                </div>
                <p className="mt-1 text-[11.5px] text-faint">
                  {d.plot.crop} ({d.plot.variety}) · {fmt(d.plot.area_ha, 1)} ha · {d.plot.soil_type} soil ·
                  {' '}{d.plot.irrigation_type} irrigation · sown {d.plot.sowing_date} · {d.plot.days_after_sowing} DAP
                </p>
                <p className="mt-0.5 text-[11.5px] text-faint">
                  {d.farm.owner_name} · {d.farm.village}, {d.farm.district}, {d.farm.state} ·
                  {' '}harvest window {d.plot.expected_harvest_date}
                </p>
              </div>

              <div className="ml-auto flex flex-wrap gap-6">
                <div>
                  <p className="label">Crop health</p>
                  <p className={cx('num mt-1 text-[26px] font-black leading-none', healthColor(d.health.score))}>
                    {fmt(d.health.score, 1)}
                  </p>
                  <p className="mt-1 text-[10.5px] text-faint">{d.health.band}</p>
                </div>
                <div>
                  <p className="label">Yield forecast</p>
                  <p className="num mt-1 text-[26px] font-black leading-none text-leaf">
                    {fmt(d.predictions.yield.value, 2)}
                  </p>
                  <p className="num mt-1 text-[10.5px] text-faint">
                    t/ha · {fmt(d.predictions.yield.plot_total_tonnes, 2)} t total
                  </p>
                </div>
                <div>
                  <p className="label">Vs 6-season mean</p>
                  <p className={cx('num mt-1 text-[26px] font-black leading-none',
                    d.predictions.yield.vs_history_pct >= 0 ? 'text-leaf' : 'text-amber')}>
                    {d.predictions.yield.vs_history_pct >= 0 ? '+' : ''}{fmt(d.predictions.yield.vs_history_pct, 1)}%
                  </p>
                  <p className="num mt-1 text-[10.5px] text-faint">history {fmt(d.predictions.yield.historical_avg_t_ha, 2)} t/ha</p>
                </div>
              </div>
            </div>

            <div className="flex gap-1 overflow-x-auto px-3 py-2">
              {SECTIONS.map((s) => (
                <button key={s.id} onClick={() => setSection(s.id)}
                  data-testid={`section-${s.id}`}
                  className={cx('flex shrink-0 items-center gap-1.5 rounded-lg px-3 py-1.5 text-[12px] font-semibold transition-colors',
                    section === s.id ? 'bg-leaf/12 text-leaf' : 'text-muted hover:bg-raised hover:text-ink')}>
                  <s.icon size={13} /> {s.label}
                </button>
              ))}
            </div>
          </div>

          {/* ----------------------------------------------- recommendations */}
          <Panel title="AI recommendations" bodyClass="grid grid-cols-1 gap-3 p-4 md:grid-cols-2 xl:grid-cols-3"
            subtitle="Every card carries a confidence score, the environmental drivers behind it, and satellite evidence">
            {d.recommendations.map((r: any) => (
              <article key={r.id} className="rounded-xl border border-line bg-raised/40 p-3.5">
                <div className="flex items-start justify-between gap-2">
                  <Badge tone={r.priority === 'High' ? 'rose' : r.priority === 'Medium' ? 'amber' : 'leaf'}>
                    {r.category}
                  </Badge>
                  <Confidence value={r.confidence} />
                </div>
                <h3 className="mt-2.5 text-[12.5px] font-bold leading-snug text-ink">{r.title_localised}</h3>
                <p className="mt-1.5 text-[11.5px] leading-relaxed text-muted">{r.action_localised}</p>
                <p className="mt-2 text-[10.5px] italic leading-snug text-leaf/80">{r.expected_impact}</p>
                <ul className="mt-2.5 space-y-1 border-t border-line pt-2.5">
                  {r.supporting_indicators.map((s: string, i: number) => (
                    <li key={i} className="flex gap-1.5 text-[10.5px] leading-snug text-faint">
                      <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-leaf/60" />{s}
                    </li>
                  ))}
                </ul>
                <p className="num mt-2 text-[9.5px] uppercase tracking-wide text-faint">model: {r.model}</p>
              </article>
            ))}
          </Panel>

          {/* ============================================ SECTION: vitals */}
          {section === 'vitals' && (
            <div className="space-y-5">
              <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
                <Panel className="xl:col-span-2" title="Vegetation index time series"
                  subtitle={`${d.satellite.series.length} cloud-filtered Sentinel-2 scenes · ${d.satellite.latest.platform} · ${d.satellite.latest.resolution_m} m`}>
                  <div className="h-[264px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={ndviSeries} margin={{ top: 4, right: 6, left: -8, bottom: 0 }}>
                        <defs>
                          <linearGradient id="gN" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0%" stopColor="hsl(88 62% 55%)" stopOpacity={0.42} />
                            <stop offset="100%" stopColor="hsl(88 62% 55%)" stopOpacity={0.02} />
                          </linearGradient>
                        </defs>
                        <CartesianGrid stroke="hsl(var(--line))" vertical={false} />
                        <XAxis dataKey="date" tickLine={false} axisLine={false} minTickGap={22} />
                        <YAxis domain={[0, 1]} tickLine={false} axisLine={false} />
                        <Tooltip contentStyle={{ background: 'hsl(var(--surface))', border: '1px solid hsl(var(--line))', borderRadius: 12, fontSize: 12 }} />
                        <Legend wrapperStyle={{ fontSize: 11 }} />
                        <ReferenceLine y={d.health.expected_ndvi_for_stage} stroke="hsl(36 92% 58%)"
                          strokeDasharray="4 4"
                          label={{ value: 'stage norm', fill: 'hsl(36 92% 58%)', fontSize: 10, position: 'insideTopRight' }} />
                        <Area type="monotone" dataKey="NDVI" stroke="hsl(88 62% 55%)" strokeWidth={2.2} fill="url(#gN)" />
                        <Line type="monotone" dataKey="EVI" stroke="hsl(196 74% 55%)" strokeWidth={1.6} dot={false} />
                        <Line type="monotone" dataKey="NDWI" stroke="hsl(268 60% 68%)" strokeWidth={1.4} dot={false} strokeDasharray="3 3" />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                </Panel>

                <Panel title="Latest scene" subtitle={`${d.satellite.latest.tile_id} · ${d.satellite.latest.capture_date} · ${fmt(d.satellite.latest.cloud_pct, 1)}% cloud`}
                  bodyClass="p-4">
                  <div className="grid grid-cols-2 gap-2">
                    {[
                      ['NDVI', d.satellite.latest.ndvi], ['EVI', d.satellite.latest.evi],
                      ['SAVI', d.satellite.latest.savi], ['NDWI', d.satellite.latest.ndwi],
                      ['NDRE', d.satellite.latest.ndre], ['LAI', d.satellite.latest.lai],
                    ].map(([l, v]: any) => (
                      <div key={l} className="rounded-xl border border-line bg-raised/40 px-2.5 py-2">
                        <p className="label">{l}</p>
                        <p className="num mt-1 text-[14px] font-bold text-ink">{fmt(v, 3)}</p>
                      </div>
                    ))}
                  </div>
                  <div className="mt-3 space-y-1.5 border-t border-line pt-3">
                    <p className="label">Raw surface reflectance</p>
                    {[['Blue B2', d.satellite.latest.band_blue], ['Red B4', d.satellite.latest.band_red],
                      ['NIR B8', d.satellite.latest.band_nir], ['SWIR B11', d.satellite.latest.band_swir]].map(([l, v]: any) => (
                      <div key={l} className="flex items-center gap-2.5">
                        <span className="w-[62px] shrink-0 text-[10.5px] text-faint">{l}</span>
                        <span className="flex-1"><Meter value={v * 100} tone="sky" height={4} /></span>
                        <span className="num w-11 shrink-0 text-right text-[10.5px] text-muted">{fmt(v, 4)}</span>
                      </div>
                    ))}
                  </div>
                </Panel>
              </div>

              <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
                <Panel title="Crop health decomposition"
                  subtitle={`Weighted score ${fmt(d.health.score, 1)}/100 — vigour ratio ${fmt(d.health.vigour_ratio, 3)}× the stage norm`}
                  bodyClass="space-y-3 p-4">
                  {d.health.components.map((c: any) => (
                    <div key={c.name}>
                      <div className="flex items-baseline justify-between gap-2">
                        <span className="text-[11.5px] text-muted">{c.name}</span>
                        <span className="num shrink-0 text-[11.5px] font-semibold text-ink">
                          {fmt(c.value, 0)} <span className="text-faint">× {c.weight}%</span>
                        </span>
                      </div>
                      <div className="mt-1.5">
                        <Meter value={c.value} tone={c.value >= 70 ? 'leaf' : c.value >= 45 ? 'amber' : 'rose'} height={5} />
                      </div>
                    </div>
                  ))}
                </Panel>

                <Panel title="Soil quality" subtitle={`${d.soil.texture} · score ${fmt(d.soil.score, 1)}/100`}
                  bodyClass="p-4">
                  <div className="grid grid-cols-3 gap-2">
                    {[['pH', d.soil.ph, d.soil.sub_scores.ph], ['EC dS/m', d.soil.ec, d.soil.sub_scores.salinity],
                      ['Avail. water', d.soil.available_water_fraction, d.soil.sub_scores.moisture]].map(([l, v, s]: any) => (
                      <div key={l} className="rounded-xl border border-line bg-raised/40 px-2.5 py-2">
                        <p className="label">{l}</p>
                        <p className="num mt-1 text-[14px] font-bold text-ink">{fmt(v, 2)}</p>
                        <div className="mt-1.5"><Meter value={s} tone={s >= 70 ? 'leaf' : s >= 45 ? 'amber' : 'rose'} height={3} /></div>
                      </div>
                    ))}
                  </div>
                  <div className="num mt-3 flex gap-4 border-t border-line pt-3 text-[10.5px] text-faint">
                    <span>Field capacity {pct(d.soil.field_capacity)}</span>
                    <span>Wilting point {pct(d.soil.wilting_point)}</span>
                  </div>
                  <ul className="mt-2 space-y-1.5">
                    {d.soil.notes.map((n: string, i: number) => (
                      <li key={i} className="flex gap-1.5 text-[11px] leading-snug text-muted">
                        <Beaker size={11} className="mt-0.5 shrink-0 text-leaf" />{n}
                      </li>
                    ))}
                  </ul>
                </Panel>

                <Panel title="Climate anomaly profile" subtitle="Standardised deviation from long-term normals"
                  bodyClass="p-4">
                  <div className="space-y-3">
                    {[
                      ['NDVI', d.features.ndvi_anomaly, Leaf],
                      ['Temperature', d.features.temp_anomaly, Gauge],
                      ['Rainfall', d.features.rain_anomaly, Droplets],
                      ['Humidity', d.features.humidity_anomaly, Wind],
                    ].map(([l, z, Icon]: any) => {
                      const mag = Math.min(Math.abs(z) / 3, 1);
                      const tone = Math.abs(z) >= 2 ? 'rose' : Math.abs(z) >= 1 ? 'amber' : 'leaf';
                      return (
                        <div key={l}>
                          <div className="flex items-center justify-between gap-2">
                            <span className="flex items-center gap-1.5 text-[11.5px] text-muted">
                              <Icon size={11} className="text-faint" />{l}
                            </span>
                            <span className={cx('num text-[11.5px] font-semibold',
                              tone === 'rose' ? 'text-rose' : tone === 'amber' ? 'text-amber' : 'text-leaf')}>
                              {z >= 0 ? '+' : ''}{fmt(z, 2)}σ
                            </span>
                          </div>
                          <div className="relative mt-1.5 h-1.5 rounded-full bg-raised">
                            <span className="absolute left-1/2 top-[-3px] h-3 w-px bg-line" />
                            <span className={cx('absolute top-0 h-1.5 rounded-full',
                              tone === 'rose' ? 'bg-rose' : tone === 'amber' ? 'bg-amber' : 'bg-leaf')}
                              style={{
                                width: `${mag * 50}%`,
                                left: z >= 0 ? '50%' : `${50 - mag * 50}%`,
                              }} />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                  <p className="mt-3 border-t border-line pt-3 text-[10.5px] leading-relaxed text-faint">
                    Isolation-forest anomaly score{' '}
                    <span className="num font-semibold text-ink">{fmt(d.predictions.climate_anomaly.value, 3)}</span>
                    {' '}— flags joint combinations of conditions that are rare in the historical record even
                    when each single variable looks normal.
                  </p>
                </Panel>
              </div>

              <Panel title="Ground sensor telemetry" subtitle="60 days of soil moisture, rainfall, temperature and reference evapotranspiration">
                <div className="h-[248px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={sensorSeries} margin={{ top: 4, right: 6, left: -8, bottom: 0 }}>
                      <CartesianGrid stroke="hsl(var(--line))" vertical={false} />
                      <XAxis dataKey="date" tickLine={false} axisLine={false} minTickGap={26} />
                      <YAxis yAxisId="l" tickLine={false} axisLine={false} />
                      <YAxis yAxisId="r" orientation="right" tickLine={false} axisLine={false} width={34} />
                      <Tooltip contentStyle={{ background: 'hsl(var(--surface))', border: '1px solid hsl(var(--line))', borderRadius: 12, fontSize: 12 }} />
                      <Legend wrapperStyle={{ fontSize: 11 }} />
                      <Bar yAxisId="r" dataKey="rain" name="Rain mm" fill="hsl(196 74% 55%)" opacity={0.55} radius={[3, 3, 0, 0]} />
                      <Line yAxisId="l" type="monotone" dataKey="moisture" name="Soil moisture %v/v" stroke="hsl(88 62% 55%)" strokeWidth={2} dot={false} />
                      <Line yAxisId="l" type="monotone" dataKey="tmax" name="Max temp °C" stroke="hsl(36 92% 58%)" strokeWidth={1.4} dot={false} />
                      <Line yAxisId="l" type="monotone" dataKey="humidity" name="Humidity %" stroke="hsl(268 60% 68%)" strokeWidth={1.2} dot={false} strokeDasharray="3 3" />
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
              </Panel>
            </div>
          )}

          {/* ============================================ SECTION: inputs */}
          {section === 'inputs' && (
            <div className="space-y-5">
              <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
                {[
                  ['Crop coefficient Kc', fmt(d.water.kc, 2), `${d.water.growth_stage} stage · FAO-56`],
                  ['Total available water', `${fmt(d.water.total_available_water_mm, 1)} mm`, `readily available ${fmt(d.water.readily_available_water_mm, 1)} mm`],
                  ['Current depletion', `${fmt(d.water.current_depletion_mm, 1)} mm`, d.water.next_irrigation ? `next event ${d.water.next_irrigation}` : 'no event in 7 days'],
                  ['7-day demand', litres(d.water.week_litres), `${fmt(d.water.week_gross_mm, 1)} mm gross · ${d.water.method} @ ${pct(d.water.application_efficiency)} eff.`],
                ].map(([l, v, s]: any) => (
                  <div key={l} className="panel px-4 py-3.5">
                    <p className="label">{l}</p>
                    <p className="num mt-1.5 text-[19px] font-bold leading-none text-ink">{v}</p>
                    <p className="mt-1.5 text-[10.5px] leading-snug text-faint">{s}</p>
                  </div>
                ))}
              </div>

              <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
                <Panel className="xl:col-span-2" title="Irrigation schedule — FAO-56 dual-Kc water balance"
                  subtitle="Daily root-zone depletion against the readily-available-water trigger">
                  <div className="h-[240px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <ComposedChart data={waterSeries} margin={{ top: 4, right: 6, left: -8, bottom: 0 }}>
                        <CartesianGrid stroke="hsl(var(--line))" vertical={false} />
                        <XAxis dataKey="date" tickLine={false} axisLine={false} />
                        <YAxis tickLine={false} axisLine={false} />
                        <Tooltip contentStyle={{ background: 'hsl(var(--surface))', border: '1px solid hsl(var(--line))', borderRadius: 12, fontSize: 12 }} />
                        <Legend wrapperStyle={{ fontSize: 11 }} />
                        <ReferenceLine y={d.water.readily_available_water_mm} stroke="hsl(352 76% 60%)" strokeDasharray="4 4"
                          label={{ value: 'RAW trigger', fill: 'hsl(352 76% 60%)', fontSize: 10, position: 'insideTopRight' }} />
                        <Bar dataKey="irrigation" name="Irrigation mm" fill="hsl(196 74% 55%)" radius={[3, 3, 0, 0]} maxBarSize={26} />
                        <Bar dataKey="rain" name="Effective rain mm" fill="hsl(268 60% 68%)" opacity={0.6} radius={[3, 3, 0, 0]} maxBarSize={26} />
                        <Line type="monotone" dataKey="depletion" name="Depletion mm" stroke="hsl(36 92% 58%)" strokeWidth={2.2} dot={{ r: 2 }} />
                        <Line type="monotone" dataKey="etc" name="ETc mm" stroke="hsl(88 62% 55%)" strokeWidth={1.5} dot={false} />
                      </ComposedChart>
                    </ResponsiveContainer>
                  </div>

                  <div className="mt-4 overflow-x-auto">
                    <table className="w-full min-w-[560px] text-left">
                      <thead><tr className="border-b border-line">
                        {['Date', 'ETc', 'Eff. rain', 'Depletion', 'Apply', 'Volume', 'Runtime'].map((h) => (
                          <th key={h} className="label py-2 pr-3 font-semibold">{h}</th>
                        ))}
                      </tr></thead>
                      <tbody>
                        {d.water.schedule.map((s: any) => (
                          <tr key={s.date} className={cx('border-b border-line/50 last:border-0',
                            s.irrigate && 'bg-sky/[0.06]')}>
                            <td className="num py-2 pr-3 text-[11.5px] text-muted">{s.date}</td>
                            <td className="num py-2 pr-3 text-[11.5px] text-muted">{fmt(s.etc_mm, 2)}</td>
                            <td className="num py-2 pr-3 text-[11.5px] text-muted">{fmt(s.effective_rain_mm, 1)}</td>
                            <td className="num py-2 pr-3 text-[11.5px] text-ink">{fmt(s.depletion_mm, 1)}</td>
                            <td className="py-2 pr-3">
                              {s.irrigate
                                ? <Badge tone="sky">{fmt(s.gross_mm, 1)} mm</Badge>
                                : <span className="text-[11px] text-faint">—</span>}
                            </td>
                            <td className="num py-2 pr-3 text-[11.5px] text-muted">{s.litres ? litres(s.litres) : '—'}</td>
                            <td className="num py-2 pr-3 text-[11.5px] text-muted">{s.minutes ? `${s.minutes} min` : '—'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </Panel>

                <div className="space-y-5">
                  <Panel title="Water savings" subtitle="Scheduled application against unmanaged flood irrigation"
                    bodyClass="p-4">
                    <p className="num text-[28px] font-black leading-none text-sky">{pct(d.water.water_saved_pct / 100)}</p>
                    <p className="mt-1.5 text-[11.5px] text-muted">
                      {litres(d.water.water_saved_vs_flood_litres)} saved over the next 7 days
                    </p>
                    <div className="mt-3"><Meter value={d.water.water_saved_pct} tone="sky" height={7} /></div>
                    <p className="mt-3 text-[10.5px] leading-relaxed text-faint">
                      {d.plot.irrigation_type} application efficiency {pct(d.water.application_efficiency)} vs
                      55% for uncontrolled flood. Effective rainfall follows the USDA-SCS method.
                    </p>
                  </Panel>

                  <Panel title="Autonomous irrigation control" subtitle="Edge gateway valve command with safety interlocks"
                    bodyClass="p-4">
                    <button className="btn btn-primary w-full" data-testid="button-irrigate"
                      onClick={() => api.irrigate(d.plot.id, 'V1', 'auto').then(setCmd).catch(() => setCmd({ ok: false }))}>
                      <Zap size={13} /> Issue valve command
                    </button>
                    {cmd?.command && (
                      <div className="mt-3 space-y-1.5 rounded-xl border border-leaf/40 bg-leaf/[0.07] p-3">
                        <p className="text-[11.5px] font-semibold text-leaf">Queued to {cmd.command.device}</p>
                        <p className="num text-[10.5px] leading-relaxed text-muted">
                          valve {cmd.command.valve} · {cmd.command.mode} · {cmd.command.open_minutes} min ·
                          target {fmt(cmd.command.target_mm, 1)} mm<br />
                          abort if rain &gt; {fmt(cmd.command.safety_interlocks.abort_if_rain_over_mm, 1)} mm
                          (forecast {fmt(cmd.command.safety_interlocks.rain_forecast_mm_24h, 1)} mm)
                        </p>
                      </div>
                    )}
                    {cmd && !cmd.command && (
                      <p className="mt-3 text-[11px] text-amber">Gateway unreachable — command queued offline.</p>
                    )}
                    <p className="mt-3 text-[10.5px] leading-relaxed text-faint">
                      Commands are idempotent and expire after the scheduled window. A rain-abort interlock and a
                      max-runtime cap prevent over-application if connectivity drops.
                    </p>
                  </Panel>
                </div>
              </div>

              <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
                <Panel className="xl:col-span-2" title="Fertiliser prescription"
                  subtitle="Yield-goal adjusted NPK with a stage-wise split plan and product conversion">
                  <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                    <div>
                      <p className="label">Season target (kg/ha)</p>
                      <div className="mt-2 space-y-2">
                        {Object.entries(d.fertilizer.season_target_kg_ha).map(([k, v]: any) => (
                          <div key={k} className="flex items-center gap-2.5">
                            <span className="w-14 shrink-0 text-[11.5px] text-muted">{k}</span>
                            <span className="flex-1"><Meter value={v} max={200} tone="violet" height={6} /></span>
                            <span className="num w-16 shrink-0 text-right text-[11.5px] font-semibold text-ink">{fmt(v, 1)}</span>
                          </div>
                        ))}
                      </div>
                      <p className="label mt-4">Plot total (kg)</p>
                      <div className="num mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-[11.5px] text-muted">
                        {Object.entries(d.fertilizer.plot_total_kg).map(([k, v]: any) => (
                          <span key={k}>{k} <span className="font-semibold text-ink">{fmt(v, 1)}</span></span>
                        ))}
                      </div>
                      <p className="label mt-4">Product quantities (kg/ha)</p>
                      <div className="mt-1.5 space-y-1">
                        {Object.entries(d.fertilizer.products_kg_ha).map(([k, v]: any) => (
                          <div key={k} className="flex justify-between text-[11.5px]">
                            <span className="text-muted">{k}</span>
                            <span className="num font-semibold text-ink">{fmt(v, 1)}</span>
                          </div>
                        ))}
                      </div>
                    </div>

                    <div>
                      <div className="rounded-xl border border-leaf/40 bg-leaf/[0.07] p-3">
                        <p className="label text-leaf">Next dose</p>
                        <p className="mt-1.5 text-[13px] font-bold text-ink">
                          {fmt(d.fertilizer.next_dose.N_kg_ha, 1)} kg N/ha
                          <span className="text-faint"> ({fmt(d.fertilizer.next_dose.urea_kg_plot, 1)} kg urea for this plot)</span>
                        </p>
                        <p className="num mt-1 text-[10.5px] text-muted">
                          {d.fertilizer.next_dose.stage} stage · {fmt(d.fertilizer.next_dose.share_pct, 0)}% of season N ·
                          window {d.fertilizer.next_dose.window}
                        </p>
                      </div>

                      <p className="label mt-4">Split plan</p>
                      <div className="mt-1.5 space-y-1.5">
                        {d.fertilizer.split_plan.map((s: any) => (
                          <div key={s.stage} className="flex items-center gap-2.5 rounded-lg border border-line bg-raised/40 px-2.5 py-1.5">
                            <span className="w-16 shrink-0 text-[11px] text-muted">{s.stage}</span>
                            <span className="num shrink-0 text-[11px] font-semibold text-ink">{s.share_pct}%</span>
                            <span className="num ml-auto text-[10.5px] text-faint">
                              N {fmt(s.N_kg_ha, 1)} · K₂O {fmt(s.K2O_kg_ha, 1)}
                            </span>
                          </div>
                        ))}
                      </div>

                      <p className="label mt-4">Why this number</p>
                      <ul className="mt-1.5 space-y-1.5">
                        {d.fertilizer.adjustments.map((a: any) => (
                          <li key={a.factor} className="rounded-lg border border-line bg-raised/30 px-2.5 py-1.5">
                            <div className="flex items-baseline justify-between gap-2">
                              <span className="text-[11px] font-semibold text-ink">{a.factor}</span>
                              <span className={cx('num shrink-0 text-[11px] font-semibold',
                                a.multiplier > 1 ? 'text-amber' : 'text-leaf')}>×{fmt(a.multiplier, 3)}</span>
                            </div>
                            <p className="mt-0.5 text-[10.5px] leading-snug text-faint">{a.why}</p>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>

                  <p className="mt-4 rounded-xl border border-line bg-raised/40 p-3 text-[11px] leading-relaxed text-muted">
                    <span className="font-semibold text-leaf">Organic substitution: </span>
                    {fmt(d.fertilizer.organic_substitution.farmyard_manure_t_ha, 2)} t/ha farmyard manure —
                    {' '}{d.fertilizer.organic_substitution.note}
                  </p>
                </Panel>

                <Panel title="Pest & disease pressure" subtitle="Crop-specific envelopes matched against live conditions"
                  bodyClass="space-y-3 p-4">
                  {d.pests.length === 0 && <p className="py-6 text-center text-[12px] text-faint">No pest above threshold.</p>}
                  {d.pests.map((p: any) => (
                    <article key={p.name} className="rounded-xl border border-line bg-raised/40 p-3">
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <p className="text-[12.5px] font-bold text-ink">{p.name}</p>
                          <p className="text-[10.5px] text-faint">{p.type} · window {p.window}</p>
                        </div>
                        <Badge tone={levelTone(p.level)}>{p.level} · {Math.round(p.risk * 100)}%</Badge>
                      </div>
                      <div className="mt-2.5 grid grid-cols-3 gap-2">
                        {Object.entries(p.fit).map(([k, v]: any) => (
                          <div key={k}>
                            <p className="label">{k}</p>
                            <div className="mt-1"><Meter value={v * 100} tone={v > 0.66 ? 'rose' : v > 0.33 ? 'amber' : 'leaf'} height={4} /></div>
                          </div>
                        ))}
                      </div>
                      <p className="num mt-2 text-[10px] text-faint">
                        favours {p.envelope.temp_c[0]}–{p.envelope.temp_c[1]} °C ·
                        {' '}{p.envelope.humidity_pct[0]}–{p.envelope.humidity_pct[1]}% RH ·
                        {' '}{p.envelope.favoured_stage} stage
                      </p>
                      <p className="mt-2 border-t border-line pt-2 text-[11px] leading-relaxed text-muted">
                        <Bug size={11} className="mr-1 inline text-rose" />{p.control}
                      </p>
                    </article>
                  ))}
                </Panel>
              </div>
            </div>
          )}

          {/* ============================================== SECTION: risk */}
          {section === 'risk' && (
            <div className="space-y-5">
              <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
                {MODEL_KEYS.map((m) => {
                  const p = d.predictions[m.key];
                  const isReg = p.kind === 'regression';
                  const v = isReg ? fmt(p.value, 2) : pct(p.value, 0);
                  const tone = isReg ? 'leaf' : p.value >= 0.6 ? 'rose' : p.value >= 0.32 ? 'amber' : 'leaf';
                  return (
                    <button key={m.key} onClick={() => setXai(m.key)} data-testid={`model-${m.key}`}
                      className={cx('panel px-4 py-3.5 text-left transition-all duration-200',
                        xai === m.key ? 'border-leaf/60 shadow-glow' : 'hover:border-leaf/40')}>
                      <div className="flex items-center justify-between gap-2">
                        <span className="label truncate">{m.label}</span>
                        <m.icon size={13} className="shrink-0 text-faint" />
                      </div>
                      <p className={cx('num mt-2 text-[21px] font-bold leading-none',
                        tone === 'rose' ? 'text-rose' : tone === 'amber' ? 'text-amber' : 'text-leaf')}>{v}</p>
                      <p className="mt-1.5 text-[10px] text-faint">{p.unit}</p>
                      <div className="mt-2"><Confidence value={p.confidence} /></div>
                    </button>
                  );
                })}
              </div>

              <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
                <Panel className="xl:col-span-2"
                  title={`Why the model said this — ${MODEL_KEYS.find((k) => k.key === xai)!.label}`}
                  subtitle={explain?.explanation?.method ?? 'Local attribution by ablation to the training median'}
                  right={explain && <Confidence value={explain.confidence} />}>
                  {!explain && <Loading rows={5} />}
                  {explain && (
                    <>
                      <div className="mb-4 flex flex-wrap items-end gap-6 rounded-xl border border-line bg-raised/40 p-3.5">
                        <div>
                          <p className="label">Prediction</p>
                          <p className="num mt-1 text-[22px] font-black leading-none text-ink">
                            {explain.unit === 't/ha' ? fmt(explain.value, 3) : pct(explain.value, 1)}
                          </p>
                          <p className="text-[10px] text-faint">{explain.unit}</p>
                        </div>
                        {Object.entries(explain.metrics).map(([k, v]: any) => (
                          <div key={k}>
                            <p className="label">{k.replace(/_/g, ' ')}</p>
                            <p className="num mt-1 text-[14px] font-bold text-ink">
                              {typeof v === 'number' ? (v > 100 ? fmtInt(v) : fmt(v, 4)) : String(v)}
                            </p>
                          </div>
                        ))}
                      </div>

                      <p className="label mb-2">Local drivers for this plot</p>
                      <div className="space-y-2.5">
                        {explain.explanation.drivers.map((dr: any) => (
                          <div key={dr.feature}>
                            <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
                              <span className="text-[11.5px] font-medium text-ink">{dr.label}</span>
                              <span className="num text-[10.5px] text-faint">
                                value <span className="text-muted">{fmt(dr.value, 2)}</span> ·
                                {' '}median <span className="text-muted">{fmt(dr.median, 2)}</span> ·
                                {' '}<span className={dr.direction === 'increases' ? 'text-rose' : 'text-leaf'}>
                                  {dr.direction}
                                </span> · {fmt(dr.share_pct, 1)}%
                              </span>
                            </div>
                            <div className="mt-1.5">
                              <Meter value={dr.share_pct} tone={dr.direction === 'increases' ? 'rose' : 'leaf'} height={6} />
                            </div>
                          </div>
                        ))}
                      </div>

                      <p className="label mb-2 mt-5">Global permutation importance</p>
                      <p className="mb-2.5 text-[10.5px] leading-relaxed text-faint">
                        Share of total model skill lost when each feature is shuffled on held-out data.
                        Bars are scaled against the strongest feature.
                      </p>
                      <div className="space-y-2">
                        {(() => {
                          const gi = explain.explanation.global_importance;
                          const max = Math.max(...gi.map((g: any) => Math.abs(g.importance)), 1e-9);
                          const total = gi.reduce((a: number, g: any) => a + Math.abs(g.importance), 0) || 1;
                          return gi.map((g: any, i: number) => (
                            <div key={g.label} className="flex items-center gap-3">
                              <span className="w-[120px] shrink-0 text-[11px] leading-snug text-muted">{g.label}</span>
                              <span className="flex-1">
                                <span className="block h-[6px] w-full overflow-hidden rounded-full bg-raised">
                                  <span className="block h-full rounded-full transition-all duration-500"
                                    style={{
                                      width: `${Math.max(2, (Math.abs(g.importance) / max) * 100)}%`,
                                      background: `hsl(88 62% ${58 - i * 5}%)`,
                                    }} />
                                </span>
                              </span>
                              <span className="num w-[104px] shrink-0 text-right text-[10.5px] text-faint">
                                {fmt(g.importance, 4)} · {pct(Math.abs(g.importance) / total, 0)}
                              </span>
                            </div>
                          ));
                        })()}
                      </div>
                    </>
                  )}
                </Panel>

                <div className="space-y-5">
                  <Panel title="Composite risk stack" subtitle={`Weighted index ${Math.round(d.risk.composite * 100)}/100 — ${d.risk.level}`}
                    bodyClass="space-y-3 p-4">
                    {d.risk.items.map((r: any) => (
                      <div key={r.key}>
                        <div className="flex items-baseline justify-between gap-2">
                          <span className="text-[11.5px] text-muted">{r.label}</span>
                          <span className="flex items-center gap-2">
                            <Badge tone={levelTone(r.level)}>{r.level}</Badge>
                            <span className="num text-[11.5px] font-semibold text-ink">{pct(r.score, 1)}</span>
                          </span>
                        </div>
                        <div className="mt-1.5">
                          <Meter value={r.score * 100} tone={levelTone(r.level) as string} height={5} />
                        </div>
                        <p className="num mt-1 text-[9.5px] text-faint">model confidence {pct(r.confidence)}</p>
                      </div>
                    ))}
                  </Panel>

                  <Panel title="Historical benchmark" subtitle="Six recorded seasons on this plot" bodyClass="p-4">
                    <div className="h-[150px]">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={[...d.history].map((h: any) => ({
                          yr: `${h.year}`, yield: h.yield_t_ha, pest: h.pest_incidence,
                        })).concat([{ yr: '2026 AI', yield: d.predictions.yield.value, pest: 0 }] as any)}
                          margin={{ top: 4, right: 6, left: -10, bottom: 0 }}>
                          <CartesianGrid stroke="hsl(var(--line))" vertical={false} />
                          <XAxis dataKey="yr" tickLine={false} axisLine={false} tick={{ fontSize: 9.5 }} />
                          <YAxis tickLine={false} axisLine={false} />
                          <Tooltip contentStyle={{ background: 'hsl(var(--surface))', border: '1px solid hsl(var(--line))', borderRadius: 12, fontSize: 12 }} />
                          <Bar dataKey="yield" name="t/ha" radius={[5, 5, 0, 0]} maxBarSize={26}>
                            {[...d.history, { year: 'ai' }].map((_h: any, i: number) => (
                              <Cell key={i} fill={i === d.history.length ? 'hsl(88 62% 55%)' : 'hsl(96 34% 32%)'} />
                            ))}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                    <div className="mt-2 space-y-1">
                      {d.history.slice(-3).map((h: any) => (
                        <div key={h.year} className="num flex items-center justify-between text-[10.5px] text-faint">
                          <span>{h.year} {h.season} · {h.variety}</span>
                          <span>{fmt(h.yield_t_ha, 2)} t/ha · N {fmt(h.fertilizer_n_kg_ha, 0)} · {fmt(h.season_rainfall_mm, 0)} mm</span>
                        </div>
                      ))}
                    </div>
                    <p className="mt-2 flex items-start gap-1.5 border-t border-line pt-2 text-[10.5px] leading-relaxed text-faint">
                      <History size={11} className="mt-0.5 shrink-0 text-leaf" />
                      <span className="min-w-0">
                        Yield confidence band {fmt(d.predictions.yield.range[0], 2)}–{fmt(d.predictions.yield.range[1], 2)} t/ha
                        from the model MAE of {fmt(d.predictions.yield.metrics.mae, 3)} t/ha.
                      </span>
                    </p>
                  </Panel>
                </div>
              </div>

              <Panel title="Weather forecast — decision window"
                subtitle={d.forecast[0]?.source ?? 'IMD + ECMWF blend'} bodyClass="p-0">
                <div className="grid grid-cols-2 divide-x divide-line sm:grid-cols-5 lg:grid-cols-10">
                  {d.forecast.map((f: any) => (
                    <div key={f.forecast_date} className="p-3">
                      <p className="label">{f.forecast_date.slice(5)}</p>
                      <p className="num mt-1.5 text-[15px] font-bold text-ink">{fmt(f.temp_max, 0)}°<span className="text-[11px] text-faint">/{fmt(f.temp_min, 0)}°</span></p>
                      <p className="num mt-1 text-[10.5px] text-sky">{fmt(f.rainfall_mm, 1)} mm · {fmt(f.rain_probability, 0)}%</p>
                      <p className="num mt-0.5 text-[10px] text-faint">RH {fmt(f.humidity, 0)}%</p>
                      <p className="num text-[10px] text-faint">{fmt(f.wind_kph, 0)} kph {f.wind_dir}</p>
                      <p className="num text-[10px] text-faint">ET₀ {fmt(f.et0_mm, 1)}</p>
                    </div>
                  ))}
                </div>
              </Panel>
            </div>
          )}

          {/* ============================================== SECTION: twin */}
          {section === 'twin' && (
            <div className="space-y-5">
              <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
                <Panel title="Digital farm twin"
                  subtitle={twin?.engine ?? 'Water-balance coupled NDVI growth simulation, daily step'}>
                  {!twin && <Loading rows={4} />}
                  {twin && (
                    <>
                      <div className="mb-4 grid grid-cols-3 gap-2 sm:grid-cols-6">
                        {[
                          ['NDVI', fmt(twin.state.ndvi, 3)],
                          ['Moisture', pct(twin.state.soil_moisture, 1)],
                          ['LAI', fmt(twin.state.lai, 2)],
                          ['Biomass', fmt(twin.state.biomass_proxy, 2)],
                          ['Root mm', twin.state.root_depth_mm],
                          ['DAP', twin.state.dap],
                        ].map(([l, v]: any) => (
                          <div key={l} className="rounded-xl border border-line bg-raised/40 px-2.5 py-2">
                            <p className="label">{l}</p>
                            <p className="num mt-1 text-[13px] font-bold text-ink">{v}</p>
                          </div>
                        ))}
                      </div>
                      <div className="h-[222px]">
                        <ResponsiveContainer width="100%" height="100%">
                          <ComposedChart data={twinChart} margin={{ top: 4, right: 6, left: -8, bottom: 0 }}>
                            <CartesianGrid stroke="hsl(var(--line))" vertical={false} />
                            <XAxis dataKey="date" tickLine={false} axisLine={false} />
                            {/* Soil moisture and stress share a narrow % band; NDVI keeps its own 0-1 axis
                                so both curves show real variation instead of flattening out. */}
                            <YAxis yAxisId="l" domain={[0, 60]} tickLine={false} axisLine={false} width={34} />
                            <YAxis yAxisId="r" orientation="right" domain={[0, 1]} tickLine={false} axisLine={false} width={34} />
                            <Tooltip contentStyle={{ background: 'hsl(var(--surface))', border: '1px solid hsl(var(--line))', borderRadius: 12, fontSize: 12 }} />
                            <Legend wrapperStyle={{ fontSize: 11 }} />
                            <Bar yAxisId="l" dataKey="stress" name="Water stress %" fill="hsl(352 76% 60%)" opacity={0.4} radius={[3, 3, 0, 0]} />
                            <Line yAxisId="l" type="monotone" dataKey="moisture" name="Soil moisture %" stroke="hsl(196 74% 55%)" strokeWidth={2} dot={false} />
                            <Line yAxisId="r" type="monotone" dataKey="ndvi" name="Simulated NDVI" stroke="hsl(88 62% 55%)" strokeWidth={2.2} dot={false} />
                          </ComposedChart>
                        </ResponsiveContainer>
                      </div>
                      <p className="mt-3 text-[10.5px] leading-relaxed text-faint">
                        The twin advances soil moisture with the same FAO-56 balance used for scheduling, then
                        couples canopy growth to the resulting water-stress coefficient — so the simulated NDVI
                        curve reacts to whichever irrigation plan you commit to.
                      </p>
                    </>
                  )}
                </Panel>

                <Panel title="Commodity price outlook"
                  subtitle={`${d.market.mandi} · ${d.market.model}`}>
                  <div className="mb-3 flex flex-wrap items-end gap-6">
                    <div>
                      <p className="label">Latest modal price</p>
                      <p className="num mt-1 text-[22px] font-black leading-none text-ink">₹{fmtInt(d.market.latest_price)}</p>
                      <p className="text-[10px] text-faint">per quintal</p>
                    </div>
                    <div>
                      <p className="label">Trend</p>
                      <p className={cx('num mt-1 text-[16px] font-bold leading-none',
                        d.market.trend_per_day >= 0 ? 'text-leaf' : 'text-rose')}>
                        {d.market.trend_per_day >= 0 ? '+' : ''}₹{fmt(d.market.trend_per_day, 2)}/day
                      </p>
                    </div>
                    <Badge tone={d.market.signal.startsWith('Hold') ? 'amber' : 'leaf'} className="mb-1">
                      {d.market.signal}
                    </Badge>
                  </div>
                  <div className="h-[222px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <ComposedChart data={priceSeries} margin={{ top: 4, right: 6, left: -2, bottom: 0 }}>
                        <CartesianGrid stroke="hsl(var(--line))" vertical={false} />
                        <XAxis dataKey="date" tickLine={false} axisLine={false} minTickGap={24} />
                        <YAxis domain={['auto', 'auto']} tickLine={false} axisLine={false} width={46} />
                        <Tooltip contentStyle={{ background: 'hsl(var(--surface))', border: '1px solid hsl(var(--line))', borderRadius: 12, fontSize: 12 }} />
                        <Legend wrapperStyle={{ fontSize: 11 }} />
                        <Area type="monotone" dataKey="high" name="Upper band" stroke="none" fill="hsl(268 60% 68%)" fillOpacity={0.14} />
                        <Area type="monotone" dataKey="low" name="Lower band" stroke="none" fill="hsl(var(--surface))" fillOpacity={1} />
                        <Line type="monotone" dataKey="actual" name="Observed ₹" stroke="hsl(88 62% 55%)" strokeWidth={2} dot={false} />
                        <Line type="monotone" dataKey="forecast" name="Forecast ₹" stroke="hsl(268 60% 68%)" strokeWidth={2} strokeDasharray="5 4" dot={false} />
                      </ComposedChart>
                    </ResponsiveContainer>
                  </div>
                  <p className="num mt-2 text-[10.5px] text-faint">
                    Expected revenue at forecast yield:
                    {' '}<span className="font-semibold text-ink">
                      ₹{fmtInt(d.predictions.yield.plot_total_tonnes * 10 * d.market.forecast[d.market.forecast.length - 1].price)}
                    </span>{' '}
                    ({fmt(d.predictions.yield.plot_total_tonnes, 2)} t × 10 quintal × forecast price)
                  </p>
                </Panel>
              </div>

              <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
                <Panel className="xl:col-span-2" title="Carbon footprint"
                  subtitle={d.carbon.factors_source}>
                  <div className="mb-3 flex flex-wrap items-end gap-8">
                    <div>
                      <p className="label">Season total</p>
                      <p className="num mt-1 text-[24px] font-black leading-none text-ink">
                        {fmt(d.carbon.total_kg_co2e / 1000, 2)} <span className="text-[12px] text-faint">t CO₂e</span>
                      </p>
                    </div>
                    <div>
                      <p className="label">Intensity</p>
                      <p className="num mt-1 text-[18px] font-bold leading-none text-amber">
                        {fmtInt(d.carbon.per_hectare)} <span className="text-[11px] text-faint">kg/ha</span>
                      </p>
                    </div>
                    <div>
                      <p className="label">Per tonne produced</p>
                      <p className="num mt-1 text-[18px] font-bold leading-none text-muted">
                        {fmtInt(d.carbon.total_kg_co2e / Math.max(d.predictions.yield.plot_total_tonnes, 0.01))}
                        <span className="text-[11px] text-faint"> kg/t</span>
                      </p>
                    </div>
                  </div>
                  <div className="space-y-2.5">
                    {(() => {
                      const rows = d.carbon.breakdown;
                      const max = Math.max(...rows.map((r: any) => r.kg_co2e), 1e-9);
                      const total = rows.reduce((a: number, r: any) => a + r.kg_co2e, 0) || 1;
                      return rows.map((r: any, i: number) => (
                        <div key={r.source} className="flex items-center gap-3">
                          <span className="w-[148px] shrink-0 text-[11px] leading-snug text-muted">{r.source}</span>
                          <span className="flex-1">
                            <span className="block h-[7px] w-full overflow-hidden rounded-full bg-raised">
                              <span className="block h-full rounded-full transition-all duration-500"
                                style={{
                                  width: `${Math.max(r.kg_co2e > 0 ? 2 : 0, (r.kg_co2e / max) * 100)}%`,
                                  background: `hsl(36 92% ${58 - i * 7}%)`,
                                }} />
                            </span>
                          </span>
                          <span className="num w-[124px] shrink-0 text-right text-[10.5px] text-faint">
                            {fmtInt(r.kg_co2e)} kg · {pct(r.kg_co2e / total, 0)}
                          </span>
                        </div>
                      ));
                    })()}
                  </div>
                  <ul className="mt-3 space-y-1.5 border-t border-line pt-3">
                    {d.carbon.mitigation.map((m: string, i: number) => (
                      <li key={i} className="flex gap-1.5 text-[11px] leading-snug text-muted">
                        <Leaf size={11} className="mt-0.5 shrink-0 text-leaf" />{m}
                      </li>
                    ))}
                  </ul>
                </Panel>

                <Panel title="Crop rotation plan"
                  subtitle="Nitrogen-fixing and disease-cycle-breaking successors"
                  bodyClass="p-4">
                  {d.recommendations.filter((r: any) => r.category === 'Crop rotation').map((r: any) => (
                    <div key={r.id}>
                      <p className="text-[12.5px] font-bold text-ink">{r.title_localised}</p>
                      <p className="mt-1.5 text-[11.5px] leading-relaxed text-muted">{r.action_localised}</p>
                      <div className="mt-2.5"><Confidence value={r.confidence} /></div>
                      <ul className="mt-3 space-y-1.5 border-t border-line pt-3">
                        {r.supporting_indicators.map((s: string, i: number) => (
                          <li key={i} className="flex gap-1.5 text-[10.5px] leading-snug text-faint">
                            <CalendarClock size={11} className="mt-0.5 shrink-0 text-leaf" />{s}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                  <div className="mt-4 rounded-xl border border-line bg-raised/40 p-3">
                    <p className="label flex items-center gap-1.5"><Radio size={11} /> Edge readiness</p>
                    <p className="mt-1.5 text-[10.5px] leading-relaxed text-faint">
                      All six models are tree-based and export to a single joblib bundle under 6 MB, so the same
                      inference runs on a field gateway with no GPU. Advisories generated on-device are queued and
                      replayed to Supabase when the link returns.
                    </p>
                  </div>
                </Panel>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
