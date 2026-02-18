"use client";

import { useQuery } from '@tanstack/react-query';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { api } from '@/lib/api';
import { Cpu, MemoryStick, HardDrive, Network, Activity } from 'lucide-react';
import { motion } from 'framer-motion';

interface ResourceMonitorProps {
  deploymentId: string;
}

export function ResourceMonitor({ deploymentId }: ResourceMonitorProps) {
  const { data: metrics, isLoading } = useQuery({
    queryKey: ['metrics', deploymentId],
    queryFn: async () => {
      const response = await api.monitoring.getMetrics(deploymentId);
      return response.data;
    },
    refetchInterval: 5000, // Refresh every 5 seconds
  });

  const { data: health } = useQuery({
    queryKey: ['health', deploymentId],
    queryFn: async () => {
      const response = await api.monitoring.getHealth(deploymentId);
      return response.data;
    },
    refetchInterval: 10000, // Refresh every 10 seconds
  });

  if (isLoading) {
    return (
      <Card className="p-6">
        <div className="text-sm text-muted-foreground">Loading metrics...</div>
      </Card>
    );
  }

  const metricsData = metrics?.metrics || {};

  // Metric items configuration
  const metricItems = [
    {
      icon: Cpu,
      label: 'CPU',
      value: `${metricsData.cpu_utilization}%`,
      percent: metricsData.cpu_utilization,
      color: metricsData.cpu_utilization > 80 ? 'red' : metricsData.cpu_utilization > 60 ? 'yellow' : 'green',
      gradient: 'from-blue-500 to-cyan-500'
    },
    {
      icon: MemoryStick,
      label: 'Memory',
      value: `${metricsData.memory_used_mb?.toFixed(0)} MB`,
      percent: metricsData.memory_used_percent,
      total: `${metricsData.memory_total_mb} MB`,
      color: metricsData.memory_used_percent > 85 ? 'red' : metricsData.memory_used_percent > 70 ? 'yellow' : 'green',
      gradient: 'from-purple-500 to-pink-500'
    },
    {
      icon: HardDrive,
      label: 'Disk',
      value: `${metricsData.disk_used_gb?.toFixed(1)} GB`,
      percent: metricsData.disk_used_percent,
      total: `${metricsData.disk_total_gb} GB`,
      color: metricsData.disk_used_percent > 80 ? 'red' : metricsData.disk_used_percent > 60 ? 'yellow' : 'green',
      gradient: 'from-green-500 to-emerald-500'
    },
    {
      icon: Network,
      label: 'Network',
      value: `↓ ${metricsData.network_in_mb?.toFixed(2)} MB/s`,
      value2: `↑ ${metricsData.network_out_mb?.toFixed(2)} MB/s`,
      percent: 50, // Mock percentage for visual
      color: 'green',
      gradient: 'from-orange-500 to-red-500'
    },
  ];

  return (
    <div className="space-y-4">
      {/* Health Status */}
      {health && (
        <Card className="p-4 bg-gradient-to-r from-background to-muted/20">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className={`
                w-10 h-10 rounded-full flex items-center justify-center
                ${health.status === 'healthy' ? 'bg-green-500/20 text-green-400' : ''}
                ${health.status === 'warning' ? 'bg-yellow-500/20 text-yellow-400' : ''}
                ${health.status === 'critical' ? 'bg-red-500/20 text-red-400' : ''}
              `}>
                <Activity className="w-5 h-5" />
              </div>
              <div>
                <p className="font-semibold capitalize">{health.status}</p>
                <p className="text-xs text-muted-foreground">
                  Uptime: {Math.floor(health.uptime_seconds / 3600)}h {Math.floor((health.uptime_seconds % 3600) / 60)}m
                </p>
              </div>
            </div>

            <div className="text-right">
              <p className="text-sm font-medium">{health.response_time_ms}ms</p>
              <p className="text-xs text-muted-foreground">Response Time</p>
            </div>
          </div>

          {health.issues && health.issues.length > 0 && (
            <div className="mt-3 pt-3 border-t border-border/50">
              <p className="text-xs font-medium text-muted-foreground mb-2">Issues:</p>
              <div className="space-y-1">
                {health.issues.map((issue: string, i: number) => (
                  <div key={i} className="text-xs text-yellow-400 flex items-center gap-1.5">
                    <div className="w-1 h-1 rounded-full bg-yellow-400" />
                    {issue}
                  </div>
                ))}
              </div>
            </div>
          )}
        </Card>
      )}

      {/* Resource Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {metricItems.map((metric, index) => {
          const Icon = metric.icon;
          return (
            <motion.div
              key={metric.label}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.1 }}
            >
              <Card className="p-4 relative overflow-hidden group hover:border-primary/50 transition-colors">
                {/* Gradient background */}
                <div className={`absolute inset-0 bg-gradient-to-br ${metric.gradient} opacity-5 group-hover:opacity-10 transition-opacity`} />

                <div className="relative space-y-3">
                  {/* Header */}
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Icon className="w-4 h-4 text-muted-foreground" />
                      <span className="text-sm font-medium">{metric.label}</span>
                    </div>
                    <Badge
                      variant="outline"
                      className={`
                        ${metric.color === 'green' ? 'bg-green-500/10 border-green-500/20 text-green-400' : ''}
                        ${metric.color === 'yellow' ? 'bg-yellow-500/10 border-yellow-500/20 text-yellow-400' : ''}
                        ${metric.color === 'red' ? 'bg-red-500/10 border-red-500/20 text-red-400' : ''}
                        text-xs
                      `}
                    >
                      {metric.percent?.toFixed(0)}%
                    </Badge>
                  </div>

                  {/* Progress bar */}
                  <div className="space-y-1">
                    <div className="h-2 bg-muted rounded-full overflow-hidden">
                      <motion.div
                        className={`h-full bg-gradient-to-r ${metric.gradient} rounded-full`}
                        initial={{ width: 0 }}
                        animate={{ width: `${metric.percent}%` }}
                        transition={{ duration: 0.6, ease: "easeOut" }}
                      />
                    </div>
                  </div>

                  {/* Values */}
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-mono font-medium">{metric.value}</span>
                    {metric.total && (
                      <span className="text-muted-foreground">of {metric.total}</span>
                    )}
                    {metric.value2 && (
                      <span className="font-mono font-medium">{metric.value2}</span>
                    )}
                  </div>
                </div>
              </Card>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
