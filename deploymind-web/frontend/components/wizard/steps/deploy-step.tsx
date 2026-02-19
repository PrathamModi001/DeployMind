"use client";

import { useEffect, useState } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import {
  CheckCircle2, Circle, Loader2, XCircle, ArrowRight,
  Shield, Hammer, Rocket, Activity
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useRouter } from 'next/navigation';

interface DeployStepProps {
  deploymentId: string;
  status: string;
  onViewDetails: () => void;
}

interface DeploymentPhase {
  id: string;
  name: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
  status: 'pending' | 'in_progress' | 'completed' | 'failed';
  duration?: number;
}

export function DeployStep({ deploymentId, status, onViewDetails }: DeployStepProps) {
  const router = useRouter();
  const [phases, setPhases] = useState<DeploymentPhase[]>([
    {
      id: 'security',
      name: 'Security Scan',
      description: 'Scanning for vulnerabilities',
      icon: Shield,
      status: 'pending',
    },
    {
      id: 'build',
      name: 'Building',
      description: 'Building Docker image',
      icon: Hammer,
      status: 'pending',
    },
    {
      id: 'deploy',
      name: 'Deploying',
      description: 'Deploying to instance',
      icon: Rocket,
      status: 'pending',
    },
    {
      id: 'health',
      name: 'Health Check',
      description: 'Verifying application health',
      icon: Activity,
      status: 'pending',
    },
  ]);

  // Simulate deployment progress (in real app, this would come from websocket/polling)
  useEffect(() => {
    const updatePhases = () => {
      const statusMap: { [key: string]: number } = {
        'pending': 0,
        'security_scanning': 1,
        'security_failed': 1,
        'building': 2,
        'build_failed': 2,
        'deploying': 3,
        'deployed': 4,
        'failed': 4,
      };

      const currentPhaseIndex = statusMap[status] || 0;

      setPhases(prevPhases =>
        prevPhases.map((phase, index) => {
          if (index < currentPhaseIndex) {
            return { ...phase, status: 'completed' };
          } else if (index === currentPhaseIndex) {
            if (status.includes('failed')) {
              return { ...phase, status: 'failed' };
            }
            return { ...phase, status: 'in_progress' };
          }
          return phase;
        })
      );
    };

    updatePhases();
  }, [status]);

  const progress = (phases.filter(p => p.status === 'completed').length / phases.length) * 100;
  const isCompleted = status === 'deployed';
  const isFailed = status.includes('failed');
  const isInProgress = !isCompleted && !isFailed;

  return (
    <Card className="relative overflow-hidden border border-border/50">
      {/* Gradient background */}
      <div className="absolute inset-0 bg-gradient-to-br from-primary/5 to-transparent" />

      <div className="relative p-6 space-y-6">
        {/* Header */}
        <div className="space-y-1">
          <div className="flex items-center justify-between">
            <h3 className="text-2xl font-semibold">
              {isCompleted && '🎉 Deployment Successful!'}
              {isFailed && '❌ Deployment Failed'}
              {isInProgress && '🚀 Deploying...'}
            </h3>
            <Badge
              variant="outline"
              className={cn(
                isCompleted && 'bg-green-500/10 border-green-500/20 text-green-400',
                isFailed && 'bg-red-500/10 border-red-500/20 text-red-400',
                isInProgress && 'bg-blue-500/10 border-blue-500/20 text-blue-400'
              )}
            >
              {status.toUpperCase().replace('_', ' ')}
            </Badge>
          </div>
          <p className="text-sm text-muted-foreground">
            Deployment ID: <span className="font-mono">{deploymentId}</span>
          </p>
        </div>

        {/* Progress Bar */}
        {isInProgress && (
          <div className="space-y-2">
            <Progress value={progress} className="h-2" />
            <p className="text-xs text-muted-foreground text-center">
              {Math.round(progress)}% Complete
            </p>
          </div>
        )}

        {/* Deployment Phases */}
        <div className="space-y-3">
          {phases.map((phase, index) => {
            const PhaseIcon = phase.icon;
            const isPending = phase.status === 'pending';
            const isInProgress = phase.status === 'in_progress';
            const isCompleted = phase.status === 'completed';
            const isFailed = phase.status === 'failed';

            return (
              <div
                key={phase.id}
                className={cn(
                  "p-4 rounded-lg border transition-all",
                  isCompleted && "border-green-500/30 bg-green-500/5",
                  isInProgress && "border-primary bg-primary/5 animate-pulse",
                  isFailed && "border-red-500/30 bg-red-500/5",
                  isPending && "border-border bg-muted/20"
                )}
              >
                <div className="flex items-center gap-3">
                  {/* Status Icon */}
                  <div
                    className={cn(
                      "w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0",
                      isCompleted && "bg-green-500/20",
                      isInProgress && "bg-primary/20",
                      isFailed && "bg-red-500/20",
                      isPending && "bg-muted"
                    )}
                  >
                    {isCompleted && <CheckCircle2 className="w-5 h-5 text-green-400" />}
                    {isInProgress && <Loader2 className="w-5 h-5 text-primary animate-spin" />}
                    {isFailed && <XCircle className="w-5 h-5 text-red-400" />}
                    {isPending && <Circle className="w-5 h-5 text-muted-foreground" />}
                  </div>

                  {/* Phase Info */}
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <PhaseIcon className="w-4 h-4 text-muted-foreground" />
                      <p className="font-medium">{phase.name}</p>
                    </div>
                    <p className="text-sm text-muted-foreground mt-0.5">
                      {phase.description}
                    </p>
                  </div>

                  {/* Duration */}
                  {phase.duration && (
                    <span className="text-xs text-muted-foreground">
                      {phase.duration}s
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Success Message */}
        {isCompleted && (
          <Card className="p-4 bg-green-500/10 border-green-500/20">
            <div className="text-sm text-green-400">
              <p className="font-medium mb-1">Deployment Complete!</p>
              <p className="text-xs text-green-300">
                Your application has been successfully deployed and is now running. All health
                checks passed.
              </p>
            </div>
          </Card>
        )}

        {/* Error Message */}
        {isFailed && (
          <Card className="p-4 bg-red-500/10 border-red-500/20">
            <div className="text-sm text-red-400">
              <p className="font-medium mb-1">Deployment Failed</p>
              <p className="text-xs text-red-300">
                The deployment encountered an error. Check the deployment logs for more details.
                {status === 'security_failed' && ' Security scan detected critical vulnerabilities.'}
                {status === 'build_failed' && ' Build process failed.'}
              </p>
            </div>
          </Card>
        )}

        {/* Actions */}
        <div className="flex gap-3 pt-4 border-t border-border/50">
          <Button
            onClick={onViewDetails}
            className="gap-2 bg-gradient-to-r from-primary to-primary/80 hover:from-primary/90 hover:to-primary/70"
          >
            View Details
            <ArrowRight className="w-4 h-4" />
          </Button>

          {(isCompleted || isFailed) && (
            <Button
              variant="outline"
              onClick={() => router.push('/dashboard/deployments')}
            >
              Back to Deployments
            </Button>
          )}
        </div>
      </div>
    </Card>
  );
}
