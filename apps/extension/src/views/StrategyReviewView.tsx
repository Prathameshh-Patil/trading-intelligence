import { motion } from "framer-motion";

import { CheckIcon } from "../ui/Icons";
import { CountUp, Stat } from "../ui/components";
import { riseIn, spring, stagger } from "../ui/motion";
import type { JournalEntry, Strategy, StrategyStats } from "../lib/types";

interface Props {
  strategy: Strategy;
  stats: StrategyStats;
  journal: JournalEntry[];
  onEdit: () => void;
}

export default function StrategyReviewView({
  strategy,
  stats,
  journal,
  onEdit,
}: Props) {
  const closed = journal.filter((entry) => entry.outcome !== "open").slice(0, 12);
  const peak = Math.max(1, ...closed.map((e) => Math.abs(e.rMultiple)));

  // Which tags show up most often on losing trades — the useful half of a review.
  const leakCounts = new Map<string, number>();

  journal
    .filter((entry) => entry.outcome === "loss")
    .forEach((entry) =>
      entry.tags.forEach((tag) =>
        leakCounts.set(tag, (leakCounts.get(tag) ?? 0) + 1),
      ),
    );

  const leaks = [...leakCounts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 4);

  return (
    <motion.div
      className="view"
      variants={stagger}
      initial="hidden"
      animate="show"
    >
      <motion.div variants={riseIn}>
        <div className="eyebrow">{strategy.market}</div>
        <h2>{strategy.name}</h2>
        <p className="lede" style={{ marginTop: 6 }}>
          {strategy.thesis}
        </p>
      </motion.div>

      <motion.div className="stat-grid" variants={stagger}>
        <Stat label="Trades" value={<CountUp value={stats.trades} />} />
        <Stat
          label="Win rate"
          value={<CountUp value={stats.winRate} suffix="%" />}
        />
        <Stat
          label="Expectancy"
          value={
            <CountUp
              value={stats.expectancy}
              decimals={2}
              suffix="R"
              prefix={stats.expectancy > 0 ? "+" : ""}
            />
          }
          tone={stats.expectancy >= 0 ? "pos" : "neg"}
        />
        <Stat
          label="Avg risk"
          value={<CountUp value={stats.avgRisk} decimals={1} suffix="%" />}
          tone={stats.avgRisk > strategy.maxRiskPct ? "neg" : undefined}
        />
        <Stat
          label="Best"
          value={<CountUp value={stats.bestR} decimals={1} suffix="R" />}
          tone="pos"
        />
        <Stat
          label="Worst"
          value={<CountUp value={stats.worstR} decimals={1} suffix="R" />}
          tone="neg"
        />
      </motion.div>

      {closed.length > 0 && (
        <motion.div variants={riseIn} className="card">
          <div className="eyebrow" style={{ marginBottom: 12 }}>
            R multiple by trade
          </div>

          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              height: 74,
            }}
          >
            {closed
              .slice()
              .reverse()
              .map((entry, i) => {
                const up = entry.rMultiple >= 0;
                const h = (Math.abs(entry.rMultiple) / peak) * 30;

                return (
                  <div
                    key={entry.id}
                    style={{
                      // Grow to fill when there are few trades, but cap the
                      // width so five entries read as a chart, not as blocks.
                      flex: "1 1 0",
                      maxWidth: 30,
                      display: "flex",
                      flexDirection: "column",
                      justifyContent: "center",
                      height: "100%",
                    }}
                    title={`${entry.symbol} ${entry.rMultiple > 0 ? "+" : ""}${entry.rMultiple}R`}
                  >
                    <div
                      style={{
                        height: 34,
                        display: "flex",
                        alignItems: "flex-end",
                      }}
                    >
                      {up && (
                        <motion.div
                          initial={{ height: 0 }}
                          animate={{ height: h }}
                          transition={{ ...spring, delay: i * 0.035 }}
                          style={{
                            width: "100%",
                            background: "#34d399",
                            borderRadius: "3px 3px 0 0",
                          }}
                        />
                      )}
                    </div>

                    <div
                      style={{ height: 1, background: "rgba(255,255,255,0.16)" }}
                    />

                    <div style={{ height: 34 }}>
                      {!up && (
                        <motion.div
                          initial={{ height: 0 }}
                          animate={{ height: h }}
                          transition={{ ...spring, delay: i * 0.035 }}
                          style={{
                            width: "100%",
                            background: "#f87171",
                            borderRadius: "0 0 3px 3px",
                          }}
                        />
                      )}
                    </div>
                  </div>
                );
              })}
          </div>
        </motion.div>
      )}

      {leaks.length > 0 && (
        <motion.div variants={riseIn} className="card">
          <div className="eyebrow" style={{ marginBottom: 10 }}>
            Where losses cluster
          </div>

          <div className="stack" style={{ gap: 8 }}>
            {leaks.map(([tag, count], i) => (
              <div key={tag} className="row" style={{ gap: 8 }}>
                <span
                  style={{
                    fontSize: 12,
                    width: 96,
                    color: "var(--text-dim)",
                  }}
                >
                  {tag}
                </span>

                <div
                  style={{
                    flex: 1,
                    height: 6,
                    borderRadius: 99,
                    background: "rgba(255,255,255,0.06)",
                    overflow: "hidden",
                  }}
                >
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${(count / leaks[0][1]) * 100}%` }}
                    transition={{ ...spring, delay: 0.1 + i * 0.06 }}
                    style={{
                      height: "100%",
                      background:
                        "linear-gradient(90deg,#8b5cf6,#6366f1)",
                    }}
                  />
                </div>

                <span
                  style={{
                    fontSize: 11,
                    color: "var(--text-faint)",
                    fontVariantNumeric: "tabular-nums",
                  }}
                >
                  {count}
                </span>
              </div>
            ))}
          </div>
        </motion.div>
      )}

      <motion.div variants={riseIn} className="card">
        <div className="eyebrow" style={{ marginBottom: 10 }}>
          Entry criteria
        </div>

        <div className="stack" style={{ gap: 8 }}>
          {strategy.entryCriteria.map((item) => (
            <div key={item} className="checklist-item">
              <span className="check">
                <CheckIcon size={10} />
              </span>
              {item}
            </div>
          ))}
        </div>
      </motion.div>

      <motion.div variants={riseIn} className="card">
        <div className="eyebrow" style={{ marginBottom: 10 }}>
          Exit criteria
        </div>

        <div className="stack" style={{ gap: 8 }}>
          {strategy.exitCriteria.map((item) => (
            <div key={item} className="checklist-item">
              <span className="check exit">
                <CheckIcon size={10} />
              </span>
              {item}
            </div>
          ))}
        </div>
      </motion.div>

      <motion.button
        variants={riseIn}
        className="btn ghost block"
        onClick={onEdit}
      >
        Change this strategy
      </motion.button>
    </motion.div>
  );
}
