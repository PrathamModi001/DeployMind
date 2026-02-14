"use client";

import { useQuery } from '@tanstack/react-query';
import { useParams, useRouter } from 'next/navigation';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { api } from '@/lib/api';
import { ArrowLeft, CheckCircle2, Clock, Rocket, Shield, XCircle } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

const statusColors = {
  PENDING: 'bg-yellow-500/10 text-yellow-500 border-yellow-500/20',
  BUILDING: 'bg-blue-500/10 text-blue-500 border-blue-500/20',
  DEPLOYING: 'bg-primary/10 text-primary border-primary/20',
  DEPLOYED: 'bg-green-500/10 text-green-500 border-green-500/20',
  FAILED: 'bg-destructive/10 text-destructive border-destructive/20',
  ROLLED_BACK: 'bg-orange-500/10 text-orange-500 border-orange-500/20',
};

const phases = [
  { id: 'security', label: 'Security Scan', icon: Shield },
  { id: 'build', label: 'Build', icon: Rocket },
  { id: 'deploy', label: 'Deploy', icon: CheckCircle2 },
];

export default function DeploymentDetailPage() {
  const params = useParams();
  const router = useRouter();
  const [logs, setLogs] = useState<string[]>([]);
  const logsEndRef = useRef<HTMLDivElement>(null);

  const { data: deployment, isLoading } = useQuery({
    queryKey: ['deployment', params.id],
    queryFn: async () => {
      const response = await api.deployments.get(params.id as string);
      return response.data;
    },
    refetchInterval: 5000, // Refresh every 5 seconds
  });

  // Fetch logs
  const { data: logsData } = useQuery({
    queryKey: ['deployment-logs', params.id],
    queryFn: async () => {
      const response = await api.deployments.logs(params.id as string);
      return response.data;
    },
    refetchInterval: 2000,
  });

  useEffect(() => {
    if (logsData?.logs) {
      setLogs(logsData.logs);
    }
  }, [logsData]);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  if (isLoading) {
    return <div className="text-muted-foreground">Loading deployment...</div>;
  }

  if (!deployment) {
    return (
      <div className="text-center py-12">
        <p className="text-lg text-muted-foreground">Deployment not found</p>
        <Button onClick={() => router.push('/dashboard/deployments')} className="mt-4">
          Back to Deployments
        </Button>
      </div>
    );
  }

  const currentPhase = deployment.status === 'BUILDING' ? 1 : deployment.status === 'DEPLOYING' ? 2 : deployment.status === 'DEPLOYED' ? 3 : 0;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => router.push('/dashboard/deployments')}>
          <ArrowLeft className="h-5 w-5" />
        </Button>
        <div>
          <h2 className="text-3xl font-semibold tracking-tight">Deployment Details</h2>
          <p className="text-muted-foreground mt-1">
            {deployment.repository} • {deployment.id?.substring(0, 8)}
          </p>
        </div>
      </div>

      {/* Status Overview */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Status Overview</CardTitle>
              <CardDescription>Current deployment status and progress</CardDescription>
            </div>
            <Badge
              variant="outline"
              className={statusColors[deployment.status as keyof typeof statusColors] || statusColors.PENDING}
            >
              {deployment.status}
            </Badge>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div>
              <p className="text-sm text-muted-foreground mb-1">Instance ID</p>
              <p className="font-mono text-sm">{deployment.instance_id || 'N/A'}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground mb-1">Strategy</p>
              <p className="capitalize">{deployment.strategy || 'rolling'}</p>
            </div>
            <div>
              <p className="text-sm text-muted-foreground mb-1">Duration</p>
              <p>
                {deployment.duration_seconds
                  ? `${Math.floor(deployment.duration_seconds / 60)}m ${deployment.duration_seconds % 60}s`
                  : 'In progress...'}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Deployment Timeline */}
      <Card>
        <CardHeader>
          <CardTitle>Deployment Pipeline</CardTitle>
          <CardDescription>Sequential deployment phases</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between">
            {phases.map((phase, index) => {
              const Icon = phase.icon;
              const isCompleted = index < currentPhase;
              const isActive = index === currentPhase;
              const isPending = index > currentPhase;

              return (
                <div key={phase.id} className="flex items-center flex-1">
                  <div className="flex flex-col items-center">
                    <div
                      className={`
                        w-12 h-12 rounded-full flex items-center justify-center border-2 transition-colors
                        ${isCompleted ? 'bg-primary/10 border-primary text-primary' : ''}
                        ${isActive ? 'bg-primary/20 border-primary text-primary animate-pulse' : ''}
                        ${isPending ? 'bg-muted border-border text-muted-foreground' : ''}
                      `}
                    >
                      <Icon className="h-5 w-5" />
                    </div>
                    <p className="text-sm mt-2 font-medium">{phase.label}</p>
                    {isCompleted && <CheckCircle2 className="h-4 w-4 text-primary mt-1" />}
                    {isActive && <Clock className="h-4 w-4 text-primary mt-1 animate-spin" />}
                  </div>
                  {index < phases.length - 1 && (
                    <div
                      className={`flex-1 h-0.5 mx-4 ${
                        isCompleted ? 'bg-primary' : 'bg-border'
                      }`}
                    />
                  )}
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Live Logs */}
      <Card>
        <CardHeader>
          <CardTitle>Deployment Logs</CardTitle>
          <CardDescription>Real-time deployment output</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="bg-[#0D0D0D] border border-border rounded-lg p-4 font-mono text-sm">
            <ScrollArea className="h-96">
              <div className="space-y-1">
                {logs.length === 0 ? (
                  <p className="text-muted-foreground">No logs available yet...</p>
                ) : (
                  logs.map((log, i) => (
                    <div key={i} className="leading-relaxed">
                      <span className="text-muted-foreground mr-3">
                        {new Date().toLocaleTimeString()}
                      </span>
                      <span className="text-foreground/80">{log}</span>
                    </div>
                  ))
                )}
                <div ref={logsEndRef} />
              </div>
              {/* Cursor indicator */}
              {deployment.status === 'DEPLOYING' || deployment.status === 'BUILDING' ? (
                <span className="inline-block w-2 h-4 bg-primary/50 animate-pulse ml-1" />
              ) : null}
            </ScrollArea>
          </div>
        </CardContent>
      </Card>

      {/* Actions */}
      {deployment.status === 'DEPLOYED' && (
        <Card>
          <CardHeader>
            <CardTitle>Actions</CardTitle>
            <CardDescription>Manage this deployment</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex gap-3">
              <Button variant="outline" className="gap-2">
                <XCircle className="h-4 w-4" />
                Rollback
              </Button>
              <Button variant="outline" className="gap-2">
                View Health Checks
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
