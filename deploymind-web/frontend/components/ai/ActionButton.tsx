"use client";

import { useState, useEffect } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { api } from '@/lib/api';
import { Loader2, CheckCircle2, XCircle, AlertTriangle } from 'lucide-react';

interface ActionableRecommendation {
  id: string;
  action_type: 'scale_instance' | 'stop_idle_deployments' | 'trigger_security_scan';
  title: string;
  description: string;
  parameters: Record<string, any>;
  impact: {
    cost_change_monthly?: number;
    downtime_minutes?: number;
    savings_monthly?: number;
    deployments_affected?: number;
    performance_improvement_percent?: number;
  };
  requires_confirmation: boolean;
  confirmation_message: string;
  confidence: string;
  estimated_duration_minutes: number;
  can_undo: boolean;
}

interface ActionButtonProps {
  recommendation: ActionableRecommendation;
  onSuccess?: () => void;
}

type ExecutionStatus = 'idle' | 'confirming' | 'executing' | 'polling' | 'completed' | 'failed';

export function ActionButton({ recommendation, onSuccess }: ActionButtonProps) {
  const [status, setStatus] = useState<ExecutionStatus>('idle');
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);
  const [executionId, setExecutionId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const queryClient = useQueryClient();

  // Execute action mutation
  const executeMutation = useMutation({
    mutationFn: async (confirmed: boolean) => {
      const requestData = {
        recommendation_id: recommendation.id,
        parameters: recommendation.parameters,
        confirmed,
      };

      // Route to correct endpoint based on action type
      switch (recommendation.action_type) {
        case 'scale_instance':
          return api.aiActions.executeScaleInstance(requestData);
        case 'stop_idle_deployments':
          return api.aiActions.executeStopIdleDeployments(requestData);
        case 'trigger_security_scan':
          return api.aiActions.executeTriggerSecurityScan(requestData);
        default:
          throw new Error(`Unknown action type: ${recommendation.action_type}`);
      }
    },
    onSuccess: (response) => {
      const execId = response.data.execution_id;
      setExecutionId(execId);
      setStatus('polling');
      // Start polling
      pollStatus(execId);
    },
    onError: (error: any) => {
      setStatus('failed');
      setErrorMessage(error.response?.data?.detail || error.message || 'Action execution failed');
    },
  });

  // Poll execution status
  const pollStatus = async (execId: string) => {
    const pollInterval = setInterval(async () => {
      try {
        const response = await api.aiActions.getExecutionStatus(execId);
        const statusData = response.data;

        setProgress(statusData.progress_percent || 0);

        if (statusData.status === 'completed') {
          clearInterval(pollInterval);
          setStatus('completed');
          setProgress(100);

          // Invalidate relevant queries
          queryClient.invalidateQueries({ queryKey: ['analytics-overview'] });
          queryClient.invalidateQueries({ queryKey: ['ai-cost-analysis'] });
          queryClient.invalidateQueries({ queryKey: ['ai-instance-recommendation'] });
          queryClient.invalidateQueries({ queryKey: ['ai-security-risk'] });

          // Call success callback
          if (onSuccess) {
            setTimeout(onSuccess, 1500);
          }
        } else if (statusData.status === 'failed') {
          clearInterval(pollInterval);
          setStatus('failed');
          setErrorMessage(statusData.error_message || 'Action execution failed');
        }
      } catch (error: any) {
        clearInterval(pollInterval);
        setStatus('failed');
        setErrorMessage(error.response?.data?.detail || 'Failed to poll status');
      }
    }, 2000); // Poll every 2 seconds

    // Timeout after 10 minutes
    setTimeout(() => {
      clearInterval(pollInterval);
      if (status === 'polling') {
        setStatus('failed');
        setErrorMessage('Action execution timed out');
      }
    }, 600000);
  };

  const handleApply = () => {
    if (recommendation.requires_confirmation) {
      setShowConfirmDialog(true);
      setStatus('confirming');
    } else {
      setStatus('executing');
      executeMutation.mutate(false);
    }
  };

  const handleConfirm = () => {
    setShowConfirmDialog(false);
    setStatus('executing');
    executeMutation.mutate(true);
  };

  const handleCancel = () => {
    setShowConfirmDialog(false);
    setStatus('idle');
  };

  // Reset to idle after successful completion
  useEffect(() => {
    if (status === 'completed') {
      const timer = setTimeout(() => {
        setStatus('idle');
        setExecutionId(null);
        setProgress(0);
      }, 3000);
      return () => clearTimeout(timer);
    }
  }, [status]);

  // Button content based on status
  const getButtonContent = () => {
    switch (status) {
      case 'idle':
        return 'Apply';
      case 'confirming':
        return 'Apply';
      case 'executing':
      case 'polling':
        return (
          <>
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Applying... {progress}%
          </>
        );
      case 'completed':
        return (
          <>
            <CheckCircle2 className="mr-2 h-4 w-4" />
            Applied ✓
          </>
        );
      case 'failed':
        return (
          <>
            <XCircle className="mr-2 h-4 w-4" />
            Failed
          </>
        );
    }
  };

  const isDisabled = status === 'executing' || status === 'polling' || status === 'completed';

  return (
    <>
      <Button
        onClick={handleApply}
        disabled={isDisabled}
        variant={status === 'completed' ? 'default' : status === 'failed' ? 'destructive' : 'default'}
        size="sm"
        className="min-w-[120px]"
      >
        {getButtonContent()}
      </Button>

      {/* Confirmation Dialog */}
      {recommendation.requires_confirmation && (
        <Dialog open={showConfirmDialog} onOpenChange={setShowConfirmDialog}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Confirm Action</DialogTitle>
              <DialogDescription>
                {recommendation.title}
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4">
              <p className="text-sm text-muted-foreground">
                {recommendation.description}
              </p>

              {/* Impact Details */}
              <div className="rounded-lg border p-4 space-y-2">
                <h4 className="font-medium text-sm">Impact:</h4>
                {recommendation.impact.cost_change_monthly !== undefined && (
                  <div className="text-sm flex justify-between">
                    <span>Monthly Cost Change:</span>
                    <span className={recommendation.impact.cost_change_monthly > 0 ? 'text-red-500' : 'text-green-500'}>
                      {recommendation.impact.cost_change_monthly > 0 ? '+' : ''}
                      ${Math.abs(recommendation.impact.cost_change_monthly).toFixed(2)}/mo
                    </span>
                  </div>
                )}
                {recommendation.impact.savings_monthly !== undefined && (
                  <div className="text-sm flex justify-between">
                    <span>Monthly Savings:</span>
                    <span className="text-green-500">
                      ${recommendation.impact.savings_monthly.toFixed(2)}/mo
                    </span>
                  </div>
                )}
                {recommendation.impact.downtime_minutes !== undefined && (
                  <div className="text-sm flex justify-between">
                    <span>Expected Downtime:</span>
                    <span className="text-yellow-500">
                      ~{recommendation.impact.downtime_minutes} minutes
                    </span>
                  </div>
                )}
                {recommendation.impact.deployments_affected !== undefined && (
                  <div className="text-sm flex justify-between">
                    <span>Deployments Affected:</span>
                    <span>{recommendation.impact.deployments_affected}</span>
                  </div>
                )}
                {recommendation.impact.performance_improvement_percent !== undefined && (
                  <div className="text-sm flex justify-between">
                    <span>Performance Improvement:</span>
                    <span className="text-green-500">
                      +{recommendation.impact.performance_improvement_percent}%
                    </span>
                  </div>
                )}
              </div>

              {/* Warning Message */}
              {recommendation.confirmation_message && (
                <Alert>
                  <AlertTriangle className="h-4 w-4" />
                  <AlertDescription>
                    {recommendation.confirmation_message}
                  </AlertDescription>
                </Alert>
              )}

              {/* Duration Estimate */}
              <p className="text-xs text-muted-foreground">
                Estimated duration: ~{recommendation.estimated_duration_minutes} minutes
              </p>
            </div>

            <DialogFooter>
              <Button variant="outline" onClick={handleCancel}>
                Cancel
              </Button>
              <Button onClick={handleConfirm}>
                Confirm
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}

      {/* Error Alert */}
      {status === 'failed' && errorMessage && (
        <Alert variant="destructive" className="mt-2">
          <XCircle className="h-4 w-4" />
          <AlertDescription>{errorMessage}</AlertDescription>
        </Alert>
      )}
    </>
  );
}
