"use client";

import { useQuery } from '@tanstack/react-query';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Shield, Sparkles, AlertTriangle, Info } from 'lucide-react';
import { WizardStep } from '../wizard-step';
import { api } from '@/lib/api';
import { Card } from '@/components/ui/card';
import { cn } from '@/lib/utils';

interface StrategyStepProps {
  data: {
    strategy: string;
  };
  onChange: (data: any) => void;
  onNext: () => void;
  onBack: () => void;
}

const STRATEGIES = [
  {
    id: 'rolling',
    name: 'Rolling Update',
    description: 'Gradually replace instances one by one. Zero downtime, safe rollback.',
    risk: 'low',
    duration: 'Medium',
    icon: Shield,
    features: ['Zero downtime', 'Automatic rollback', 'Health checks', 'Safe for production'],
  },
  {
    id: 'blue_green',
    name: 'Blue/Green',
    description: 'Deploy to new environment, switch traffic when ready. Instant rollback.',
    risk: 'low',
    duration: 'Fast',
    icon: Shield,
    features: ['Instant rollback', 'Full testing before switch', '2x resources needed', 'Best for critical apps'],
  },
  {
    id: 'canary',
    name: 'Canary',
    description: 'Gradually shift traffic to new version. Test with small user percentage first.',
    risk: 'very-low',
    duration: 'Slow',
    icon: Shield,
    features: ['Gradual traffic shift', 'Early issue detection', 'A/B testing', 'Complex setup'],
  },
];

export function StrategyStep({ data, onChange, onNext, onBack }: StrategyStepProps) {
  // Get AI recommendation
  const { data: aiRecommendation } = useQuery({
    queryKey: ['strategy-recommendation'],
    queryFn: async () => {
      const response = await api.ai.recommendStrategy({
        current_status: 'deployed',
        deployment_count: 50,
        success_rate: 95.5,
      });
      return response.data;
    },
  });

  const isValid = data.strategy.length > 0;

  const getRiskColor = (risk: string) => {
    switch (risk) {
      case 'very-low':
        return 'text-green-400 bg-green-500/10 border-green-500/20';
      case 'low':
        return 'text-blue-400 bg-blue-500/10 border-blue-500/20';
      case 'medium':
        return 'text-yellow-400 bg-yellow-500/10 border-yellow-500/20';
      default:
        return 'text-red-400 bg-red-500/10 border-red-500/20';
    }
  };

  return (
    <WizardStep
      title="Deployment Strategy"
      description="Choose how your application will be deployed"
      onNext={onNext}
      onBack={onBack}
      isNextDisabled={!isValid}
    >
      {/* AI Recommendation */}
      {aiRecommendation && (
        <Card className="p-4 bg-gradient-to-br from-purple-500/10 to-transparent border-purple-500/20">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-lg bg-purple-500/20 flex items-center justify-center flex-shrink-0">
              <Sparkles className="w-5 h-5 text-purple-400" />
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <h4 className="font-semibold text-sm">AI Recommendation</h4>
                <Badge variant="outline" className="bg-purple-500/10 border-purple-500/20 text-purple-400 uppercase">
                  {aiRecommendation.recommended_strategy}
                </Badge>
              </div>
              <p className="text-sm text-muted-foreground mb-2">
                {aiRecommendation.reasoning}
              </p>
              <div className="flex items-center gap-2 text-xs">
                <Info className="w-3 h-3 text-muted-foreground" />
                <span className="text-muted-foreground">
                  Risk Level: <span className="font-medium text-foreground">{aiRecommendation.risk_level}</span>
                </span>
              </div>
            </div>
          </div>
        </Card>
      )}

      {/* Strategy Selection */}
      <div className="space-y-3">
        <Label>Select Deployment Strategy</Label>
        <div className="grid gap-3">
          {STRATEGIES.map((strategy) => {
            const StrategyIcon = strategy.icon;
            const isRecommended = strategy.id === aiRecommendation?.recommended_strategy;
            const isSelected = data.strategy === strategy.id;

            return (
              <div
                key={strategy.id}
                className={cn(
                  "p-4 rounded-lg border-2 cursor-pointer transition-all hover:border-primary/50",
                  isSelected && "border-primary bg-primary/5",
                  !isSelected && "border-border bg-card",
                  isRecommended && !isSelected && "border-purple-500/30 bg-purple-500/5"
                )}
                onClick={() => onChange({ ...data, strategy: strategy.id })}
              >
                <div className="space-y-3">
                  {/* Header */}
                  <div className="flex items-start justify-between">
                    <div className="flex items-start gap-3">
                      <div className={cn(
                        "w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0",
                        isSelected ? "bg-primary/20" : "bg-muted"
                      )}>
                        <StrategyIcon className={cn(
                          "w-5 h-5",
                          isSelected ? "text-primary" : "text-muted-foreground"
                        )} />
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <h4 className="font-semibold">{strategy.name}</h4>
                          {isRecommended && (
                            <Badge variant="outline" className="bg-purple-500/10 border-purple-500/20 text-purple-400">
                              Recommended
                            </Badge>
                          )}
                        </div>
                        <p className="text-sm text-muted-foreground mt-1">
                          {strategy.description}
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* Metrics */}
                  <div className="flex items-center gap-4 text-xs">
                    <Badge variant="outline" className={getRiskColor(strategy.risk)}>
                      {strategy.risk.toUpperCase()} RISK
                    </Badge>
                    <span className="text-muted-foreground">Duration: {strategy.duration}</span>
                  </div>

                  {/* Features */}
                  <div className="grid grid-cols-2 gap-2">
                    {strategy.features.map((feature, idx) => (
                      <div key={idx} className="flex items-center gap-2 text-xs text-muted-foreground">
                        <div className="w-1.5 h-1.5 rounded-full bg-primary" />
                        {feature}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Info Box */}
      <Card className="p-4 bg-blue-500/10 border-blue-500/20">
        <div className="flex items-start gap-2">
          <Info className="w-4 h-4 text-blue-400 mt-0.5 flex-shrink-0" />
          <div className="text-sm text-blue-400">
            <p className="font-medium mb-1">Strategy Comparison</p>
            <p className="text-xs text-blue-300">
              <strong>Rolling:</strong> Best balance of safety and speed. <br />
              <strong>Blue/Green:</strong> Safest, but uses 2x resources temporarily. <br />
              <strong>Canary:</strong> Lowest risk, but slower rollout.
            </p>
          </div>
        </div>
      </Card>
    </WizardStep>
  );
}
