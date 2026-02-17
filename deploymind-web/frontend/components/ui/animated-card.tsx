"use client";

import { motion } from 'framer-motion';
import { Card } from './card';
import { forwardRef } from 'react';

export const AnimatedCard = forwardRef<
  HTMLDivElement,
  React.ComponentProps<typeof Card> & {
    delay?: number;
    hover?: boolean;
  }
>(({ children, className, delay = 0, hover = true, ...props }, ref) => {
  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{
        duration: 0.4,
        delay,
        ease: [0.4, 0, 0.2, 1],
      }}
      whileHover={hover ? {
        y: -4,
        transition: {
          duration: 0.2,
          ease: [0.4, 0, 0.2, 1],
        },
      } : undefined}
    >
      <Card className={className} {...props}>
        {children}
      </Card>
    </motion.div>
  );
});

AnimatedCard.displayName = "AnimatedCard";
