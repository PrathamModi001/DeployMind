"use client";

import { useEffect, useState } from 'react';
import { motion, useSpring, useTransform } from 'framer-motion';

export function AnimatedStat({
  value,
  duration = 1.5
}: {
  value: number;
  duration?: number;
}) {
  const [mounted, setMounted] = useState(false);

  const spring = useSpring(0, {
    duration: duration * 1000,
    bounce: 0
  });

  const display = useTransform(spring, (current) =>
    Math.round(current).toLocaleString()
  );

  useEffect(() => {
    setMounted(true);
    spring.set(value);
  }, [spring, value]);

  if (!mounted) return <span>0</span>;

  return <motion.span>{display}</motion.span>;
}
