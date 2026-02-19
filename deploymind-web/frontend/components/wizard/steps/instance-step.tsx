"use client";

import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Server, Cpu, HardDrive, Sparkles, Loader2, DollarSign } from 'lucide-react';
import { WizardStep } from '../wizard-step';
import { api } from '@/lib/api';
import { Card } from '@/components/ui/card';
import { cn } from '@/lib/utils';

interface InstanceStepProps {
  data: {
    instance_id: string;
    instance_type?: string;
    region?: string;
  };
  repositoryData: {
    repository: string;
    branch: string;
  };
  onChange: (data: any) => void;
  onNext: () => void;
  onBack: () => void;
}

const INSTANCE_TYPES = [
  { type: 't2.micro', cpu: '1 vCPU', memory: '1 GB', cost: '$8.47/mo', recommended: false },
  { type: 't2.small', cpu: '1 vCPU', memory: '2 GB', cost: '$16.79/mo', recommended: false },
  { type: 't2.medium', cpu: '2 vCPU', memory: '4 GB', cost: '$33.58/mo', recommended: true },
  { type: 't3.small', cpu: '2 vCPU', memory: '2 GB', cost: '$15.18/mo', recommended: false },
  { type: 't3.medium', cpu: '2 vCPU', memory: '4 GB', cost: '$30.37/mo', recommended: false },
];

export function InstanceStep({ data, repositoryData, onChange, onNext, onBack }: InstanceStepProps) {
  const [showManual, setShowManual] = useState(!!data.instance_id);

  // Get AI recommendation
  const { data: aiRecommendation, isLoading: isLoadingAI } = useQuery({
    queryKey: ['instance-recommendation', repositoryData.repository],
    queryFn: async () => {
      const response = await api.ai.recommendInstance({
        repository: repositoryData.repository,
        language: 'python', // Could be detected from repo
        traffic_estimate: 'medium',
      });
      return response.data;
    },
    enabled: !!repositoryData.repository,
  });

  const isValid = data.instance_id.length > 0 || data.instance_type !== undefined;

  return (
    <WizardStep
      title="Configure Instance"
      description="Select or create an EC2 instance for deployment"
      onNext={onNext}
      onBack={onBack}
      isNextDisabled={!isValid}
    >
      {/* AI Recommendation Card */}
      {aiRecommendation && !showManual && (
        <Card className="p-4 bg-gradient-to-br from-purple-500/10 to-transparent border-purple-500/20">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-lg bg-purple-500/20 flex items-center justify-center flex-shrink-0">
              <Sparkles className="w-5 h-5 text-purple-400" />
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <h4 className="font-semibold text-sm">AI Recommendation</h4>
                <Badge variant="outline" className="bg-purple-500/10 border-purple-500/20 text-purple-400">
                  Recommended
                </Badge>
              </div>
              <p className="text-sm text-muted-foreground mb-3">
                {aiRecommendation.reasoning}
              </p>
              <div className="flex items-center gap-4 text-sm">
                <span className="font-mono font-semibold text-purple-400">
                  {aiRecommendation.recommended_instance}
                </span>
                <span className="text-muted-foreground">
                  ${aiRecommendation.estimated_cost_monthly_usd}/month
                </span>
              </div>
            </div>
          </div>
        </Card>
      )}

      {/* Instance Type Selection */}
      <div className="space-y-3">
        <Label>Choose Instance Type</Label>
        <div className="grid gap-3">
          {INSTANCE_TYPES.map((instance) => {
            const isRecommended =
              instance.type === aiRecommendation?.recommended_instance || instance.recommended;
            const isSelected = data.instance_type === instance.type;

            return (
              <div
                key={instance.type}
                className={cn(
                  "p-4 rounded-lg border-2 cursor-pointer transition-all hover:border-primary/50",
                  isSelected && "border-primary bg-primary/5",
                  !isSelected && "border-border bg-card",
                  isRecommended && !isSelected && "border-purple-500/30 bg-purple-500/5"
                )}
                onClick={() => {
                  onChange({ ...data, instance_type: instance.type, instance_id: '' });
                  setShowManual(false);
                }}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className={cn(
                      "w-10 h-10 rounded-lg flex items-center justify-center",
                      isSelected ? "bg-primary/20" : "bg-muted"
                    )}>
                      <Server className={cn(
                        "w-5 h-5",
                        isSelected ? "text-primary" : "text-muted-foreground"
                      )} />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <p className="font-mono font-semibold">{instance.type}</p>
                        {isRecommended && (
                          <Badge variant="outline" className="bg-purple-500/10 border-purple-500/20 text-purple-400">
                            Recommended
                          </Badge>
                        )}
                      </div>
                      <div className="flex items-center gap-4 text-xs text-muted-foreground mt-1">
                        <span className="flex items-center gap-1">
                          <Cpu className="w-3 h-3" />
                          {instance.cpu}
                        </span>
                        <span className="flex items-center gap-1">
                          <HardDrive className="w-3 h-3" />
                          {instance.memory}
                        </span>
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <DollarSign className="w-4 h-4 text-muted-foreground" />
                    <span className="font-semibold">{instance.cost}</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Divider */}
      <div className="relative">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t border-border"></div>
        </div>
        <div className="relative flex justify-center text-xs uppercase">
          <span className="bg-card px-2 text-muted-foreground">Or</span>
        </div>
      </div>

      {/* Manual Instance ID */}
      <div className="space-y-2">
        <Label htmlFor="instance_id">Use Existing Instance ID</Label>
        <Input
          id="instance_id"
          placeholder="i-1234567890abcdef0"
          value={data.instance_id}
          onChange={(e) => {
            onChange({ ...data, instance_id: e.target.value, instance_type: undefined });
            setShowManual(true);
          }}
          className="font-mono"
        />
        <p className="text-xs text-muted-foreground">
          Enter an existing EC2 instance ID to use for deployment
        </p>
      </div>

      {/* Region Selection */}
      <div className="space-y-2">
        <Label htmlFor="region">AWS Region</Label>
        <select
          id="region"
          value={data.region || 'us-east-1'}
          onChange={(e) => onChange({ ...data, region: e.target.value })}
          className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <option value="us-east-1">US East (N. Virginia)</option>
          <option value="us-west-2">US West (Oregon)</option>
          <option value="eu-west-1">EU (Ireland)</option>
          <option value="ap-southeast-1">Asia Pacific (Singapore)</option>
        </select>
      </div>
    </WizardStep>
  );
}
