import { AnimatePresence, motion } from "framer-motion";

import { AlertIcon, CheckIcon } from "../ui/Icons";
import { Toggle } from "../ui/components";
import { riseIn, spring, stagger } from "../ui/motion";
import type { RuleViolation, TradeRule } from "../lib/types";

interface Props {
  rules: TradeRule[];
  violations: RuleViolation[];
  onToggle: (id: string, enabled: boolean) => void;
}

export default function RulesView({ rules, violations, onToggle }: Props) {
  const byRule = new Map(violations.map((v) => [v.ruleId, v]));
  const breached = violations.filter((v) => v.severity === "hard").length;

  return (
    <motion.div
      className="view"
      variants={stagger}
      initial="hidden"
      animate="show"
    >
      <motion.div variants={riseIn}>
        <div className="eyebrow">Guardrails</div>
        <h2>
          {violations.length === 0
            ? "Everything inside the plan"
            : `${violations.length} rule${violations.length > 1 ? "s" : ""} flagged`}
        </h2>

        <p className="lede" style={{ marginTop: 6 }}>
          {violations.length === 0
            ? "No breaches today. The indicator in the header stays green while this holds."
            : `${breached} hard and ${violations.length - breached} soft. Hard breaches are the ones that end a session.`}
        </p>
      </motion.div>

      <motion.div className="stack" variants={stagger}>
        {rules.map((rule) => {
          const violation = byRule.get(rule.id);
          const violated = Boolean(violation);

          return (
            // Deliberately no `layout`: these cards never reorder, and layout
            // projection measures against a parent that is still transformed
            // during a route transition.
            <motion.div
              key={rule.id}
              variants={riseIn}
              transition={spring}
              className={[
                "rule",
                violated ? "violated" : "",
                violated && violation!.severity === "soft" ? "soft" : "",
              ]
                .filter(Boolean)
                .join(" ")}
              style={{ opacity: rule.enabled ? 1 : 0.5 }}
            >
              <motion.div
                className="check"
                style={
                  violated
                    ? {
                        background: "rgba(248,113,113,0.16)",
                        color: "#f87171",
                      }
                    : undefined
                }
                animate={
                  violated
                    ? { scale: [1, 1.12, 1] }
                    : { scale: 1 }
                }
                transition={
                  violated
                    ? { duration: 1.6, repeat: Infinity, ease: "easeInOut" }
                    : spring
                }
              >
                {violated ? <AlertIcon size={11} /> : <CheckIcon size={11} />}
              </motion.div>

              <div className="rule-body">
                <div className="between">
                  <span className="rule-label">{rule.label}</span>

                  <span className={`tag ${rule.severity}`}>
                    {rule.severity}
                  </span>
                </div>

                <div className="rule-detail">{rule.detail}</div>

                <AnimatePresence>
                  {violation && (
                    <motion.div
                      className="rule-breach"
                      initial={{ opacity: 0, height: 0, marginTop: 0 }}
                      animate={{ opacity: 1, height: "auto", marginTop: 8 }}
                      exit={{ opacity: 0, height: 0, marginTop: 0 }}
                      transition={spring}
                    >
                      {violation.message}

                      <div
                        style={{
                          marginTop: 7,
                          height: 3,
                          borderRadius: 99,
                          background: "rgba(255,255,255,0.08)",
                          overflow: "hidden",
                        }}
                      >
                        <motion.div
                          initial={{ width: 0 }}
                          animate={{
                            width: `${20 + violation.overage * 80}%`,
                          }}
                          transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
                          style={{
                            height: "100%",
                            background:
                              violation.severity === "hard"
                                ? "#f87171"
                                : "#fbbf24",
                          }}
                        />
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>

              <Toggle
                on={rule.enabled}
                label={`Enable rule: ${rule.label}`}
                onChange={(next) => onToggle(rule.id, next)}
              />
            </motion.div>
          );
        })}
      </motion.div>
    </motion.div>
  );
}
