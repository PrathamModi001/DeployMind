"use client";

import { Card } from '@/components/ui/card';
import { motion, AnimatePresence } from 'framer-motion';
import { Check } from 'lucide-react';
import { cn } from '@/lib/utils';

interface WizardStep {
  id: string;
  title: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
}

interface WizardContainerProps {
  steps: WizardStep[];
  currentStep: number;
  children: React.ReactNode;
}

export function WizardContainer({ steps, currentStep, children }: WizardContainerProps) {
  return (
    <div className="space-y-6">
      {/* Progress Steps */}
      <Card className="p-6 border border-border/50 bg-gradient-to-br from-card to-muted/20">
        <div className="flex items-center justify-between">
          {steps.map((step, index) => {
            const StepIcon = step.icon;
            const isCompleted = index < currentStep;
            const isCurrent = index === currentStep;
            const isUpcoming = index > currentStep;

            return (
              <div key={step.id} className="flex items-center flex-1">
                {/* Step Circle */}
                <div className="flex flex-col items-center">
                  <motion.div
                    className={cn(
                      "w-12 h-12 rounded-full flex items-center justify-center border-2 transition-all",
                      isCompleted && "bg-primary border-primary",
                      isCurrent && "bg-primary/20 border-primary animate-pulse",
                      isUpcoming && "bg-muted border-border"
                    )}
                    initial={{ scale: 0.8, opacity: 0 }}
                    animate={{ scale: 1, opacity: 1 }}
                    transition={{ delay: index * 0.1 }}
                  >
                    {isCompleted ? (
                      <Check className="w-6 h-6 text-primary-foreground" />
                    ) : (
                      <StepIcon
                        className={cn(
                          "w-6 h-6",
                          isCurrent && "text-primary",
                          isUpcoming && "text-muted-foreground"
                        )}
                      />
                    )}
                  </motion.div>

                  {/* Step Info */}
                  <div className="mt-2 text-center min-w-[100px]">
                    <p
                      className={cn(
                        "text-sm font-medium",
                        isCurrent && "text-foreground",
                        !isCurrent && "text-muted-foreground"
                      )}
                    >
                      {step.title}
                    </p>
                    <p className="text-xs text-muted-foreground mt-0.5 hidden sm:block">
                      {step.description}
                    </p>
                  </div>
                </div>

                {/* Connector Line */}
                {index < steps.length - 1 && (
                  <div className="flex-1 h-0.5 mx-4 relative">
                    <div className="absolute inset-0 bg-border" />
                    <motion.div
                      className="absolute inset-0 bg-primary"
                      initial={{ scaleX: 0 }}
                      animate={{ scaleX: isCompleted ? 1 : 0 }}
                      transition={{ duration: 0.3 }}
                      style={{ transformOrigin: 'left' }}
                    />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </Card>

      {/* Content Area */}
      <AnimatePresence mode="wait">
        <motion.div
          key={currentStep}
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -20 }}
          transition={{ duration: 0.2 }}
        >
          {children}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
