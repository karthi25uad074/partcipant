import type { ReactNode } from 'react';

export const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(' ');

export const fmt = (n: number | null | undefined, d = 1) =>
  n === null || n === undefined || Number.isNaN(n) ? '—' : Number(n).toFixed(d);

export const fmtInt = (n: number | null | undefined) =>
  n === null || n === undefined ? '—' : Math.round(n).toLocaleString('en-IN');

export const pct = (n: number | null | undefined, d = 0) =>
  n === null || n === undefined ? '—' : `${(n * 100).toFixed(d)}%`;

export const litres = (n: number) =>
  n >= 1e6 ? `${(n / 1e6).toFixed(2)}M L` : n >= 1e3 ? `${(n / 1e3).toFixed(1)}k L` : `${Math.round(n)} L`;

/** Sequential greenness ramp used consistently for NDVI everywhere. */
export function ndviColor(v: number) {
  const stops: [number, string][] = [
    [0.1, '#7c4a1e'], [0.2, '#a1712c'], [0.3, '#c9a227'], [0.45, '#a8c62a'],
    [0.6, '#63b12c'], [0.72, '#2f9e44'], [0.85, '#14803c'], [1, '#0a5c2c'],
  ];
  for (const [t, c] of stops) if (v <= t) return c;
  return '#0a5c2c';
}

export function riskColor(v: number) {
  if (v >= 0.6) return 'hsl(352 76% 60%)';
  if (v >= 0.32) return 'hsl(36 92% 58%)';
  return 'hsl(88 62% 55%)';
}

export function healthColor(score: number) {
  if (score >= 78) return 'text-leaf';
  if (score >= 62) return 'text-leaf';
  if (score >= 45) return 'text-amber';
  return 'text-rose';
}

const TONE: Record<string, string> = {
  leaf: 'border-leaf/40 bg-leaf/10 text-leaf',
  amber: 'border-amber/40 bg-amber/10 text-amber',
  rose: 'border-rose/40 bg-rose/10 text-rose',
  sky: 'border-sky/40 bg-sky/10 text-sky',
  violet: 'border-violet/40 bg-violet/10 text-violet',
  neutral: 'border-line bg-raised text-muted',
};

export function Badge({
  children, tone = 'neutral', className = '', title,
}: { children: ReactNode; tone?: keyof typeof TONE | string; className?: string; title?: string }) {
  return (
    <span title={title} className={cx('chip', TONE[tone] ?? TONE.neutral, className)}>
      {children}
    </span>
  );
}

export const levelTone = (l: string) =>
  l === 'High' || l === 'Critical' || l === 'Poor' ? 'rose'
    : l === 'Medium' || l === 'Moderate' ? 'amber'
      : 'leaf';

export function Panel({
  title, subtitle, right, children, className = '', bodyClass = 'p-5',
}: {
  title?: ReactNode; subtitle?: ReactNode; right?: ReactNode;
  children: ReactNode; className?: string; bodyClass?: string;
}) {
  return (
    <section className={cx('panel animate-fade-up', className)}>
      {(title || right) && (
        <header className="panel-head">
          <div className="min-w-0">
            {title && <h2 className="text-[13.5px] font-bold leading-tight text-ink">{title}</h2>}
            {subtitle && <p className="mt-1 text-[11.5px] leading-snug text-faint">{subtitle}</p>}
          </div>
          {right && <div className="shrink-0">{right}</div>}
        </header>
      )}
      <div className={bodyClass}>{children}</div>
    </section>
  );
}

export function Stat({
  label, value, unit, sub, tone = 'ink', icon,
}: {
  label: string; value: ReactNode; unit?: string; sub?: ReactNode;
  tone?: 'ink' | 'leaf' | 'amber' | 'rose' | 'sky'; icon?: ReactNode;
}) {
  const toneCls = { ink: 'text-ink', leaf: 'text-leaf', amber: 'text-amber', rose: 'text-rose', sky: 'text-sky' }[tone];
  return (
    <div className="panel px-4 py-3.5">
      <div className="flex items-center justify-between gap-2">
        <span className="label">{label}</span>
        {icon && <span className="text-faint">{icon}</span>}
      </div>
      <div className={cx('mt-2 flex items-baseline gap-1.5', toneCls)}>
        <span className="num text-[22px] font-bold leading-none tracking-tight">{value}</span>
        {unit && <span className="text-[11px] font-medium text-faint">{unit}</span>}
      </div>
      {sub && <div className="mt-1.5 text-[11px] leading-snug text-faint">{sub}</div>}
    </div>
  );
}

export function Meter({
  value, max = 100, tone = 'leaf', height = 6,
}: { value: number; max?: number; tone?: string; height?: number }) {
  const w = Math.max(0, Math.min(100, (value / max) * 100));
  const bg = { leaf: 'bg-leaf', amber: 'bg-amber', rose: 'bg-rose', sky: 'bg-sky', violet: 'bg-violet' }[tone] ?? 'bg-leaf';
  return (
    <div className="w-full overflow-hidden rounded-full bg-raised" style={{ height }}>
      <div className={cx('h-full rounded-full transition-all duration-700', bg)} style={{ width: `${w}%` }} />
    </div>
  );
}

export function Confidence({ value }: { value: number }) {
  const tone = value >= 0.8 ? 'leaf' : value >= 0.6 ? 'amber' : 'rose';
  return (
    <span className="inline-flex items-center gap-2" title="Model confidence: skill × in-distribution typicality">
      <span className="w-14"><Meter value={value * 100} tone={tone} height={4} /></span>
      <span className="num text-[11px] font-semibold text-muted">{pct(value)}</span>
    </span>
  );
}

export function Empty({ text, hint }: { text: string; hint?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-1.5 py-12 text-center">
      <p className="text-[13px] font-semibold text-muted">{text}</p>
      {hint && <p className="max-w-sm text-[11.5px] text-faint">{hint}</p>}
    </div>
  );
}

export function Loading({ rows = 4, label }: { rows?: number; label?: string }) {
  return (
    <div className="space-y-3">
      {label && <p className="text-[11.5px] text-faint">{label}</p>}
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="skeleton" style={{ height: 14 + (i % 3) * 8, width: `${100 - i * 7}%` }} />
      ))}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: string; onRetry?: () => void }) {
  return (
    <div className="panel p-6">
      <p className="text-[13px] font-bold text-rose">Backend unreachable</p>
      <p className="mt-1.5 max-w-lg text-[12px] leading-relaxed text-muted">{error}</p>
      <p className="mt-3 text-[11.5px] leading-relaxed text-faint">
        Start the Python API from the <span className="num">backend/</span> folder:
        <span className="num ml-1 rounded bg-raised px-1.5 py-0.5 text-ink">
          uvicorn app.main:app --port 8000
        </span>
      </p>
      {onRetry && <button className="btn mt-4" onClick={onRetry}>Retry connection</button>}
    </div>
  );
}
