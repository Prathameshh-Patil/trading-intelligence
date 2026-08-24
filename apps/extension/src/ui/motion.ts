import type { Transition, Variants } from "framer-motion";

/** Shared spring — snappy without overshooting into a bounce. */
export const spring: Transition = {
  type: "spring",
  stiffness: 420,
  damping: 34,
  mass: 0.8,
};

export const softSpring: Transition = {
  type: "spring",
  stiffness: 260,
  damping: 30,
};

/** Push/pop between views. `custom` is +1 forward, -1 back. */
export const viewVariants: Variants = {
  enter: (dir: number) => ({
    opacity: 0,
    x: dir > 0 ? 28 : -28,
    scale: 0.98,
  }),
  center: {
    opacity: 1,
    x: 0,
    scale: 1,
    transition: { ...spring, opacity: { duration: 0.18 } },
  },
  exit: (dir: number) => ({
    opacity: 0,
    x: dir > 0 ? -24 : 24,
    scale: 0.98,
    transition: { duration: 0.16, ease: [0.4, 0, 1, 1] },
  }),
};

/** Parent that reveals its children one after another. */
export const stagger: Variants = {
  hidden: { opacity: 1 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.055, delayChildren: 0.04 },
  },
};

export const riseIn: Variants = {
  hidden: { opacity: 0, y: 14 },
  show: { opacity: 1, y: 0, transition: spring },
};

export const fadeIn: Variants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { duration: 0.25 } },
};

export const pressable = {
  whileHover: { y: -2 },
  whileTap: { scale: 0.975, y: 0 },
  transition: spring,
} as const;
