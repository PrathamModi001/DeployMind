"use client";

import { useQuery } from '@tanstack/react-query';
import { useParams, useRouter } from 'next/navigation';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { AnimatedCard } from '@/components/ui/animated-card';
import { api } from '@/lib/api';
import {
  ArrowLeft, GitBranch, Clock, Server, Terminal, Play, Square,
  CheckCircle2, XCircle, Loader2, Activity, Shield, Rocket
} from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';

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

const phases = [
  { id: 'security', label: 'Security Scan', icon: Shield, description: 'Scanning for vulnerabilities' },
  { id: 'build', label: 'Build', icon: Rocket, description: 'Building Docker image' },
  { id: 'deploy', label: 'Deploy', icon: CheckCircle2, description: 'Deploying to EC2' },
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
    refetchInterval: 5000,
  });

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

  const status = statusConfig[deployment.status as keyof typeof statusConfig] || statusConfig.PENDING;
  const StatusIcon = status.icon;
  const currentPhase = deployment.status === 'BUILDING' ? 1 : deployment.status === 'DEPLOYING' ? 2 : deployment.status === 'DEPLOYED' ? 3 : 0;

  return (
    <div className="space-y-6">
      {/* Breadcrumb header - Vercel style */}
      <div className="flex items-center gap-3">
        <Button
          variant="ghost"
          size="icon"
          className="hover:bg-white/5"
          onClick={() => router.push('/dashboard/deployments')}
        >
          <ArrowLeft className="w-5 h-5" />
        </Button>

        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <span className="hover:text-foreground transition-colors cursor-pointer"
            onClick={() => router.push('/dashboard/deployments')}>
            Deployments
          </span>
          <span>/</span>
          <span className="text-foreground font-medium font-mono">
            {deployment.id?.substring(0, 8)}
          </span>
        </div>
      </div>

      {/* Repository header - Vercel style */}
      <div className="flex items-start justify-between">
        <div className="space-y-2">
          <div className="flex items-center gap-3">
            <GitBranch className="w-5 h-5 text-muted-foreground" />
            <h2 className="text-2xl font-semibold font-mono">
              {deployment.repository}
            </h2>
          </div>

          <div className="flex items-center gap-4 text-sm text-muted-foreground">
            <div className="flex items-center gap-1.5">
              <Server className="w-4 h-4" />
              <span className="font-mono">{deployment.instance_id || 'N/A'}</span>
            </div>
            <div className="flex items-center gap-1.5">
              <Clock className="w-4 h-4" />
              <span>
                {deployment.created_at
                  ? new Date(deployment.created_at).toLocaleString()
                  : 'Just now'}
              </span>
            </div>
          </div>
        </div>

        {/* Status badge - large */}
        <Badge
          variant="outline"
          className={`
            ${status.bg}
            ${status.border}
            ${status.color}
            px-4 py-2 text-sm flex items-center gap-2
          `}
        >
          <StatusIcon className={`w-4 h-4 ${status.animate}`} />
          {deployment.status}
        </Badge>
      </div>

      {/* Terminal logs - Vercel style */}
      <AnimatedCard className="relative overflow-hidden" delay={0.1}>
        <div className="flex items-center justify-between px-4 py-3 border-b border-border/50 bg-black/20">
          <div className="flex items-center gap-2">
            <Terminal className="w-4 h-4 text-muted-foreground" />
            <span className="text-sm font-medium">Deployment Logs</span>
            {(deployment.status === 'DEPLOYING' || deployment.status === 'BUILDING') && (
              <Badge variant="outline" className="text-xs bg-blue-500/10 border-blue-500/20 text-blue-400">
                <Activity className="w-3 h-3 mr-1 animate-pulse" />
                Live
              </Badge>
            )}
          </div>

          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" className="h-7 text-xs gap-1.5">
              <Play className="w-3 h-3" />
              Resume
            </Button>
            <Button variant="ghost" size="sm" className="h-7 text-xs gap-1.5">
              <Square className="w-3 h-3" />
              Pause
            </Button>
          </div>
        </div>

        <div className="bg-[#0a0a0f] p-4 font-mono text-xs leading-relaxed">
          <ScrollArea className="h-96">
            {logs.length === 0 ? (
              <p className="text-muted-foreground">No logs available yet...</p>
            ) : (
              logs.map((log, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.02 }}
                  className="flex gap-3 mb-1 hover:bg-white/5 px-2 py-0.5 rounded transition-colors"
                >
                  <span className="text-muted-foreground select-none min-w-[80px]">
                    {new Date().toLocaleTimeString()}
                  </span>
                  <span className="text-foreground/90">{log}</span>
                </motion.div>
              ))
            )}
            <div ref={logsEndRef} />

            {/* Animated cursor */}
            {(deployment.status === 'DEPLOYING' || deployment.status === 'BUILDING') && (
              <motion.span
                animate={{ opacity: [1, 0, 1] }}
                transition={{ duration: 1, repeat: Infinity }}
                className="inline-block w-2 h-4 bg-primary/60 ml-2"
              />
            )}
          </ScrollArea>
        </div>
      </AnimatedCard>

      {/* Deployment pipeline - Visual (Railway + Linear style) */}
      <AnimatedCard delay={0.2}>
        <div className="p-6">
          <h3 className="text-lg font-semibold mb-6">Deployment Pipeline</h3>

          <div className="relative">
            {/* Progress line */}
            <div className="absolute left-6 top-6 bottom-6 w-0.5 bg-border" />
            <motion.div
              className="absolute left-6 top-6 w-0.5 bg-gradient-to-b from-primary to-primary/50"
              initial={{ height: 0 }}
              animate={{ height: `${(currentPhase / phases.length) * 100}%` }}
              transition={{ duration: 0.6, ease: [0.4, 0, 0.2, 1] }}
            />

            {/* Phases */}
            <div className="space-y-6">
              {phases.map((phase, index) => {
                const Icon = phase.icon;
                const isCompleted = index < currentPhase;
                const isActive = index === currentPhase;

                return (
                  <motion.div
                    key={phase.id}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: index * 0.1 }}
                    className="flex items-start gap-4 relative"
                  >
                    {/* Icon */}
                    <div className={`
                      relative z-10 w-12 h-12 rounded-full flex items-center justify-center
                      transition-all duration-300
                      ${isCompleted
                        ? 'bg-primary/20 border-2 border-primary'
                        : isActive
                          ? 'bg-primary/10 border-2 border-primary/50 animate-pulse'
                          : 'bg-muted border-2 border-border'
                      }
                    `}>
                      <Icon className={`
                        w-5 h-5 transition-colors
                        ${isCompleted
                          ? 'text-primary'
                          : isActive
                            ? 'text-primary/70'
                            : 'text-muted-foreground'
                        }
                      `} />
                    </div>

                    {/* Content */}
                    <div className="flex-1 pt-2">
                      <div className="flex items-center justify-between mb-1">
                        <h4 className="font-semibold">{phase.label}</h4>
                        {isCompleted && (
                          <CheckCircle2 className="w-4 h-4 text-primary" />
                        )}
                        {isActive && (
                          <motion.div
                            animate={{ rotate: 360 }}
                            transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
                          >
                            <Activity className="w-4 h-4 text-primary" />
                          </motion.div>
                        )}
                      </div>
                      <p className="text-sm text-muted-foreground">
                        {phase.description}
                      </p>
                    </div>
                  </motion.div>
                );
              })}
            </div>
          </div>
        </div>
      </AnimatedCard>

      {/* Actions */}
      {deployment.status === 'DEPLOYED' && (
        <AnimatedCard delay={0.3}>
          <div className="p-6">
            <h3 className="text-lg font-semibold mb-4">Actions</h3>
            <div className="flex gap-3">
              <Button variant="outline" className="gap-2">
                <XCircle className="h-4 w-4" />
                Rollback
              </Button>
              <Button variant="outline" className="gap-2">
                View Health Checks
              </Button>
            </div>
          </div>
        </AnimatedCard>
      )}
    </div>
  );
}
