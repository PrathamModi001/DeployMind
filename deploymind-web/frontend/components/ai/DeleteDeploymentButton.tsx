"use client";

import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
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
import { Trash2, Loader2, AlertTriangle } from 'lucide-react';

interface DeleteDeploymentButtonProps {
  deploymentId: string;
  deploymentName?: string;
  variant?: 'default' | 'destructive' | 'outline' | 'secondary' | 'ghost' | 'link';
  size?: 'default' | 'sm' | 'lg' | 'icon';
  showIcon?: boolean;
  onDeleteSuccess?: () => void;
}

export function DeleteDeploymentButton({
  deploymentId,
  deploymentName,
  variant = 'destructive',
  size = 'default',
  showIcon = true,
  onDeleteSuccess,
}: DeleteDeploymentButtonProps) {
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const router = useRouter();

  // Delete deployment mutation
  const deleteMutation = useMutation({
    mutationFn: async () => {
      return api.deployments.delete(deploymentId);
    },
    onSuccess: () => {
      // Invalidate deployment queries
      queryClient.invalidateQueries({ queryKey: ['deployments-list'] });
      queryClient.invalidateQueries({ queryKey: ['deployment', deploymentId] });
      queryClient.invalidateQueries({ queryKey: ['analytics-overview'] });

      // Close dialog
      setShowConfirmDialog(false);

      // Call success callback or redirect
      if (onDeleteSuccess) {
        onDeleteSuccess();
      } else {
        // Redirect to deployments list
        router.push('/dashboard/deployments');
      }
    },
    onError: (error: any) => {
      setError(error.response?.data?.detail || error.message || 'Failed to delete deployment');
    },
  });

  const handleDelete = () => {
    setError(null);
    deleteMutation.mutate();
  };

  return (
    <>
      <Button
        variant={variant}
        size={size}
        onClick={() => setShowConfirmDialog(true)}
        disabled={deleteMutation.isPending}
      >
        {showIcon && <Trash2 className="mr-2 h-4 w-4" />}
        Delete Deployment
      </Button>

      {/* Confirmation Dialog */}
      <Dialog open={showConfirmDialog} onOpenChange={setShowConfirmDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-red-500">
              <AlertTriangle className="h-5 w-5" />
              Delete Deployment
            </DialogTitle>
            <DialogDescription>
              This action cannot be undone.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <Alert variant="destructive">
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>
                <strong>WARNING:</strong> You are about to permanently delete this deployment.
              </AlertDescription>
            </Alert>

            <div className="space-y-2">
              <p className="text-sm font-medium">This will delete:</p>
              <ul className="text-sm text-muted-foreground list-disc list-inside space-y-1">
                <li>Deployment record and configuration</li>
                <li>All security scan results</li>
                <li>Build results and Docker images</li>
                <li>Health check history</li>
                <li>Deployment logs and events</li>
                <li>AI agent execution records</li>
              </ul>
            </div>

            {deploymentName && (
              <div className="p-3 rounded-lg bg-muted border">
                <p className="text-xs text-muted-foreground mb-1">Deployment:</p>
                <p className="font-mono text-sm font-semibold">{deploymentName}</p>
                <p className="text-xs text-muted-foreground mt-1">ID: {deploymentId}</p>
              </div>
            )}

            <p className="text-sm text-muted-foreground">
              Are you absolutely sure you want to proceed?
            </p>

            {/* Error Display */}
            {error && (
              <Alert variant="destructive">
                <AlertTriangle className="h-4 w-4" />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
          </div>

          <DialogFooter className="gap-2">
            <Button
              variant="outline"
              onClick={() => {
                setShowConfirmDialog(false);
                setError(null);
              }}
              disabled={deleteMutation.isPending}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              {deleteMutation.isPending ? 'Deleting...' : 'Delete Permanently'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
