"use client";

import { useQuery } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import {
  Rocket, Clock, GitBranch, Server, Activity,
  CheckCircle2, XCircle, Loader2, Plus
} from 'lucide-react';

// Gradient colors for deployments (Railway-style)
const deploymentGradients = [
  'from-purple-500/20 to-purple-600/5',
  'from-blue-500/20 to-blue-600/5',
  'from-pink-500/20 to-pink-600/5',
  'from-green-500/20 to-green-600/5',
  'from-orange-500/20 to-orange-600/5',
];

const statusConfig = {
  DEPLOYED: {
    color: 'text-green-400',
    bg: 'bg-green-500/10',
    border: 'border-green-500/20',
    icon: CheckCircle2,
    animate: ''
  },
  DEPLOYING: {
    color: 'text-blue-400',
    bg: 'bg-blue-500/10',
    border: 'border-blue-500/20',
    icon: Loader2,
    animate: 'animate-spin'
  },
  BUILDING: {
    color: 'text-purple-400',
    bg: 'bg-purple-500/10',
    border: 'border-purple-500/20',
    icon: Loader2,
    animate: 'animate-spin'
  },
  FAILED: {
    color: 'text-red-400',
    bg: 'bg-red-500/10',
    border: 'border-red-500/20',
    icon: XCircle,
    animate: ''
  },
  PENDING: {
    color: 'text-yellow-400',
    bg: 'bg-yellow-500/10',
    border: 'border-yellow-500/20',
    icon: Clock,
    animate: ''
  },
  ROLLED_BACK: {
    color: 'text-orange-400',
    bg: 'bg-orange-500/10',
    border: 'border-orange-500/20',
    icon: XCircle,
    animate: ''
  },
};

export default function DeploymentsPage() {
  const router = useRouter();
  const { data: deploymentsData, isLoading } = useQuery({
    queryKey: ['deployments'],
    queryFn: async () => {
      const response = await api.deployments.list({ page: 1, page_size: 20 });
      return response.data;
    },
  });

  const deployments = deploymentsData?.deployments || [];

  if (isLoading) {
    return <div className="text-muted-foreground">Loading deployments...</div>;
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-semibold tracking-tight">Deployments</h2>
          <p className="text-muted-foreground mt-1">
            {deployments.length} active deployment{deployments.length !== 1 ? 's' : ''}
          </p>
        </div>

        {/* Railway-style new deployment button */}
        <Button
          className="gap-2 bg-gradient-to-r from-primary to-primary/80 hover:from-primary/90 hover:to-primary/70 shadow-lg shadow-primary/20 hover-lift"
          onClick={() => router.push('/dashboard/deployments/new')}
        >
          <Plus className="w-4 h-4" />
          New Deployment
        </Button>
      </div>

      {/* Railway-style deployment cards grid */}
      {deployments.length > 0 ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {deployments.map((deployment: any, index: number) => {
            const gradient = deploymentGradients[index % deploymentGradients.length];
            const status = statusConfig[deployment.status as keyof typeof statusConfig] || statusConfig.PENDING;
            const StatusIcon = status.icon;

            return (
              <Card
                key={deployment.id}
                className={`
                  group relative overflow-hidden border border-border/50
                  hover:border-border transition-all duration-200 cursor-pointer
                  hover-lift
                `}
                onClick={() => router.push(`/dashboard/deployments/${deployment.id}`)}
              >
                {/* Gradient background (Railway-style) */}
                <div className={`absolute inset-0 bg-gradient-to-br ${gradient} opacity-50 group-hover:opacity-70 transition-opacity`} />

                {/* Accent border on left */}
                <div className={`absolute left-0 top-0 bottom-0 w-1 bg-gradient-to-b ${gradient.replace('/20', '').replace('/5', '/80')}`} />

                {/* Content */}
                <div className="relative p-6 space-y-4">
                  {/* Header: Repository + Status */}
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-center gap-2 min-w-0 flex-1">
                      <GitBranch className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                      <span className="font-mono text-sm font-semibold truncate">
                        {deployment.repository}
                      </span>
                    </div>

                    <Badge
                      variant="outline"
                      className={`${status.bg} ${status.border} ${status.color} flex items-center gap-1.5 px-2.5 py-1`}
                    >
                      <StatusIcon className={`w-3 h-3 ${status.animate}`} />
                      <span className="text-xs font-medium">{deployment.status}</span>
                    </Badge>
                  </div>

                  {/* Deployment ID */}
                  <div className="flex items-center gap-2 text-xs text-muted-foreground font-mono">
                    <Server className="w-3.5 h-3.5" />
                    <span>{deployment.id?.substring(0, 12)}</span>
                  </div>

                  {/* Metadata grid */}
                  <div className="grid grid-cols-2 gap-4 pt-3 border-t border-border/30">
                    <div>
                      <p className="text-xs text-muted-foreground mb-1">Environment</p>
                      <p className="text-sm font-medium capitalize">
                        {deployment.environment || 'production'}
                      </p>
                    </div>

                    <div>
                      <p className="text-xs text-muted-foreground mb-1">Duration</p>
                      <p className="text-sm font-medium font-mono">
                        {deployment.duration_seconds
                          ? `${Math.floor(deployment.duration_seconds / 60)}m ${deployment.duration_seconds % 60}s`
                          : '—'}
                      </p>
                    </div>
                  </div>

                  {/* Footer: Created time + Activity */}
                  <div className="flex items-center justify-between text-xs text-muted-foreground pt-2">
                    <div className="flex items-center gap-1.5">
                      <Clock className="w-3.5 h-3.5" />
                      <span>
                        {deployment.created_at
                          ? new Date(deployment.created_at).toLocaleDateString('en-US', {
                              month: 'short',
                              day: 'numeric',
                              hour: '2-digit',
                              minute: '2-digit'
                            })
                          : 'Just now'}
                      </span>
                    </div>

                    {(deployment.status === 'DEPLOYING' || deployment.status === 'BUILDING') && (
                      <div className="flex items-center gap-1.5 text-blue-400">
                        <Activity className="w-3.5 h-3.5 animate-pulse" />
                        <span>Active</span>
                      </div>
                    )}
                  </div>

                  {/* Hover overlay - Railway style */}
                  <div className="absolute inset-0 bg-gradient-to-t from-background/50 to-transparent opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none" />
                </div>
              </Card>
            );
          })}
        </div>
      ) : (
        /* Empty state - Railway style */
        <Card className="relative overflow-hidden border-dashed border-2 border-border/50">
          <div className="absolute inset-0 bg-gradient-to-br from-primary/5 to-transparent" />
          <div className="relative p-12 text-center">
            <div className="w-16 h-16 rounded-full bg-gradient-to-br from-primary/20 to-primary/5 flex items-center justify-center mx-auto mb-4">
              <Rocket className="w-8 h-8 text-primary/50" />
            </div>
            <h3 className="text-lg font-semibold mb-2">No deployments yet</h3>
            <p className="text-muted-foreground mb-6 max-w-sm mx-auto">
              Deploy your first application to get started with automated deployments
            </p>
            <Button
              className="gap-2 bg-gradient-to-r from-primary to-primary/80 hover:from-primary/90 hover:to-primary/70"
              onClick={() => router.push('/dashboard/deployments/new')}
            >
              <Plus className="w-4 h-4" />
              Create Deployment
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
}
