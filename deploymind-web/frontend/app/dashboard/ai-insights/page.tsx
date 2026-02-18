"use client";

import { useQuery } from '@tanstack/react-query';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import {
  Brain, DollarSign, Server, Shield, TrendingDown,
  CheckCircle2, AlertTriangle, Info, Sparkles
} from 'lucide-react';
import { motion } from 'framer-motion';
import { AnimatedCard } from '@/components/ui/animated-card';

export default function AIInsightsPage() {
  // Sample data for AI recommendations (in real app, fetch from deployments)
  const { data: analytics } = useQuery({
    queryKey: ['analytics-overview'],
    queryFn: async () => {
      const response = await api.analytics.overview(30);
      return response.data;
    },
  });

  // Instance recommendation
  const { data: instanceRec } = useQuery({
    queryKey: ['ai-instance-recommendation'],
    queryFn: async () => {
      const response = await api.ai.recommendInstance({
        repository: 'sample/app',
        language: 'python',
        traffic_estimate: 'medium'
      });
      return response.data;
    },
  });

  // Cost optimization
  const { data: costAnalysis } = useQuery({
    queryKey: ['ai-cost-analysis'],
    queryFn: async () => {
      const response = await api.ai.analyzeCosts({
        deployment_count: analytics?.total_deployments || 100,
        avg_duration_seconds: 450,
        instance_types: { 't2.small': 80, 't2.medium': 20 }
      });
      return response.data;
    },
    enabled: !!analytics,
  });

  // Strategy recommendation
  const { data: strategyRec } = useQuery({
    queryKey: ['ai-strategy-recommendation'],
    queryFn: async () => {
      const response = await api.ai.recommendStrategy({
        current_status: 'deployed',
        deployment_count: analytics?.total_deployments || 50,
        success_rate: analytics?.success_rate || 95.5
      });
      return response.data;
    },
    enabled: !!analytics,
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-semibold tracking-tight flex items-center gap-3">
            <Sparkles className="w-8 h-8 text-primary" />
            AI Insights
          </h2>
          <p className="text-muted-foreground mt-1">
            AI-powered recommendations and optimizations
          </p>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid gap-4 md:grid-cols-3">
        <AnimatedCard delay={0}>
          <div className="p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-primary/20 to-primary/5 flex items-center justify-center">
                <Brain className="w-5 h-5 text-primary" />
              </div>
              <Badge variant="outline" className="bg-primary/10 border-primary/20 text-primary">
                Active
              </Badge>
            </div>
            <p className="text-2xl font-semibold">
              {analytics?.total_deployments || 0}
            </p>
            <p className="text-sm text-muted-foreground">Deployments Analyzed</p>
          </div>
        </AnimatedCard>

        <AnimatedCard delay={0.1}>
          <div className="p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-green-500/20 to-green-500/5 flex items-center justify-center">
                <DollarSign className="w-5 h-5 text-green-400" />
              </div>
              <Badge variant="outline" className="bg-green-500/10 border-green-500/20 text-green-400">
                Savings
              </Badge>
            </div>
            <p className="text-2xl font-semibold">
              ${costAnalysis?.potential_savings_usd?.toFixed(2) || '0.00'}
            </p>
            <p className="text-sm text-muted-foreground">Potential Monthly Savings</p>
          </div>
        </AnimatedCard>

        <AnimatedCard delay={0.2}>
          <div className="p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-500/20 to-blue-500/5 flex items-center justify-center">
                <CheckCircle2 className="w-5 h-5 text-blue-400" />
              </div>
              <Badge variant="outline" className="bg-blue-500/10 border-blue-500/20 text-blue-400">
                Success Rate
              </Badge>
            </div>
            <p className="text-2xl font-semibold">
              {analytics?.success_rate?.toFixed(1) || 0}%
            </p>
            <p className="text-sm text-muted-foreground">Deployment Success Rate</p>
          </div>
        </AnimatedCard>
      </div>

      {/* Instance Recommendation */}
      <AnimatedCard delay={0.3}>
        <div className="p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-purple-500/20 to-purple-500/5 flex items-center justify-center">
              <Server className="w-5 h-5 text-purple-400" />
            </div>
            <div>
              <h3 className="text-lg font-semibold">Instance Recommendation</h3>
              <p className="text-sm text-muted-foreground">Optimal EC2 instance for your workload</p>
            </div>
          </div>

          {instanceRec && (
            <div className="space-y-4">
              <div className="p-4 rounded-lg bg-purple-500/10 border border-purple-500/20">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-purple-400">Recommended</span>
                  <span className="font-mono text-lg font-semibold">
                    {instanceRec.recommended_instance}
                  </span>
                </div>
                <p className="text-sm text-muted-foreground">
                  {instanceRec.reasoning}
                </p>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-xs text-muted-foreground mb-1">Estimated Cost</p>
                  <p className="text-lg font-semibold">
                    ${instanceRec.estimated_cost_monthly_usd}/mo
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground mb-1">Alternatives</p>
                  <div className="flex gap-2">
                    {instanceRec.alternatives?.slice(0, 2).map((alt: string) => (
                      <Badge key={alt} variant="outline" className="font-mono">
                        {alt}
                      </Badge>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </AnimatedCard>

      {/* Cost Optimization */}
      <AnimatedCard delay={0.4}>
        <div className="p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-green-500/20 to-green-500/5 flex items-center justify-center">
              <TrendingDown className="w-5 h-5 text-green-400" />
            </div>
            <div>
              <h3 className="text-lg font-semibold">Cost Optimization</h3>
              <p className="text-sm text-muted-foreground">AI-powered cost savings suggestions</p>
            </div>
          </div>

          {costAnalysis && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4 p-4 rounded-lg bg-muted/50">
                <div>
                  <p className="text-xs text-muted-foreground mb-1">Current Cost</p>
                  <p className="text-xl font-semibold">
                    ${costAnalysis.current_monthly_cost_usd?.toFixed(2)}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground mb-1">Potential Savings</p>
                  <p className="text-xl font-semibold text-green-400">
                    ${costAnalysis.potential_savings_usd?.toFixed(2)}
                  </p>
                </div>
              </div>

              <div className="space-y-2">
                <p className="text-sm font-medium">Optimization Suggestions</p>
                {costAnalysis.optimization_suggestions?.map((suggestion: string, i: number) => (
                  <div
                    key={i}
                    className="flex items-start gap-2 p-3 rounded-lg bg-green-500/5 border border-green-500/10"
                  >
                    <CheckCircle2 className="w-4 h-4 text-green-400 mt-0.5 flex-shrink-0" />
                    <span className="text-sm text-muted-foreground">{suggestion}</span>
                  </div>
                ))}
              </div>

              <Badge
                variant="outline"
                className={`
                  ${costAnalysis.priority === 'high' ? 'bg-red-500/10 border-red-500/20 text-red-400' : ''}
                  ${costAnalysis.priority === 'medium' ? 'bg-yellow-500/10 border-yellow-500/20 text-yellow-400' : ''}
                  ${costAnalysis.priority === 'low' ? 'bg-blue-500/10 border-blue-500/20 text-blue-400' : ''}
                `}
              >
                {costAnalysis.priority?.toUpperCase()} PRIORITY
              </Badge>
            </div>
          )}
        </div>
      </AnimatedCard>

      {/* Deployment Strategy */}
      <AnimatedCard delay={0.5}>
        <div className="p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-500/20 to-blue-500/5 flex items-center justify-center">
              <Shield className="w-5 h-5 text-blue-400" />
            </div>
            <div>
              <h3 className="text-lg font-semibold">Deployment Strategy</h3>
              <p className="text-sm text-muted-foreground">Recommended deployment approach</p>
            </div>
          </div>

          {strategyRec && (
            <div className="space-y-4">
              <div className="p-4 rounded-lg bg-blue-500/10 border border-blue-500/20">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-blue-400">Strategy</span>
                  <Badge variant="outline" className="bg-blue-500/10 border-blue-500/20 text-blue-400">
                    {strategyRec.recommended_strategy}
                  </Badge>
                </div>
                <p className="text-sm text-muted-foreground">
                  {strategyRec.reasoning}
                </p>
              </div>

              <div className="flex items-center gap-2 p-3 rounded-lg bg-muted/50">
                <Info className="w-4 h-4 text-muted-foreground" />
                <span className="text-sm text-muted-foreground">
                  Risk Level: <span className="font-medium text-foreground">{strategyRec.risk_level}</span>
                </span>
              </div>
            </div>
          )}
        </div>
      </AnimatedCard>
    </div>
  );
}
