import { useMemo } from 'react';
import {
  Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from 'recharts';
import {
  AlertTriangle, ArrowUpRight, ChevronRight, CloudRain, Droplets, Factory,
  Leaf, Sprout, TrendingUp, Wheat,
} from 'lucide-react';
import { Badge, cx, fmt, fmtInt, healthColor, levelTone, Meter, Panel, Stat, ndviColor, riskColor } from '../lib/ui';

const CAT_TONE: Record<string, string> = {
  Irrigation: 'sky', Fertilizer: 'violet', 'Pest management': 'rose',
  'Climate adaptation': 'amber', 'Harvest planning': 'leaf', 'Crop rotation': 'leaf',
};

export default function Overview({
  data, lang, onOpenPlot,
}: { data: any; lang: string; onOpenPlot: (id: string) => void }) {
  const k = data.kpi;

  const districtData = useMemo(
    () => data.by_district.map((d: any) => ({ ...d, riskPct: Math.round(d.risk * 100) })),
    [data],
  );
  const cropData = useMemo(
    () => data.by_crop.map((c: any) => ({ ...c, health: Math.round(c.health) })),
    [data],
  );

  return (
    <div className="space-y-5">
      {/* ------------------------------------------------------------- KPIs */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <Stat label="Monitored area" value={fmt(k.area_ha, 1)} unit="ha"
          sub={`${k.plots} plots · ${k.farms} farms`} icon={<Sprout size={14} />} />
        <Stat label="Mean crop health" value={fmt(k.avg_health, 1)} unit="/100"
          tone={k.avg_health >= 70 ? 'leaf' : 'amber'}
          sub={`Fleet NDVI ${fmt(k.avg_ndvi, 3)}`} icon={<Leaf size={14} />} />
        <Stat label="Forecast production" value={fmt(k.total_yield_t, 1)} unit="t"
          tone="leaf" sub={`${fmt(k.yield_t_ha_weighted, 2)} t/ha weighted`} icon={<Wheat size={14} />} />
        <Stat label="Plots at high risk" value={k.high_risk_plots} unit={`of ${k.plots}`}
          tone={k.high_risk_plots > 2 ? 'rose' : 'amber'}
          sub={`${k.open_alerts} open advisories`} icon={<AlertTriangle size={14} />} />
        <Stat label="Irrigation demand" value={fmt(k.water_week_l / 1e6, 2)} unit="M L / 7d"
          tone="sky" sub={`${fmt(k.water_saved_l / 1e6, 2)}M L saved vs flood`} icon={<Droplets size={14} />} />
        <Stat label="Season footprint" value={fmt(k.carbon_kg / 1000, 1)} unit="t CO₂e"
          sub={`${fmt(k.carbon_kg / Math.max(k.area_ha, 1), 0)} kg/ha`} icon={<Factory size={14} />} />
      </div>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-3">
        {/* --------------------------------------------------- plot table */}
        <Panel
          className="xl:col-span-2"
          title="Plot register"
          subtitle="Ranked by composite risk — fused satellite, sensor, weather and history signals"
          bodyClass="p-0"
          right={<Badge tone="leaf"><TrendingUp size={11} /> live inference</Badge>}
        >
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-left">
              <thead>
                <tr className="border-b border-line text-faint">
                  <th className="label px-5 py-2.5 font-semibold">Plot</th>
                  <th className="label px-3 py-2.5 font-semibold">Crop / stage</th>
                  <th className="label px-3 py-2.5 text-right font-semibold">NDVI</th>
                  <th className="label px-3 py-2.5 font-semibold">Health</th>
                  <th className="label px-3 py-2.5 text-right font-semibold">Yield t/ha</th>
                  <th className="label px-3 py-2.5 font-semibold">Risk</th>
                  <th className="label px-3 py-2.5 font-semibold">Next action</th>
                  <th className="px-3 py-2.5" />
                </tr>
              </thead>
              <tbody>
                {[...data.plots].sort((a: any, b: any) => b.risk - a.risk).map((p: any) => (
                  <tr key={p.plot_id} onClick={() => onOpenPlot(p.plot_id)}
                    data-testid={`row-plot-${p.plot_id}`}
                    className="row-hover cursor-pointer border-b border-line/60 last:border-0">
                    <td className="px-5 py-3">
                      <div className="text-[12.5px] font-semibold text-ink">{p.name}</div>
                      <div className="text-[10.5px] text-faint">{p.district}, {p.state} · {fmt(p.area_ha, 1)} ha</div>
                    </td>
                    <td className="px-3 py-3">
                      <div className="text-[12px] text-muted">{p.crop}</div>
                      <div className="text-[10.5px] text-faint">{p.stage} · {p.dap} DAP</div>
                    </td>
                    <td className="px-3 py-3 text-right">
                      <span className="num inline-flex items-center gap-1.5 text-[12.5px] font-semibold text-ink">
                        <span className="h-2 w-2 rounded-full" style={{ background: ndviColor(p.ndvi) }} />
                        {fmt(p.ndvi, 3)}
                      </span>
                    </td>
                    <td className="px-3 py-3">
                      <div className={cx('num text-[12.5px] font-bold', healthColor(p.health))}>{fmt(p.health, 1)}</div>
                      <div className="mt-1 w-16"><Meter value={p.health} tone={p.health >= 62 ? 'leaf' : p.health >= 45 ? 'amber' : 'rose'} height={3} /></div>
                    </td>
                    <td className="px-3 py-3 text-right">
                      <div className="num text-[12.5px] font-semibold text-ink">{fmt(p.yield_t_ha, 2)}</div>
                      <div className={cx('num text-[10.5px]', p.vs_history_pct >= 0 ? 'text-leaf' : 'text-amber')}>
                        {p.vs_history_pct >= 0 ? '+' : ''}{fmt(p.vs_history_pct, 1)}% vs history
                      </div>
                    </td>
                    <td className="px-3 py-3">
                      <Badge tone={levelTone(p.risk_level)}>{p.risk_level} · {Math.round(p.risk * 100)}</Badge>
                    </td>
                    <td className="max-w-[210px] px-3 py-3">
                      <div className="truncate text-[11.5px] text-muted" title={p.top_action}>{p.top_action}</div>
                    </td>
                    <td className="px-3 py-3 text-faint"><ChevronRight size={14} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>

        {/* ------------------------------------------------------- alerts */}
        <Panel
          title="Priority advisory queue"
          subtitle={`${data.alerts.length} recommendations above the confidence threshold`}
          bodyClass="max-h-[560px] space-y-2.5 overflow-y-auto p-4"
        >
          {data.alerts.length === 0 && (
            <p className="py-8 text-center text-[12px] text-faint">No high-priority advisories. All plots nominal.</p>
          )}
          {data.alerts.map((a: any, i: number) => (
            <button key={i} onClick={() => onOpenPlot(a.plot_id)}
              data-testid={`alert-${i}`}
              className="w-full rounded-xl border border-line bg-raised/50 p-3 text-left transition-all duration-200 hover:border-leaf/50 hover:bg-raised">
              <div className="flex items-center justify-between gap-2">
                <Badge tone={CAT_TONE[a.category] ?? 'neutral'}>{a.category}</Badge>
                <span className="num text-[10.5px] font-semibold text-faint">{Math.round(a.confidence * 100)}% conf</span>
              </div>
              <p className="mt-2 text-[12px] font-semibold leading-snug text-ink">{a.title}</p>
              <p className="mt-1 text-[10.5px] text-faint">{a.plot} · {a.crop} · {a.district}</p>
            </button>
          ))}
        </Panel>
      </div>

      {/* -------------------------------------------------------- charts */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <Panel title="District risk surface" subtitle="Composite risk index aggregated by revenue district">
          <div className="h-[236px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={districtData} margin={{ top: 4, right: 8, left: -22, bottom: 0 }}>
                <CartesianGrid stroke="hsl(var(--line))" vertical={false} />
                <XAxis dataKey="key" tickLine={false} axisLine={false} />
                <YAxis domain={[0, 100]} tickLine={false} axisLine={false} />
                <Tooltip
                  contentStyle={{ background: 'hsl(var(--surface))', border: '1px solid hsl(var(--line))', borderRadius: 12, fontSize: 12 }}
                  formatter={(v: any) => [`${v}`, 'Risk index']}
                />
                <Bar dataKey="riskPct" radius={[6, 6, 0, 0]} maxBarSize={54}>
                  {districtData.map((d: any, i: number) => (
                    <Cell key={i} fill={riskColor(d.risk)} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
            {districtData.map((d: any) => (
              <div key={d.key} className="rounded-xl border border-line bg-raised/40 p-2.5">
                <p className="truncate text-[11.5px] font-semibold text-ink">{d.key}</p>
                <p className="num mt-1 text-[10.5px] text-faint">{d.plots} plots · {fmt(d.area_ha, 1)} ha</p>
                <p className="num text-[10.5px] text-faint">health {fmt(d.health, 0)} · {fmt(d.yield_t, 0)} t</p>
              </div>
            ))}
          </div>
        </Panel>

        <Panel title="Crop portfolio" subtitle="Mean health score and forecast production per crop">
          <div className="h-[236px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={cropData} margin={{ top: 4, right: 8, left: -22, bottom: 0 }}>
                <CartesianGrid stroke="hsl(var(--line))" vertical={false} />
                <XAxis dataKey="key" tickLine={false} axisLine={false} interval={0}
                  tick={{ fontSize: 9.5 }} angle={-18} textAnchor="end" height={44} />
                <YAxis domain={[0, 100]} tickLine={false} axisLine={false} />
                <Tooltip
                  contentStyle={{ background: 'hsl(var(--surface))', border: '1px solid hsl(var(--line))', borderRadius: 12, fontSize: 12 }}
                />
                <Bar dataKey="health" name="Health /100" radius={[6, 6, 0, 0]} maxBarSize={40}>
                  {cropData.map((c: any, i: number) => (
                    <Cell key={i} fill={c.health >= 75 ? 'hsl(88 62% 55%)' : c.health >= 55 ? 'hsl(96 44% 42%)' : 'hsl(36 92% 58%)'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-3 space-y-1.5">
            {cropData.map((c: any) => (
              <div key={c.key} className="flex items-center gap-3">
                <span className="w-[92px] shrink-0 truncate text-[11.5px] text-muted">{c.key}</span>
                <span className="flex-1"><Meter value={c.health} tone={c.health >= 62 ? 'leaf' : 'amber'} height={5} /></span>
                <span className="num w-[86px] shrink-0 text-right text-[10.5px] text-faint">{fmt(c.yield_t, 1)} t</span>
              </div>
            ))}
          </div>
        </Panel>
      </div>

      <Panel title="Fusion pipeline" subtitle="What the platform is currently ingesting and how it flows to a decision"
        bodyClass="p-4">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {[
            { icon: CloudRain, title: 'Ingest', tone: 'sky', items: ['Sentinel-2 L2A · 10 m · 5-day revisit', 'IoT soil moisture / pH / EC', 'IMD + ECMWF 1 km downscaled', 'Mandi price feeds'] },
            { icon: Leaf, title: 'Derive', tone: 'leaf', items: ['NDVI · EVI · SAVI · NDWI · NDRE', 'LAI + chlorophyll index', 'GDD accumulation, FAO-56 ET₀', 'Anomaly z-scores vs normals'] },
            { icon: TrendingUp, title: 'Predict', tone: 'violet', items: ['Yield (GBM regressor)', 'Pest / disease (RF + HGB)', 'Drought / flood classifiers', 'Isolation-forest anomaly'] },
            { icon: ArrowUpRight, title: 'Act', tone: 'amber', items: ['Irrigation schedule + valve command', 'NPK split dosage', 'Localised SMS advisory', 'Offline advisory bundle'] },
          ].map((s) => (
            <div key={s.title} className="rounded-xl border border-line bg-raised/40 p-3.5">
              <div className="flex items-center gap-2">
                <Badge tone={s.tone}><s.icon size={11} /> {s.title}</Badge>
              </div>
              <ul className="mt-2.5 space-y-1.5">
                {s.items.map((it) => (
                  <li key={it} className="flex gap-1.5 text-[11px] leading-snug text-muted">
                    <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-faint" />{it}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <p className="num mt-3 text-[10.5px] text-faint">
          {fmtInt(Object.values(data.data_source.row_counts).reduce((a: any, b: any) => a + b, 0) as number)} rows
          across {Object.keys(data.data_source.row_counts).length} tables ·
          source: {data.data_source.source} ·
          language: {lang.toUpperCase()}
        </p>
      </Panel>
    </div>
  );
}
