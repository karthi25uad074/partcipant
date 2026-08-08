import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Activity, AlertTriangle, Cpu, Droplets, Globe2, Leaf, Map as MapIcon,
  MessageSquare, Moon, RefreshCw, Satellite, Sun, WifiOff,
} from 'lucide-react';
import { api, LANGS } from './lib/api';
import { Badge, cx, ErrorState, Loading } from './lib/ui';
import Overview from './pages/Overview';
import PlotIntel from './pages/PlotIntel';
import MapView from './pages/MapView';
import Advisory from './pages/Advisory';
import Models from './pages/Models';

/* ------------------------------------------------------------------ logo --- */
export function Logo({ size = 26 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" aria-label="AgriSense logo"
      className="text-leaf shrink-0">
      <path d="M16 29V14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
      <path d="M16 15C16 9 12 4 5 3c-1 7 3 12 11 12Z" stroke="currentColor" strokeWidth="2"
        strokeLinejoin="round" />
      <path d="M16 21c0-5 3.5-9 10-10 1 6-3 10-10 10Z" stroke="currentColor" strokeWidth="2"
        strokeLinejoin="round" opacity="0.62" />
      <circle cx="16" cy="6" r="2.4" stroke="currentColor" strokeWidth="1.6" opacity="0.9" />
      <path d="M9.5 6.2 4 4.6M22.5 6.2 28 4.6" stroke="currentColor" strokeWidth="1.4"
        strokeLinecap="round" opacity="0.5" />
    </svg>
  );
}

type Tab = 'overview' | 'plot' | 'map' | 'advisory' | 'models';

const NAV: { id: Tab; label: string; icon: any; hint: string }[] = [
  { id: 'overview', label: 'Command Center', icon: Activity, hint: 'Fleet KPIs, alerts, district risk' },
  { id: 'map', label: 'GIS Intelligence', icon: MapIcon, hint: 'Plot polygons, NDVI zone raster' },
  { id: 'plot', label: 'Plot Intelligence', icon: Satellite, hint: 'Per-plot AI deep dive + XAI' },
  { id: 'advisory', label: 'Advisory & SMS', icon: MessageSquare, hint: 'Multi-language farmer delivery' },
  { id: 'models', label: 'Models & Benchmark', icon: Cpu, hint: 'Accuracy, latency, API reference' },
];

export default function App() {
  const [tab, setTab] = useState<Tab>('overview');
  const [lang, setLang] = useState('en');
  const [dark, setDark] = useState(true);
  const [plotId, setPlotId] = useState<string | null>(null);
  const [health, setHealth] = useState<any>(null);
  const [overview, setOverview] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(true);

  useEffect(() => {
    document.documentElement.classList.toggle('light', !dark);
  }, [dark]);

  const load = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const [h, o] = await Promise.all([api.health(), api.overview(lang)]);
      setHealth(h);
      setOverview(o);
      setPlotId((p) => p ?? o.plots[0]?.plot_id ?? null);
    } catch (e: any) {
      setError(e.message ?? String(e));
    } finally {
      setBusy(false);
    }
  }, [lang]);

  useEffect(() => { load(); }, [load]);

  const openPlot = (id: string) => { setPlotId(id); setTab('plot'); };

  const source = health?.data?.source;
  const sourceLabel = source === 'supabase' ? 'Supabase Postgres'
    : source === 'sqlite-cache' ? 'Local cache (offline)' : 'Demo dataset';

  const alerts = overview?.alerts?.length ?? 0;

  const body = useMemo(() => {
    if (error) return <ErrorState error={error} onRetry={load} />;
    if (!overview) return <div className="panel p-6"><Loading rows={6} label="Training models and fusing environmental layers…" /></div>;
    switch (tab) {
      case 'overview': return <Overview data={overview} lang={lang} onOpenPlot={openPlot} />;
      case 'map': return <MapView data={overview} onOpenPlot={openPlot} />;
      case 'plot': return <PlotIntel plots={overview.plots} plotId={plotId} lang={lang} onSelect={setPlotId} />;
      case 'advisory': return <Advisory plots={overview.plots} lang={lang} setLang={setLang} />;
      case 'models': return <Models />;
    }
  }, [tab, overview, error, plotId, lang, load]);

  return (
    <div className="flex min-h-screen bg-canvas">
      {/* ------------------------------------------------------------ rail */}
      <aside className="sticky top-0 hidden h-screen w-[248px] shrink-0 flex-col border-r border-line bg-surface/70 backdrop-blur lg:flex">
        <div className="flex items-center gap-2.5 px-5 py-5">
          <Logo size={28} />
          <div className="leading-none">
            <p className="text-[15px] font-black tracking-tight text-ink">AgriSense</p>
            <p className="mt-1 text-[9.5px] font-semibold uppercase tracking-[0.16em] text-faint">
              Climate × Crop AI
            </p>
          </div>
        </div>

        <nav className="flex-1 space-y-1 px-3">
          {NAV.map((n) => {
            const active = tab === n.id;
            return (
              <button
                key={n.id}
                onClick={() => setTab(n.id)}
                data-testid={`nav-${n.id}`}
                className={cx(
                  'group relative flex w-full items-start gap-2.5 rounded-xl px-3 py-2.5 text-left transition-all duration-200',
                  active ? 'bg-leaf/12 text-leaf' : 'text-muted hover:bg-raised hover:text-ink',
                )}
              >
                {active && <span className="absolute left-0 top-2.5 h-6 w-[2.5px] rounded-full bg-leaf" />}
                <n.icon size={15} className="mt-0.5 shrink-0" />
                <span className="min-w-0">
                  <span className="block truncate text-[13px] font-semibold">{n.label}</span>
                  <span className="mt-0.5 block truncate text-[10.5px] text-faint">{n.hint}</span>
                </span>
                {n.id === 'overview' && alerts > 0 && (
                  <span className="num ml-auto mt-0.5 rounded-full bg-rose/20 px-1.5 py-0.5 text-[10px] font-bold text-rose">
                    {alerts}
                  </span>
                )}
              </button>
            );
          })}
        </nav>

        <div className="space-y-2.5 border-t border-line p-4">
          <div className="flex items-center gap-1.5">
            <span className={cx('h-1.5 w-1.5 rounded-full', source === 'supabase' ? 'bg-leaf' : 'bg-amber', 'animate-pulseline')} />
            <span className="text-[10.5px] font-medium text-muted">{sourceLabel}</span>
          </div>
          <p className="num text-[10px] leading-relaxed text-faint">
            {health?.data?.row_counts
              ? `${Object.values(health.data.row_counts).reduce((a: number, b: any) => a + Number(b), 0 as number).toLocaleString()} rows fused`
              : '—'}
            <br />6 models · {health?.languages?.length ?? 4} languages
          </p>
        </div>
      </aside>

      {/* ------------------------------------------------------------ main */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 border-b border-line bg-canvas/85 backdrop-blur-md">
          <div className="flex flex-wrap items-center gap-3 px-4 py-3 md:px-7">
            <div className="flex items-center gap-2 lg:hidden">
              <Logo size={22} />
              <span className="text-[14px] font-black tracking-tight">AgriSense</span>
            </div>

            <div className="hidden min-w-0 md:block">
              <h1 className="truncate text-[15px] font-bold leading-tight text-ink">
                {NAV.find((n) => n.id === tab)?.label}
              </h1>
              <p className="mt-0.5 truncate text-[11px] text-faint">
                Hyper-local climate intelligence &amp; precision agriculture decision support
              </p>
            </div>

            <div className="ml-auto flex flex-wrap items-center gap-2">
              {source !== 'supabase' && (
                <Badge tone="amber" title="Supabase not configured — serving the deterministic demo tier">
                  <WifiOff size={11} /> Demo tier
                </Badge>
              )}
              <Badge tone="leaf"><Droplets size={11} /> {overview ? `${(overview.kpi.water_saved_l / 1e6).toFixed(2)}M L saved` : '—'}</Badge>
              {alerts > 0 && (
                <Badge tone="rose"><AlertTriangle size={11} /> {alerts} high-priority</Badge>
              )}

              <div className="flex items-center gap-1 rounded-xl border border-line bg-raised p-0.5">
                <Globe2 size={13} className="ml-1.5 text-faint" />
                {LANGS.map((l) => (
                  <button
                    key={l.code}
                    onClick={() => setLang(l.code)}
                    data-testid={`lang-${l.code}`}
                    title={l.label}
                    className={cx(
                      'rounded-lg px-2 py-1 text-[11px] font-semibold transition-colors',
                      lang === l.code ? 'bg-leaf text-canvas' : 'text-muted hover:text-ink',
                    )}
                  >
                    {l.code === 'en' ? 'EN' : l.native}
                  </button>
                ))}
              </div>

              <button className="btn px-2.5" onClick={() => setDark((d) => !d)}
                data-testid="button-theme" title="Toggle theme">
                {dark ? <Sun size={14} /> : <Moon size={14} />}
              </button>
              <button className="btn px-2.5" onClick={load} disabled={busy}
                data-testid="button-refresh" title="Re-run the inference pipeline">
                <RefreshCw size={14} className={busy ? 'animate-spin' : ''} />
              </button>
            </div>
          </div>

          {/* mobile nav */}
          <div className="flex gap-1 overflow-x-auto border-t border-line px-3 py-2 lg:hidden">
            {NAV.map((n) => (
              <button key={n.id} onClick={() => setTab(n.id)}
                className={cx('flex shrink-0 items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[11.5px] font-semibold',
                  tab === n.id ? 'bg-leaf/12 text-leaf' : 'text-muted')}>
                <n.icon size={13} /> {n.label.split(' ')[0]}
              </button>
            ))}
          </div>
        </header>

        <main className="min-w-0 flex-1 px-4 py-5 md:px-7 md:py-6">{body}</main>

        <footer className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-line px-4 py-4 text-[10.5px] text-faint md:px-7">
          <span className="flex items-center gap-1.5"><Leaf size={11} className="text-leaf" /> AgriSense v1.0</span>
          <span>React + Vite · FastAPI · scikit-learn · Supabase Postgres · Leaflet GIS</span>
          <span className="num ml-auto">
            Data source: {sourceLabel} · {health?.data?.queued_writes ?? 0} queued offline writes
          </span>
        </footer>
      </div>
    </div>
  );
}
