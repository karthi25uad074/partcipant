import { useEffect, useState } from 'react';
import {
  CloudOff, Download, Globe2, HardDriveDownload, Languages, Loader2,
  MessageSquare, Send, Signal, Smartphone,
} from 'lucide-react';
import { api, LANGS } from '../lib/api';
import { Badge, cx, fmt, levelTone, Loading, Panel } from '../lib/ui';

export default function Advisory({
  plots, lang, setLang,
}: { plots: any[]; lang: string; setLang: (l: string) => void }) {
  const [target, setTarget] = useState(plots[0]?.plot_id ?? '');
  const [sms, setSms] = useState<any>(null);
  const [sending, setSending] = useState(false);
  const [outbox, setOutbox] = useState<any[]>([]);
  const [bundle, setBundle] = useState<any>(null);
  const [bundleBusy, setBundleBusy] = useState(false);

  const refreshOutbox = () => api.smsOutbox().then(setOutbox).catch(() => setOutbox([]));
  useEffect(() => { refreshOutbox(); }, []);

  useEffect(() => {
    if (!target) return;
    setSms(null);
    api.sms(target, lang).then(setSms).catch(() => setSms(null));
  }, [target, lang]);

  const send = async () => {
    if (!target) return;
    setSending(true);
    try {
      const r = await api.sms(target, lang);
      setSms(r);
      await refreshOutbox();
    } finally { setSending(false); }
  };

  const loadBundle = async () => {
    setBundleBusy(true);
    try { setBundle(await api.offline(lang)); } finally { setBundleBusy(false); }
  };

  const downloadBundle = () => {
    if (!bundle) return;
    const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `agrisense-offline-${lang}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const p = plots.find((x) => x.plot_id === target);

  return (
    <div className="space-y-5">
      <Panel title="Delivery language" bodyClass="p-4"
        subtitle="Advisories are localised offline through a pattern + agronomic glossary layer — no network translation call, so it works on an edge gateway">
        <div className="flex flex-wrap gap-2">
          {LANGS.map((l) => (
            <button key={l.code} onClick={() => setLang(l.code)}
              data-testid={`advisory-lang-${l.code}`}
              className={cx('flex items-center gap-2 rounded-xl border px-3.5 py-2.5 transition-all duration-200',
                lang === l.code ? 'border-leaf/60 bg-leaf/12 shadow-glow' : 'border-line bg-surface hover:border-leaf/40')}>
              <Languages size={14} className={lang === l.code ? 'text-leaf' : 'text-faint'} />
              <span className="text-left">
                <span className={cx('block text-[13px] font-bold', lang === l.code ? 'text-leaf' : 'text-ink')}>
                  {l.native}
                </span>
                <span className="block text-[10px] text-faint">{l.label}</span>
              </span>
            </button>
          ))}
        </div>
      </Panel>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[300px_1fr_320px]">
        {/* ------------------------------------------------------ recipient */}
        <Panel title="Recipient" subtitle="Pick the plot to generate an advisory for" bodyClass="space-y-1.5 p-3">
          {plots.map((x) => (
            <button key={x.plot_id} onClick={() => setTarget(x.plot_id)}
              data-testid={`sms-target-${x.plot_id}`}
              className={cx('w-full rounded-xl border px-3 py-2.5 text-left transition-all duration-200',
                target === x.plot_id ? 'border-leaf/60 bg-leaf/10' : 'border-line bg-raised/40 hover:border-leaf/40')}>
              <div className="flex items-center justify-between gap-2">
                <span className="truncate text-[12px] font-semibold text-ink">{x.name}</span>
                <Badge tone={levelTone(x.risk_level)}>{x.risk_level}</Badge>
              </div>
              <p className="mt-1 truncate text-[10.5px] text-faint">{x.owner} · {x.crop} · {x.district}</p>
            </button>
          ))}
        </Panel>

        {/* ----------------------------------------------------- sms phone */}
        <Panel title="SMS / feature-phone advisory"
          subtitle="Compressed to fit GSM concatenated segments — the fallback channel when there is no data connection"
          right={sms && <Badge tone={sms.segments <= 2 ? 'leaf' : 'amber'}>
            {sms.chars} chars · {sms.segments} segment{sms.segments > 1 ? 's' : ''}
          </Badge>}>
          {!sms && <Loading rows={4} label="Composing advisory…" />}
          {sms && (
            <>
              <div className="mx-auto max-w-[352px]">
                <div className="rounded-[26px] border border-line bg-raised p-2.5 shadow-panel">
                  <div className="rounded-[20px] bg-canvas p-4">
                    <div className="flex items-center justify-between border-b border-line pb-2.5">
                      <span className="flex items-center gap-1.5 text-[10px] text-faint">
                        <Signal size={10} /> AGRISENSE
                      </span>
                      <span className="num text-[10px] text-faint">{sms.lang.toUpperCase()}</span>
                    </div>
                    <p className="mt-3 whitespace-pre-wrap break-words text-[12.5px] leading-relaxed text-ink">
                      {sms.body_localised}
                    </p>
                    <div className="mt-3 flex items-center gap-1.5 border-t border-line pt-2.5">
                      <Smartphone size={10} className="text-faint" />
                      <span className="num text-[9.5px] text-faint">
                        {p?.owner ?? 'farmer handset'} · {sms.payload_bytes} bytes · {sms.channel ?? 'SMS'}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              <div className="mt-4 flex flex-wrap items-center gap-2">
                <button className="btn btn-primary" onClick={send} disabled={sending} data-testid="button-send-sms">
                  {sending ? <Loader2 size={13} className="animate-spin" /> : <Send size={13} />}
                  Queue to gateway
                </button>
                <span className="text-[10.5px] leading-snug text-faint">
                  Queued messages persist in <span className="num">sms_outbox</span> and are replayed by the
                  aggregator worker, so nothing is lost if the SMPP link is down.
                </span>
              </div>

              <div className="mt-4 rounded-xl border border-line bg-raised/40 p-3">
                <p className="label">English source (before localisation)</p>
                <p className="mt-1.5 text-[11px] leading-relaxed text-muted">{sms.body}</p>
              </div>
            </>
          )}
        </Panel>

        {/* ------------------------------------------------------- offline */}
        <div className="space-y-5">
          <Panel title="Offline advisory bundle"
            subtitle="Low-bandwidth payload for intermittent connectivity" bodyClass="p-4">
            <button className="btn w-full" onClick={loadBundle} disabled={bundleBusy} data-testid="button-bundle">
              {bundleBusy ? <Loader2 size={13} className="animate-spin" /> : <HardDriveDownload size={13} />}
              Build bundle
            </button>
            {bundle && (
              <>
                <div className="mt-3 grid grid-cols-2 gap-2">
                  {[
                    ['Plot packs', bundle.packs?.length ?? 0],
                    ['Payload', `${fmt(JSON.stringify(bundle).length / 1024, 1)} KB`],
                    ['Language', String(bundle.lang ?? lang).toUpperCase()],
                    ['Valid for', `${bundle.ttl_hours ?? 24} h`],
                  ].map(([l, v]: any) => (
                    <div key={l} className="rounded-xl border border-line bg-raised/40 px-2.5 py-2">
                      <p className="label">{l}</p>
                      <p className="num mt-1 text-[13px] font-bold text-ink">{v}</p>
                    </div>
                  ))}
                </div>
                <div className="mt-2.5 max-h-40 space-y-1.5 overflow-y-auto rounded-xl border border-line bg-raised/40 p-2.5">
                  {bundle.packs?.slice(0, 12).map((pk: any) => (
                    <div key={pk.p} className="flex items-center justify-between gap-2">
                      <span className="truncate text-[10.5px] text-muted">{pk.n}</span>
                      <span className="num shrink-0 text-[10px] text-faint">
                        {fmt(pk.h, 0)}/100 · {pk.rl}
                      </span>
                    </div>
                  ))}
                </div>
                <button className="btn mt-2.5 w-full" onClick={downloadBundle} data-testid="button-download-bundle">
                  <Download size={13} /> Download JSON
                </button>
                <p className="mt-2.5 text-[10.5px] leading-relaxed text-faint">
                  Gzip-compressed over the wire. The bundle carries the current advisory, the 7-day irrigation
                  plan and the localised UI dictionary so the handset app stays fully usable with the radio off.
                </p>
              </>
            )}
            {!bundle && (
              <p className="mt-3 flex items-start gap-1.5 text-[10.5px] leading-relaxed text-faint">
                <CloudOff size={12} className="mt-0.5 shrink-0" />
                Builds a single compressed payload containing every plot's latest advisory, so the mobile app
                can operate for days without a connection.
              </p>
            )}
          </Panel>

          <Panel title="Gateway outbox" subtitle={`${outbox.length} messages queued or sent`}
            bodyClass="max-h-[420px] space-y-2 overflow-y-auto p-3">
            {outbox.length === 0 && (
              <p className="py-6 text-center text-[11.5px] text-faint">Outbox empty.</p>
            )}
            {[...outbox].reverse().map((m: any, i: number) => (
              <div key={i} className="rounded-xl border border-line bg-raised/40 p-2.5">
                <div className="flex items-center justify-between gap-2">
                  <span className="num text-[10.5px] font-semibold text-muted">{m.phone ?? m.plot_id}</span>
                  <Badge tone={m.status === 'sent' ? 'leaf' : 'amber'}>{m.status ?? 'queued'}</Badge>
                </div>
                <p className="mt-1.5 line-clamp-3 text-[10.5px] leading-snug text-faint">{m.body ?? m.message}</p>
                {m.created_at && <p className="num mt-1 text-[9.5px] text-faint">{String(m.created_at).slice(0, 16).replace('T', ' ')}</p>}
              </div>
            ))}
          </Panel>
        </div>
      </div>

      <Panel title="Non-functional posture" bodyClass="grid grid-cols-1 gap-3 p-4 sm:grid-cols-2 lg:grid-cols-4"
        subtitle="How the platform satisfies the offline, low-bandwidth, scalability and security requirements">
        {[
          {
            icon: CloudOff, tone: 'amber', title: 'Offline capability',
            body: 'Three-tier data layer: Supabase Postgres → local SQLite mirror → in-process dataset. Writes made while offline are queued and replayed in order.',
          },
          {
            icon: Signal, tone: 'sky', title: 'Low bandwidth',
            body: 'GZip middleware on every response, a 45-second inference cache, and an offline bundle endpoint that ships one compact payload instead of many round trips.',
          },
          {
            icon: Globe2, tone: 'leaf', title: 'Scale & edge',
            body: 'Stateless FastAPI workers scale horizontally behind any load balancer. Tree-based models serialise under 6 MB and run on a field gateway CPU.',
          },
          {
            icon: MessageSquare, tone: 'violet', title: 'Security & fault tolerance',
            body: 'Row-level security policies on every Supabase table, service-role writes only from the server, and a global exception handler that degrades to a typed error instead of a 500.',
          },
        ].map((c) => (
          <div key={c.title} className="rounded-xl border border-line bg-raised/40 p-3.5">
            <Badge tone={c.tone}><c.icon size={11} /> {c.title}</Badge>
            <p className="mt-2.5 text-[11px] leading-relaxed text-muted">{c.body}</p>
          </div>
        ))}
      </Panel>
    </div>
  );
}
