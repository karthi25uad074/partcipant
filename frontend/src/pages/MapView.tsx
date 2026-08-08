import { useEffect, useMemo, useState } from 'react';
import { CircleMarker, MapContainer, Polygon, Rectangle, TileLayer, Tooltip as LTooltip, useMap, useMapEvent } from 'react-leaflet';
import { Layers, Loader2, Maximize2, Satellite, Grid3x3 } from 'lucide-react';
import { api } from '../lib/api';
import { Badge, cx, fmt, levelTone, ndviColor, Panel, riskColor } from '../lib/ui';

type Mode = 'ndvi' | 'risk' | 'health';

const MODES: { id: Mode; label: string; legend: [string, string][] }[] = [
  {
    id: 'ndvi', label: 'NDVI vigour',
    legend: [['0.2 bare', ndviColor(0.2)], ['0.45', ndviColor(0.45)], ['0.65', ndviColor(0.65)], ['0.85 dense', ndviColor(0.85)]],
  },
  {
    id: 'risk', label: 'Composite risk',
    legend: [['Low', riskColor(0.1)], ['Medium', riskColor(0.4)], ['High', riskColor(0.8)]],
  },
  {
    id: 'health', label: 'Crop health',
    legend: [['Poor', 'hsl(352 76% 60%)'], ['Fair', 'hsl(36 92% 58%)'], ['Good', 'hsl(88 62% 55%)']],
  },
];

function colorFor(p: any, mode: Mode) {
  if (mode === 'ndvi') return ndviColor(p.ndvi);
  if (mode === 'risk') return riskColor(p.risk);
  return p.health >= 62 ? 'hsl(88 62% 55%)' : p.health >= 45 ? 'hsl(36 92% 58%)' : 'hsl(352 76% 60%)';
}

function ZoomWatch({ onZoom }: { onZoom: (z: number) => void }) {
  const map = useMapEvent('zoomend', () => onZoom(map.getZoom()));
  useEffect(() => { onZoom(map.getZoom()); }, [map, onZoom]);
  return null;
}

/** Flies to the selected plot so the sub-plot NDVI raster is actually legible. */
function FlyToPlot({ target }: { target: [number, number] | null }) {
  const map = useMap();
  useEffect(() => {
    if (target) map.flyTo(target, 16, { duration: 0.9 });
  }, [map, target?.[0], target?.[1]]);
  return null;
}

function FitBounds({ bounds }: { bounds: [number, number][] }) {
  const map = useMap();
  useEffect(() => {
    if (bounds.length > 1) map.fitBounds(bounds as any, { padding: [46, 46] });
  }, [map, JSON.stringify(bounds)]);
  return null;
}

export default function MapView({ data, onOpenPlot }: { data: any; onOpenPlot: (id: string) => void }) {
  const [mode, setMode] = useState<Mode>('ndvi');
  const [geo, setGeo] = useState<any>(null);
  const [zoneOf, setZoneOf] = useState<string | null>(null);
  const [grid, setGrid] = useState<any>(null);
  const [gridBusy, setGridBusy] = useState(false);
  const [tileFail, setTileFail] = useState(false);
  const [zoom, setZoom] = useState(8);

  useEffect(() => { api.geojson().then(setGeo).catch(() => setGeo({ features: [] })); }, []);

  useEffect(() => {
    if (!zoneOf) { setGrid(null); return; }
    setGridBusy(true);
    api.ndviGrid(zoneOf, 14).then(setGrid).catch(() => setGrid(null)).finally(() => setGridBusy(false));
  }, [zoneOf]);

  const byId = useMemo(() => {
    const m: Record<string, any> = {};
    data.plots.forEach((p: any) => { m[p.plot_id] = p; });
    return m;
  }, [data]);

  const polys = useMemo(() => {
    if (!geo?.features) return [];
    return geo.features.map((f: any) => ({
      id: f.properties.plot_id,
      // GeoJSON is [lon, lat]; Leaflet needs [lat, lon].
      latlngs: f.geometry.coordinates[0].map((c: number[]) => [c[1], c[0]] as [number, number]),
      props: { ...f.properties, ...(byId[f.properties.plot_id] ?? {}) },
    }));
  }, [geo, byId]);

  const bounds = useMemo(
    () => polys.flatMap((p: any) => p.latlngs) as [number, number][],
    [polys],
  );

  const selectedCentroid = useMemo(() => {
    const p = polys.find((x: any) => x.id === zoneOf);
    return p ? (p.props.centroid as [number, number]) : null;
  }, [polys, zoneOf]);

  const legend = MODES.find((m) => m.id === mode)!.legend;

  return (
    <div className="grid grid-cols-1 gap-5 xl:grid-cols-[1fr_336px]">
      <Panel
        title="Field boundary intelligence"
        subtitle="Real plot geometry over OpenStreetMap · click a polygon to open its AI dossier"
        bodyClass="p-0"
        right={
          <div className="flex flex-wrap items-center gap-1 rounded-xl border border-line bg-raised p-0.5">
            <Layers size={13} className="ml-1.5 text-faint" />
            {MODES.map((m) => (
              <button key={m.id} onClick={() => setMode(m.id)} data-testid={`map-mode-${m.id}`}
                className={cx('rounded-lg px-2.5 py-1 text-[11px] font-semibold transition-colors',
                  mode === m.id ? 'bg-leaf text-canvas' : 'text-muted hover:text-ink')}>
                {m.label}
              </button>
            ))}
          </div>
        }
      >
        <div className="relative h-[560px] w-full overflow-hidden rounded-b-2xl">
          <MapContainer center={[10.2, 76.7]} zoom={8} scrollWheelZoom
            style={{ height: '100%', width: '100%' }} attributionControl>
            <TileLayer
              url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
              attribution='&copy; OpenStreetMap &copy; CARTO'
              subdomains={['a', 'b', 'c', 'd']}
              eventHandlers={{ tileerror: () => setTileFail(true) }}
            />
            <FitBounds bounds={bounds} />
            <ZoomWatch onZoom={setZoom} />
            <FlyToPlot target={selectedCentroid} />

            {polys.map((p: any) => (
              <Polygon key={p.id} positions={p.latlngs}
                pathOptions={{
                  color: colorFor(p.props, mode),
                  weight: zoneOf === p.id ? 3.5 : 2,
                  fillColor: colorFor(p.props, mode),
                  fillOpacity: zoneOf === p.id ? 0.12 : 0.42,
                }}
                eventHandlers={{ click: () => setZoneOf((z) => (z === p.id ? null : p.id)) }}>
                <LTooltip sticky>
                  <div className="space-y-0.5">
                    <p className="text-[12px] font-bold">{p.props.name}</p>
                    <p className="text-[10.5px] opacity-75">{p.props.crop} · {p.props.district} · {fmt(p.props.area_ha, 1)} ha</p>
                    <p className="num text-[10.5px]">
                      NDVI {fmt(p.props.ndvi, 3)} · health {fmt(p.props.health, 1)} · risk {p.props.risk_level}
                    </p>
                    <p className="text-[10px] opacity-70">Click for management zones</p>
                  </div>
                </LTooltip>
              </Polygon>
            ))}

            {/* At district scale a 3 ha polygon is sub-pixel, so plots also get a
                proportional marker that stays legible when zoomed out. */}
            {zoom < 12 && polys.map((p: any) => (
              <CircleMarker key={`m-${p.id}`} center={p.props.centroid}
                radius={zoneOf === p.id ? 11 : 7}
                pathOptions={{
                  color: 'hsl(150 12% 8%)', weight: 2,
                  fillColor: colorFor(p.props, mode), fillOpacity: 0.95,
                }}
                eventHandlers={{ click: () => setZoneOf((z) => (z === p.id ? null : p.id)) }}>
                <LTooltip sticky>
                  <div className="space-y-0.5">
                    <p className="text-[12px] font-bold">{p.props.name}</p>
                    <p className="text-[10.5px] opacity-75">{p.props.crop} · {p.props.district} · {fmt(p.props.area_ha, 1)} ha</p>
                    <p className="num text-[10.5px]">
                      NDVI {fmt(p.props.ndvi, 3)} · health {fmt(p.props.health, 1)} · risk {p.props.risk_level}
                    </p>
                  </div>
                </LTooltip>
              </CircleMarker>
            ))}

            {/* Sub-plot NDVI management-zone raster for the selected plot */}
            {grid?.cells?.map((c: any, i: number) => {
              const dLat = (grid.bounds.max_lat - grid.bounds.min_lat) / grid.size;
              const dLon = (grid.bounds.max_lon - grid.bounds.min_lon) / grid.size;
              return (
                <Rectangle key={i}
                  bounds={[[c.lat, c.lon], [c.lat + dLat, c.lon + dLon]]}
                  pathOptions={{ stroke: false, fillColor: ndviColor(c.ndvi), fillOpacity: 0.86 }}>
                  <LTooltip>
                    <span className="num text-[11px]">NDVI {fmt(c.ndvi, 3)} · zone {c.zone}</span>
                  </LTooltip>
                </Rectangle>
              );
            })}
          </MapContainer>

          {/* legend */}
          <div className="pointer-events-none absolute bottom-6 left-3 z-[500] rounded-xl border border-line bg-surface px-3 py-2.5 shadow-panel">
            <p className="label mb-1.5 text-muted">{MODES.find((m) => m.id === mode)!.label}</p>
            <div className="flex items-center gap-2.5">
              {legend.map(([l, c]) => (
                <span key={l} className="flex items-center gap-1.5 text-[10.5px] font-medium text-ink">
                  <span className="h-2.5 w-2.5 rounded-sm" style={{ background: c }} />{l}
                </span>
              ))}
            </div>
          </div>

          {tileFail && (
            <div className="absolute right-3 top-3 z-[500] rounded-xl border border-amber/40 bg-surface/92 px-3 py-2 text-[10.5px] text-amber backdrop-blur">
              Basemap tiles blocked — plot geometry still accurate
            </div>
          )}
          {gridBusy && (
            <div className="absolute left-1/2 top-3 z-[500] flex -translate-x-1/2 items-center gap-2 rounded-xl border border-line bg-surface/92 px-3 py-2 text-[11px] text-muted backdrop-blur">
              <Loader2 size={12} className="animate-spin" /> Computing management zones…
            </div>
          )}
        </div>
      </Panel>

      {/* ------------------------------------------------------------ side */}
      <div className="space-y-5">
        <Panel title="Selected plot" subtitle={zoneOf ? 'Sub-plot variable-rate zones' : 'Click any polygon on the map'}
          bodyClass="p-4">
          {!zoneOf && (
            <p className="py-6 text-center text-[12px] leading-relaxed text-faint">
              Selecting a plot renders a 14×14 NDVI raster inside its boundary — the basis for
              variable-rate fertiliser and zone-wise irrigation.
            </p>
          )}
          {zoneOf && byId[zoneOf] && (
            <div className="space-y-3">
              <div>
                <p className="text-[13.5px] font-bold text-ink">{byId[zoneOf].name}</p>
                <p className="text-[11px] text-faint">
                  {byId[zoneOf].crop} · {byId[zoneOf].owner} · {byId[zoneOf].village ?? byId[zoneOf].district}
                </p>
              </div>
              <div className="grid grid-cols-2 gap-2">
                {[
                  ['NDVI', fmt(byId[zoneOf].ndvi, 3)],
                  ['Health', `${fmt(byId[zoneOf].health, 1)}/100`],
                  ['Yield', `${fmt(byId[zoneOf].yield_t_ha, 2)} t/ha`],
                  ['Risk', byId[zoneOf].risk_level],
                ].map(([l, v]) => (
                  <div key={l} className="rounded-xl border border-line bg-raised/40 px-2.5 py-2">
                    <p className="label">{l}</p>
                    <p className="num mt-1 text-[13px] font-bold text-ink">{v}</p>
                  </div>
                ))}
              </div>

              {grid && (
                <div className="rounded-xl border border-line bg-raised/40 p-3">
                  <p className="label flex items-center gap-1.5"><Grid3x3 size={11} /> Management zones</p>
                  <div className="mt-2 space-y-1.5">
                    {Object.entries(grid.management_zones).map(([z, n]: any) => (
                      <div key={z} className="flex items-center justify-between text-[11.5px]">
                        <span className="text-muted">{z} vigour</span>
                        <span className="num font-semibold text-ink">
                          {n} cells · {Math.round((n / grid.cells.length) * 100)}%
                        </span>
                      </div>
                    ))}
                  </div>
                  <p className="num mt-2 text-[10px] leading-relaxed text-faint">
                    Base NDVI {fmt(grid.base_ndvi, 3)} · {grid.size}×{grid.size} cells ·
                    ~{fmt((byId[zoneOf].area_ha * 10000) / grid.cells.length, 0)} m² per cell
                  </p>
                </div>
              )}

              <button className="btn btn-primary w-full" onClick={() => onOpenPlot(zoneOf)}
                data-testid="button-open-dossier">
                <Maximize2 size={13} /> Open full AI dossier
              </button>
            </div>
          )}
        </Panel>

        <Panel title="District risk ranking" subtitle="Composite of drought, flood, pest, disease and anomaly"
          bodyClass="space-y-2 p-4">
          {[...data.by_district].sort((a: any, b: any) => b.risk - a.risk).map((d: any) => (
            <div key={d.key} className="rounded-xl border border-line bg-raised/40 p-3">
              <div className="flex items-center justify-between gap-2">
                <p className="text-[12.5px] font-semibold text-ink">{d.key}</p>
                <Badge tone={levelTone(d.risk >= 0.6 ? 'High' : d.risk >= 0.32 ? 'Medium' : 'Low')}>
                  {Math.round(d.risk * 100)}
                </Badge>
              </div>
              <p className="num mt-1.5 text-[10.5px] text-faint">
                {d.state} · {d.plots} plots · {fmt(d.area_ha, 1)} ha · health {fmt(d.health, 0)}/100
              </p>
            </div>
          ))}
        </Panel>

        <Panel title="Imagery provenance" bodyClass="p-4">
          <div className="space-y-2 text-[11px] leading-relaxed text-muted">
            <p className="flex items-start gap-2">
              <Satellite size={13} className="mt-0.5 shrink-0 text-leaf" />
              Sentinel-2 L2A surface reflectance, 10 m bands (B2/B4/B8) + 20 m SWIR (B11),
              5-day revisit, scenes above 40% cloud are dropped before index computation.
            </p>
            <p className="text-faint">
              Indices follow Rouse 1974 (NDVI), Huete 1997 (EVI), Huete 1988 (SAVI) and
              Gao 1996 (NDWI). Basemap © OpenStreetMap contributors.
            </p>
          </div>
        </Panel>
      </div>
    </div>
  );
}
