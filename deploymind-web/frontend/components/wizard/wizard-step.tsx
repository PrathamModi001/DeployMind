"use client";

import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { ArrowLeft, ArrowRight, Loader2 } from 'lucide-react';

interface WizardStepProps {
  title: string;
  description: string;
  children: React.ReactNode;
  onNext?: () => void;
  onBack?: () => void;
  nextLabel?: string;
  backLabel?: string;
  isNextDisabled?: boolean;
  isLoading?: boolean;
  showBack?: boolean;
  showNext?: boolean;
}

export function WizardStep({
  title,
  description,
  children,
  onNext,
  onBack,
  nextLabel = 'Continue',
  backLabel = 'Back',
  isNextDisabled = false,
  isLoading = false,
  showBack = true,
  showNext = true,
}: WizardStepProps) {
  return (
    <Card className="relative overflow-hidden border border-border/50">
      {/* Gradient background */}
      <div className="absolute inset-0 bg-gradient-to-br from-primary/5 to-transparent" />

      <div className="relative p-6 space-y-6">
        {/* Header */}
        <div className="space-y-1">
          <h3 className="text-2xl font-semibold">{title}</h3>
          <p className="text-sm text-muted-foreground">{description}</p>
        </div>

        {/* Content */}
        <div className="space-y-4">{children}</div>

        {/* Navigation */}
        <div className="flex gap-3 pt-4 border-t border-border/50">
          {showBack && onBack && (
            <Button
              type="button"
              variant="outline"
              onClick={onBack}
              disabled={isLoading}
              className="gap-2"
            >
              <ArrowLeft className="w-4 h-4" />
              {backLabel}
            </Button>
          )}

          {showNext && onNext && (
            <Button
              type="button"
              onClick={onNext}
              disabled={isNextDisabled || isLoading}
              className="gap-2 ml-auto bg-gradient-to-r from-primary to-primary/80 hover:from-primary/90 hover:to-primary/70"
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Processing...
                </>
              ) : (
                <>
                  {nextLabel}
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </Button>
          )}
        </div>
      </div>
    </Card>
  );
}
