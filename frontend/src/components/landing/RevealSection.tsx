import { memo, type ReactNode } from "react";
import { motion, useReducedMotion, type Variants } from "framer-motion";

const containerVariants: Variants = {
  hidden: {},
  visible: {
    transition: { staggerChildren: 0.12, delayChildren: 0.04 },
  },
};

const itemVariants: Variants = {
  hidden: { opacity: 0, y: 24 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: "easeOut" } },
};

/**
 * Wraps a page section so it fades/slides into view as the user scrolls to
 * it, staggering any `RevealItem` children. Uses framer-motion's
 * `whileInView` (IntersectionObserver under the hood) rather than a manual
 * observer. Falls back to a plain, unanimated container when the user
 * prefers reduced motion so content never waits on an animation that won't
 * play.
 */
export const RevealSection = memo(function RevealSection({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  const shouldReduceMotion = useReducedMotion();

  if (shouldReduceMotion) {
    return <div className={className}>{children}</div>;
  }

  return (
    <motion.div
      className={className}
      initial="hidden"
      whileInView="visible"
      viewport={{ once: true, margin: "-100px" }}
      variants={containerVariants}
    >
      {children}
    </motion.div>
  );
});

/** A single animated child within a `RevealSection`; only animates transform/opacity. */
export const RevealItem = memo(function RevealItem({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <motion.div className={className} variants={itemVariants}>
      {children}
    </motion.div>
  );
});
