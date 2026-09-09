/**
 * S7 · the forecast surface — the reach table, as a trader reads it.
 *
 * Three things about this view are load-bearing, and all three are the kind of
 * decision that looks like a styling choice and is not.
 *
 * **1. Every probability renders as a band, never a number.** `p` reads
 * same-bar ties to the stop and `pMax` to the target; the truth is inside and
 * no bar frame can say where. M1 measured 10.2% of cells undecided by that band
 * and 20.45% of bars wide enough to tie at the tight corner of the grid. A
 * single figure — including the midpoint, *especially* the midpoint — is a
 * precision the data does not have, and it is the one number a trader would
 * quote back at us. `strategy-precommit.md` §10 rule 2.
 *
 * **2. "No forecast" gets a designed state, not an empty div.** 28 of the real
 * table's 144 cells are below the floor (`REACH.md` §1) — a minority, but a
 * concentrated one: both transition phases lose their entire CONTRACTING state
 * (§2), so a trader working the London-NY handoff meets the empty state far
 * more often than 19% suggests. It is not an error and is not styled as one.
 *
 * **3. Nothing here suggests a bracket.** `reach.py`'s first line: *"This
 * module is a LOOKUP, not a chooser."* `suggested` is null until a pass line is
 * committed, and the UI must not quietly become the chooser by sorting the list
 * so the best-looking row lands on top. The rows render in grid order.
 */

import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";

import { getForecaster, getMockForecasterControls } from "../lib/engine";
import { MIN_SAMPLES, type ForecastResult, type HorizonMinutes } from "../lib/engine/forecast";
import { WARM_UP_MINUTES } from "../lib/engine/forecastMock";

const HORIZONS: HorizonMinutes[] = [15, 30, 60];

const pct = (n: number) => `${(n * 100).toFixed(0)}%`;
const fmt = (n: number) => n.toLocaleString("en-US");

const clock = (t: number) =>
  new Date(t).toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "America/New_York",
  });

/**
 * What the trader is told when there is no forecast.
 *
 * `reach.lookup` returns `None` for two reasons and forbids distinguishing them
 * *into a forecast* — that rule is about arithmetic, and it holds: none of these
 * becomes a number. The copy differs because the required response differs. One
 * of them is "wait, and here is until when"; the others are not.
 */
const UNAVAILABLE_COPY = {
  "warming-up": {
    title: "Warming up",
    body:
      `The vol state compares this hour's volatility to the previous hour's, so the ` +
      `first forecast needs ${WARM_UP_MINUTES} minutes of feed. This is the feed working, not failing.`,
  },
  "thin-bucket": {
    title: "Not enough history",
    body:
      `This bucket has fewer than ${fmt(MIN_SAMPLES)} legs in 19 months, so there is no ` +
      `honest number to give. Most buckets are like this. Nothing is wrong.`,
  },
  "no-key": {
    title: "No bucket for this bar",
    body:
      "The feed has a gap, or the window behind this bar is not full. A bar with no " +
      "bucket gets no forecast rather than a guess at which bucket it belongs to.",
  },
  "no-table": {
    title: "No table loaded",
    body: "Nothing is serving the reach table. This one is a wiring fault, not a market condition.",
  },
} as const;

export default function ForecastView() {
  const forecaster = useMemo(() => getForecaster(), []);
  const controls = useMemo(() => getMockForecasterControls(), []);

  const [horizon, setHorizon] = useState<HorizonMinutes>(30);
  const [now, setNow] = useState(() => Date.now());
  const [connectedAt] = useState(() => Date.now());
  const [tick, setTick] = useState(0);

  // The warm-up is a countdown, so this view needs its own clock rather than
  // rendering once and looking frozen for two hours.
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 1_000);
    return () => window.clearInterval(id);
  }, []);

  const result: ForecastResult = useMemo(
    // `tick` is here so the mock controls force a re-read; the lookup itself is
    // pure and returns the same answer for the same key.
    () => forecaster.forecastAt(now, horizon),
    [forecaster, now, horizon, tick],
  );

  const cell = useMemo(() => forecaster.cellAt(now), [forecaster, now, tick]);
  const coverage = controls?.coverage();

  const readyAt = connectedAt + WARM_UP_MINUTES * 60_000;
  const minutesLeft = Math.max(0, Math.ceil((readyAt - now) / 60_000));

  return (
    <div className="view">
      <div className="eyebrow">FORECAST</div>

      <div className="horizon-row" role="group" aria-label="Horizon">
        {HORIZONS.map((h) => (
          <button
            key={h}
            className={`horizon-btn${h === horizon ? " active" : ""}`}
            onClick={() => setHorizon(h)}
            aria-pressed={h === horizon}
          >
            {h}m
          </button>
        ))}
      </div>

      {/*
        The bucket, always — including when there is no forecast. What the
        lookup was made with is exactly what a trader needs to see in order to
        disbelieve the answer, and hiding it on the empty path is how a tool
        becomes unauditable in precisely the case that most needs auditing.
      */}
      <div className="bucket-card">
        <div className="cvd-label">BUCKET</div>
        {cell ? (
          <div className="bucket-grid">
            <span className="bucket-k">phase</span>
            <span className="bucket-v">{cell.phase}</span>
            <span className="bucket-k">vol</span>
            <span className="bucket-v">{cell.volState}</span>
            <span className="bucket-k">atr bp</span>
            <span className="bucket-v">{cell.atrBucket}</span>
            <span className="bucket-k">side</span>
            <span className="bucket-v">{cell.side === 1 ? "long" : "short"}</span>
          </div>
        ) : (
          <div className="empty-note">No bucket — see below.</div>
        )}
      </div>

      {result.forecast === null ? (
        <motion.div
          className={`forecast-empty ${result.unavailable}`}
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <div className="forecast-empty-title">
            {UNAVAILABLE_COPY[result.unavailable].title}
          </div>
          <div className="forecast-empty-body">
            {UNAVAILABLE_COPY[result.unavailable].body}
          </div>

          {/*
            A real clock time, not a spinner. `reach.cell_of` says the two-hour
            warm-up is "correct rather than broken" and worth saying out loud,
            because otherwise it is discovered as "the product does not work at
            the open" — which is a support ticket, at 09:30, from a paying
            subscriber.
          */}
          {result.unavailable === "warming-up" && (
            <div className="warmup-line">
              <div className="warmup-bar">
                <div
                  className="warmup-fill"
                  style={{
                    width: `${Math.min(100, 100 * (1 - minutesLeft / WARM_UP_MINUTES))}%`,
                  }}
                />
              </div>
              <span className="warmup-eta">
                first forecast ~{clock(readyAt)} ET · {minutesLeft}m
              </span>
            </div>
          )}
        </motion.div>
      ) : (
        <>
          <div className="forecast-meta">
            {fmt(result.forecast.bucket.n)} legs · {horizon}m horizon ·{" "}
            {result.forecast.reach.length} of 24 brackets clear
          </div>

          <div className="reach-head">
            <span>target</span>
            <span>stop</span>
            <span className="reach-band-h">p(target first)</span>
            <span>n</span>
          </div>

          <div className="reach-list">
            {result.forecast.reach.map((r) => {
              const width = Math.max(2, (r.pMax - r.p) * 100);
              return (
                <div key={`${r.targetAtr}-${r.stopAtr}`} className="reach-row">
                  <span className="reach-geo">{r.targetAtr.toFixed(2)}</span>
                  <span className="reach-geo">{r.stopAtr.toFixed(2)}</span>

                  {/*
                    The band. Rendered as a range and as a bar with real width,
                    because a band drawn at one pixel reads as a point estimate
                    and the whole rule is that it is not one.
                  */}
                  <span className="reach-band">
                    <span className="reach-band-track">
                      <span
                        className="reach-band-fill"
                        style={{ left: `${r.p * 100}%`, width: `${width}%` }}
                      />
                    </span>
                    <span className="reach-band-text">
                      {pct(r.p)}–{pct(r.pMax)}
                    </span>
                  </span>

                  <span className="reach-n">{fmt(r.n)}</span>
                </div>
              );
            })}
          </div>

          {/*
            The rest of the distribution. p_neither is usually the largest of the
            three and is the number a trader most needs in order not to read a
            low p(target) as a high p(stop).
          */}
          <div className="eyebrow">WHERE THE REST GOES</div>
          <div className="rest-note">
            At {result.forecast.reach[0].targetAtr.toFixed(2)}/
            {result.forecast.reach[0].stopAtr.toFixed(2)}: stop first{" "}
            {pct(result.forecast.reach[0].pStop)}, neither barrier inside {horizon}m{" "}
            {pct(result.forecast.reach[0].pNeither)}.
          </div>

          {/*
            §10 rule 3, enforced in the UI as well as the table. If this ever
            renders a bracket, someone has made the lookup a chooser.
          */}
          <div className="no-suggestion">
            No suggested bracket. The table counts what happened; it does not pick.
          </div>
        </>
      )}

      {controls && (
        <>
          <div className="eyebrow">MOCK — BREAK IT ON PURPOSE</div>
          <div className="mock-note">
            Invented numbers on the real key shape. {coverage?.clearing}/{coverage?.cells} cells
            clear {fmt(MIN_SAMPLES)} legs ({Math.round((coverage?.fraction ?? 0) * 100)}%) — the
            real table was predicted at a third to a half.
          </div>
          <div className="mock-controls">
            <button
              className="mock-btn"
              onClick={() => {
                controls.restartWarmUp();
                setTick((n) => n + 1);
              }}
            >
              Warm up
            </button>
            <button
              className="mock-btn"
              onClick={() => {
                controls.forceThin();
                setTick((n) => n + 1);
              }}
            >
              Thin bucket
            </button>
            <button
              className="mock-btn"
              onClick={() => {
                controls.forceNoTable();
                setTick((n) => n + 1);
              }}
            >
              No table
            </button>
            <button
              className="mock-btn"
              onClick={() => {
                controls.forceClearing();
                setTick((n) => n + 1);
              }}
            >
              A cell that clears
            </button>
            <button
              className="mock-btn primary"
              onClick={() => {
                controls.resume();
                controls.finishWarmUp();
                setTick((n) => n + 1);
              }}
            >
              Resume
            </button>
          </div>
        </>
      )}
    </div>
  );
}
