'use client'

/**
 * A mock of the real overlay window.
 *
 * Built from `apps/desktop/src/ui/theme.css` — the same 380px width
 * (`--panel-w`), the same topbar, rule pill, CVD card, flow grid and outlier
 * rows. It is a picture of the product rather than an abstraction of it, and it
 * has to keep matching: when the app's panel changes, this changes too, or the
 * site is advertising something that no longer exists.
 *
 * Everything in it is illustrative and labelled as such at the bottom of the
 * hero. No number here is a claim.
 */

const OUTLIERS = [
  { kind: 'Absorption', tone: 'text-violet', price: '2418.40', side: 'ask', size: '1,940' },
  { kind: 'Trapped', tone: 'text-warn', price: '2417.90', side: 'bid', size: '612' },
  { kind: 'Cluster', tone: 'text-indigo', price: '2419.10', side: 'ask', size: '884' },
]

export function AppPanel() {
  return (
    <div className="relative w-full max-w-[380px]">
      {/* The app paints a violet radial behind its shell; the floating window
          needs the same light or it reads as a flat screenshot. */}
      <div className="aura aura-violet drift -inset-16 h-[120%] w-[120%]" />

      <div className="relative overflow-hidden rounded-[20px] border border-white/[0.1] bg-bg shadow-[0_40px_120px_-20px_rgba(0,0,0,0.8),0_0_60px_-20px_rgba(139,92,246,0.35)]">
        {/* topbar */}
        <div className="flex items-center gap-2.5 border-b border-white/[0.08] bg-bg/70 px-4 py-3.5 backdrop-blur-md">
          <span className="grad grid h-[26px] w-[26px] place-items-center rounded-lg text-[13px] font-bold text-white shadow-[0_4px_14px_rgba(139,92,246,0.4)]">
            T
          </span>
          <span className="text-[14px] font-semibold">Flow</span>
          <span className="flex-1" />
          <span className="inline-flex items-center gap-1.5 rounded-full border border-bid/30 bg-bid/10 px-2.5 py-1 text-[11px] font-semibold text-bid">
            <span className="h-[7px] w-[7px] rounded-full bg-bid" />
            Rules clear
          </span>
        </div>

        <div className="flex flex-col gap-3.5 p-4">
          {/* feed status */}
          <div className="surface flex items-center gap-2 rounded-xl px-3 py-2.5">
            <span className="h-2 w-2 rounded-full bg-bid" />
            <span className="text-[13px] font-semibold text-bid">Live</span>
            <span className="num ml-auto truncate text-[11px] text-faint">GCZ6 · 24ms</span>
          </div>

          {/* CVD */}
          <div className="surface rounded-2xl p-3.5">
            <div className="num text-[10px] tracking-[0.08em] text-faint">SESSION CVD</div>
            <div className="num mt-0.5 text-[30px] leading-tight font-bold text-bid">+4,218</div>
            <div className="num text-[12px] text-dim">last 1m −612 · vwap 2418.22</div>
          </div>

          {/* flow grid */}
          <div className="grid grid-cols-2 gap-2">
            {[
              { k: 'DELTA 1M', v: '−612', tone: 'text-ask' },
              { k: 'ABSORB', v: '1,940', tone: 'text-ink' },
              { k: 'ATR BP', v: '18.4', tone: 'text-ink' },
              { k: 'PHASE', v: 'RTH', tone: 'text-ink' },
            ].map((cell) => (
              <div key={cell.k} className="surface rounded-xl p-2.5">
                <div className="num text-[10px] tracking-[0.06em] text-faint">{cell.k}</div>
                <div className={`num text-[16px] font-semibold ${cell.tone}`}>{cell.v}</div>
              </div>
            ))}
          </div>

          {/* outliers */}
          <div className="flex flex-col gap-1.5">
            {OUTLIERS.map((o) => (
              <div
                key={o.kind}
                className="surface num grid grid-cols-[84px_1fr_auto] items-center gap-2 rounded-lg px-2.5 py-2 text-[12px]"
              >
                <span className={`text-[11px] font-semibold ${o.tone}`}>{o.kind}</span>
                <span className="text-ink">{o.price}</span>
                <span className={o.side === 'ask' ? 'text-bid' : 'text-ask'}>{o.size}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
