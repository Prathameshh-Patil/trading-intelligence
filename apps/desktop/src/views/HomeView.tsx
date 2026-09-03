import { motion } from "framer-motion";

import {
  BookIcon,
  ChartIcon,
  ScanIcon,
  ShieldIcon,
  SlidersIcon,
  SparkIcon,
} from "../ui/Icons";
import { ActionTile, CountUp, Stat } from "../ui/components";
import { riseIn, stagger } from "../ui/motion";
import type { RiskLevel } from "../lib/rules";
import type { RuleViolation, StrategyStats, ViewKey } from "../lib/types";

interface Props {
  stats: StrategyStats;
  todayCount: number;
  violations: RuleViolation[];
  level: RiskLevel;
  strategyName: string;
  onNavigate: (view: ViewKey) => void;
}

export default function HomeView({
  stats,
  todayCount,
  violations,
  level,
  strategyName,
  onNavigate,
}: Props) {
  const hardBreaches = violations.filter((v) => v.severity === "hard");

  return (
    <motion.div
      className="view"
      variants={stagger}
      initial="hidden"
      animate="show"
    >
      <motion.div variants={riseIn}>
        <div className="eyebrow">Active strategy</div>
        <h2>{strategyName}</h2>
      </motion.div>

      {level !== "clear" && (
        <motion.button
          variants={riseIn}
          className={`notice ${level === "breach" ? "error" : "warn"}`}
          onClick={() => onNavigate("rules")}
          style={{
            textAlign: "left",
            cursor: "pointer",
            width: "100%",
            border: undefined,
          }}
        >
          <strong>
            {hardBreaches.length > 0
              ? `${hardBreaches.length} hard rule${hardBreaches.length > 1 ? "s" : ""} broken today.`
              : `${violations.length} rule${violations.length > 1 ? "s" : ""} need attention.`}
          </strong>{" "}
          {violations[0]?.message} Tap to review.
        </motion.button>
      )}

      <motion.div className="stat-grid" variants={stagger}>
        <Stat label="Today" value={<CountUp value={todayCount} />} />

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
      </motion.div>

      <motion.div className="tiles" variants={stagger}>
        <ActionTile
          wide
          primary
          icon={<ScanIcon size={17} />}
          title="Analyze screen"
          subtitle="Capture the chart in view and get a directional read with confidence and signals."
          onClick={() => onNavigate("analyze")}
        />

        <ActionTile
          wide
          icon={<SparkIcon size={17} />}
          title="Order flow"
          subtitle="Live delta, session CVD and flagged outliers from the engine."
          onClick={() => onNavigate("flow")}
        />

        <ActionTile
          icon={<ShieldIcon size={17} />}
          title="Trade rules"
          subtitle="Guardrails and live breaches."
          badge={violations.length}
          onClick={() => onNavigate("rules")}
        />

        <ActionTile
          icon={<ChartIcon size={17} />}
          title="Review strategy"
          subtitle="How the plan is performing."
          onClick={() => onNavigate("strategy-review")}
        />

        <ActionTile
          icon={<SlidersIcon size={17} />}
          title="Change strategy"
          subtitle="Edit thesis and criteria."
          onClick={() => onNavigate("strategy-change")}
        />

        <ActionTile
          icon={<BookIcon size={17} />}
          title="Journal"
          subtitle="Log and review trades."
          onClick={() => onNavigate("journal")}
        />
      </motion.div>
    </motion.div>
  );
}
