"use client";

import { useQuery } from '@tanstack/react-query';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { apiClient } from '@/lib/api';
import {
  Brain, DollarSign, Server, Shield, TrendingDown, TrendingUp,
  CheckCircle2, AlertTriangle, Info, Sparkles, Activity, Zap, Target
} from 'lucide-react';
import { motion } from 'framer-motion';
import { AnimatedCard } from '@/components/ui/animated-card';
import { ActionButton } from '@/components/ai/ActionButton';

export default function AIInsightsPage() {
  // Get first deployment ID for demos (in real app, select from UI)
  const { data: deployments } = useQuery({
    queryKey: ['deployments-list'],
    queryFn: async () => {
      const response = await apiClient.get('/api/deployments', {
        params: { page: 1, page_size: 5 }
      });
      return response.data.deployments;
    },
  });

  const firstDeploymentId = deployments?.[0]?.id || 'demo-deployment-1';

  // Analytics overview
  const { data: analytics } = useQuery({
    queryKey: ['analytics-overview'],
    queryFn: async () => {
      const response = await apiClient.get('/api/analytics/overview', {
        params: { days: 30 }
      });
      return response.data;
    },
  });

  // Auto-Scaling Advisor (Advanced AI)
  const { data: scalingRec, refetch: refetchScaling } = useQuery({
    queryKey: ['ai-scaling-recommendation', firstDeploymentId],
    queryFn: async () => {
      const response = await apiClient.post(
        `/api/ai/advanced/scaling-recommendation/${firstDeploymentId}`,
        null,
        { params: { hours_lookback: 6 } }
      );
      return response.data;
    },
    enabled: !!firstDeploymentId,
  });

  // Cost Trend Analysis (Advanced AI)
  const { data: costTrends, refetch: refetchCost } = useQuery({
    queryKey: ['ai-cost-trends'],
    queryFn: async () => {
      const response = await apiClient.get('/api/ai/advanced/cost-analysis', {
        params: { months_lookback: 6 }
      });
      return response.data;
    },
  });

  // Security Risk Score (Advanced AI)
  const { data: securityRisk, refetch: refetchSecurity } = useQuery({
    queryKey: ['ai-security-risk', firstDeploymentId],
    queryFn: async () => {
      const response = await apiClient.post(
        `/api/ai/advanced/security-risk/${firstDeploymentId}`
      );
      return response.data;
    },
    enabled: !!firstDeploymentId,
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
            AI-powered recommendations with actionable one-click fixes
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
              ${costTrends?.potential_savings_monthly?.toFixed(2) || '0.00'}
            </p>
            <p className="text-sm text-muted-foreground">Potential Monthly Savings</p>
          </div>
        </AnimatedCard>

        <AnimatedCard delay={0.2}>
          <div className="p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-500/20 to-blue-500/5 flex items-center justify-center">
                <Shield className="w-5 h-5 text-blue-400" />
              </div>
              <Badge variant="outline" className={`
                ${securityRisk?.rating === 'LOW' ? 'bg-green-500/10 border-green-500/20 text-green-400' : ''}
                ${securityRisk?.rating === 'MEDIUM' ? 'bg-yellow-500/10 border-yellow-500/20 text-yellow-400' : ''}
                ${securityRisk?.rating === 'HIGH' || securityRisk?.rating === 'CRITICAL' ? 'bg-red-500/10 border-red-500/20 text-red-400' : ''}
              `}>
                {securityRisk?.rating || 'UNKNOWN'}
              </Badge>
            </div>
            <p className="text-2xl font-semibold">
              {securityRisk?.risk_score?.toFixed(1) || '0.0'}
            </p>
            <p className="text-sm text-muted-foreground">Security Risk Score</p>
          </div>
        </AnimatedCard>
      </div>

      {/* Auto-Scaling Advisor */}
      <AnimatedCard delay={0.3}>
        <div className="p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-purple-500/20 to-purple-500/5 flex items-center justify-center">
              <Activity className="w-5 h-5 text-purple-400" />
            </div>
            <div className="flex-1">
              <h3 className="text-lg font-semibold">Auto-Scaling Recommendations</h3>
              <p className="text-sm text-muted-foreground">AI-powered vertical scaling suggestions based on resource utilization</p>
            </div>
          </div>

          {scalingRec && (
            <div className="space-y-4">
              {/* Utilization Metrics */}
              {scalingRec.utilization && (
                <div className="grid grid-cols-4 gap-4 p-4 rounded-lg bg-muted/50">
                  <div>
                    <p className="text-xs text-muted-foreground mb-1">Avg CPU</p>
                    <p className="text-lg font-semibold">{scalingRec.utilization.avg_cpu}%</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground mb-1">Peak CPU</p>
                    <p className="text-lg font-semibold">{scalingRec.utilization.peak_cpu}%</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground mb-1">Avg Memory</p>
                    <p className="text-lg font-semibold">{scalingRec.utilization.avg_memory}%</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted-foreground mb-1">Peak Memory</p>
                    <p className="text-lg font-semibold">{scalingRec.utilization.peak_memory}%</p>
                  </div>
                </div>
              )}

              {scalingRec.should_scale ? (
                <>
                  {/* Scaling Recommendation */}
                  <div className="p-4 rounded-lg bg-purple-500/10 border border-purple-500/20">
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          <Zap className="w-4 h-4 text-purple-400" />
                          <span className="text-sm font-medium text-purple-400">
                            {scalingRec.scaling_type === 'vertical' ? 'Vertical Scaling' : 'Horizontal Scaling'}
                          </span>
                          <Badge variant="outline" className="bg-purple-500/10 border-purple-500/20 text-purple-400">
                            {scalingRec.current_config?.instance_type} → {scalingRec.recommended_config?.instance_type}
                          </Badge>
                        </div>
                        <p className="text-sm text-muted-foreground">
                          {scalingRec.reasoning}
                        </p>
                      </div>
                    </div>

                    <div className="grid grid-cols-3 gap-4 mt-4 pt-4 border-t border-purple-500/20">
                      <div>
                        <p className="text-xs text-muted-foreground mb-1">Cost Impact</p>
                        <p className={`text-sm font-semibold ${scalingRec.cost_impact_monthly > 0 ? 'text-red-400' : 'text-green-400'}`}>
                          {scalingRec.cost_impact_monthly > 0 ? '+' : ''}${scalingRec.cost_impact_monthly?.toFixed(2)}/mo
                        </p>
                      </div>
                      <div>
                        <p className="text-xs text-muted-foreground mb-1">Performance</p>
                        <p className="text-sm font-semibold text-green-400">
                          {typeof scalingRec.performance_improvement === 'string'
                            ? scalingRec.performance_improvement
                            : `+${scalingRec.performance_improvement}%`}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs text-muted-foreground mb-1">Current Config</p>
                        <p className="text-sm font-semibold">
                          {scalingRec.current_config?.vcpu}vCPU / {scalingRec.current_config?.memory_gb}GB
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* Actionable Recommendations */}
                  {scalingRec.actionable_recommendations?.length > 0 && (
                    <div className="space-y-2">
                      <p className="text-sm font-medium flex items-center gap-2">
                        <Target className="w-4 h-4" />
                        Quick Actions
                      </p>
                      {scalingRec.actionable_recommendations.map((rec: any) => (
                        <div
                          key={rec.id}
                          className="flex items-center justify-between p-3 rounded-lg bg-muted/50 border"
                        >
                          <div className="flex-1">
                            <p className="text-sm font-medium">{rec.title}</p>
                            <p className="text-xs text-muted-foreground mt-1">
                              {rec.description}
                            </p>
                          </div>
                          <ActionButton
                            recommendation={rec}
                            onSuccess={() => {
                              refetchScaling();
                            }}
                          />
                        </div>
                      ))}
                    </div>
                  )}
                </>
              ) : (
                <div className="flex items-center gap-2 p-4 rounded-lg bg-green-500/5 border border-green-500/10">
                  <CheckCircle2 className="w-5 h-5 text-green-400" />
                  <div>
                    <p className="text-sm font-medium text-foreground">Resources Optimized</p>
                    <p className="text-xs text-muted-foreground">
                      {scalingRec.reason || 'Current instance size is appropriate for your workload'}
                    </p>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </AnimatedCard>

      {/* Cost Trend Analysis */}
      <AnimatedCard delay={0.4}>
        <div className="p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-green-500/20 to-green-500/5 flex items-center justify-center">
              <TrendingDown className="w-5 h-5 text-green-400" />
            </div>
            <div className="flex-1">
              <h3 className="text-lg font-semibold">Cost Trend Analysis</h3>
              <p className="text-sm text-muted-foreground">Historical costs and optimization opportunities</p>
            </div>
          </div>

          {costTrends && (
            <div className="space-y-4">
              {/* Cost Summary */}
              <div className="grid grid-cols-3 gap-4 p-4 rounded-lg bg-muted/50">
                <div>
                  <p className="text-xs text-muted-foreground mb-1">Current Month</p>
                  <p className="text-xl font-semibold">${costTrends.total_cost_current_month?.toFixed(2)}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground mb-1">Growth Rate</p>
                  <p className={`text-xl font-semibold ${costTrends.monthly_growth_rate_percent > 0 ? 'text-red-400' : 'text-green-400'}`}>
                    {costTrends.monthly_growth_rate_percent > 0 ? '+' : ''}{costTrends.monthly_growth_rate_percent?.toFixed(1)}%
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground mb-1">Potential Savings</p>
                  <p className="text-xl font-semibold text-green-400">
                    ${costTrends.potential_savings_monthly?.toFixed(2)}
                  </p>
                </div>
              </div>

              {/* Trend Badge */}
              <div className="flex items-center gap-2">
                <Badge variant="outline" className={`
                  ${costTrends.trend === 'increasing' ? 'bg-red-500/10 border-red-500/20 text-red-400' : ''}
                  ${costTrends.trend === 'stable' ? 'bg-blue-500/10 border-blue-500/20 text-blue-400' : ''}
                  ${costTrends.trend === 'decreasing' ? 'bg-green-500/10 border-green-500/20 text-green-400' : ''}
                `}>
                  {costTrends.trend === 'increasing' && <TrendingUp className="w-3 h-3 mr-1" />}
                  {costTrends.trend === 'decreasing' && <TrendingDown className="w-3 h-3 mr-1" />}
                  {costTrends.trend?.toUpperCase()} TREND
                </Badge>
              </div>

              {/* Optimization Opportunities */}
              {costTrends.optimization_opportunities?.length > 0 && (
                <div className="space-y-2">
                  <p className="text-sm font-medium">Optimization Opportunities</p>
                  {costTrends.optimization_opportunities.map((opp: string, i: number) => (
                    <div
                      key={i}
                      className="flex items-start gap-2 p-3 rounded-lg bg-green-500/5 border border-green-500/10"
                    >
                      <CheckCircle2 className="w-4 h-4 text-green-400 mt-0.5 flex-shrink-0" />
                      <p className="text-sm text-foreground">{opp}</p>
                    </div>
                  ))}
                </div>
              )}

              {/* Actionable Recommendations */}
              {costTrends.actionable_recommendations?.length > 0 && (
                <div className="space-y-2">
                  <p className="text-sm font-medium flex items-center gap-2">
                    <Target className="w-4 h-4" />
                    Quick Actions
                  </p>
                  {costTrends.actionable_recommendations.map((rec: any) => (
                    <div
                      key={rec.id}
                      className="flex items-center justify-between p-3 rounded-lg bg-muted/50 border"
                    >
                      <div className="flex-1">
                        <p className="text-sm font-medium">{rec.title}</p>
                        <p className="text-xs text-muted-foreground mt-1">
                          {rec.description}
                        </p>
                        {rec.impact?.savings_monthly && (
                          <p className="text-xs text-green-400 mt-1">
                            Save ${rec.impact.savings_monthly.toFixed(2)}/month
                          </p>
                        )}
                      </div>
                      <ActionButton
                        recommendation={rec}
                        onSuccess={() => {
                          refetchCost();
                        }}
                      />
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </AnimatedCard>

      {/* Security Risk Score */}
      <AnimatedCard delay={0.5}>
        <div className="p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-orange-500/20 to-orange-500/5 flex items-center justify-center">
              <Shield className="w-5 h-5 text-orange-400" />
            </div>
            <div className="flex-1">
              <h3 className="text-lg font-semibold">Security Risk Assessment</h3>
              <p className="text-sm text-muted-foreground">Vulnerability analysis and security recommendations</p>
            </div>
          </div>

          {securityRisk && (
            <div className="space-y-4">
              {/* Risk Score */}
              <div className="p-4 rounded-lg bg-muted/50">
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <p className="text-sm text-muted-foreground mb-1">Risk Score</p>
                    <p className="text-3xl font-semibold">{securityRisk.risk_score?.toFixed(1)}<span className="text-lg text-muted-foreground">/100</span></p>
                  </div>
                  <Badge variant="outline" className={`
                    ${securityRisk.rating === 'LOW' ? 'bg-green-500/10 border-green-500/20 text-green-400' : ''}
                    ${securityRisk.rating === 'MEDIUM' ? 'bg-yellow-500/10 border-yellow-500/20 text-yellow-400' : ''}
                    ${securityRisk.rating === 'HIGH' ? 'bg-orange-500/10 border-orange-500/20 text-orange-400' : ''}
                    ${securityRisk.rating === 'CRITICAL' ? 'bg-red-500/10 border-red-500/20 text-red-400' : ''}
                  `}>
                    {securityRisk.rating}
                  </Badge>
                </div>

                {/* Vulnerability Breakdown */}
                {securityRisk.scan_coverage?.vulnerabilities && (
                  <div className="grid grid-cols-4 gap-4 pt-3 border-t">
                    <div>
                      <p className="text-xs text-muted-foreground mb-1">Critical</p>
                      <p className="text-lg font-semibold text-red-400">
                        {securityRisk.scan_coverage.vulnerabilities.critical}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground mb-1">High</p>
                      <p className="text-lg font-semibold text-orange-400">
                        {securityRisk.scan_coverage.vulnerabilities.high}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground mb-1">Medium</p>
                      <p className="text-lg font-semibold text-yellow-400">
                        {securityRisk.scan_coverage.vulnerabilities.medium}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground mb-1">Low</p>
                      <p className="text-lg font-semibold">
                        {securityRisk.scan_coverage.vulnerabilities.low}
                      </p>
                    </div>
                  </div>
                )}
              </div>

              {/* Risk Factors */}
              {securityRisk.risk_factors?.length > 0 && (
                <div className="space-y-2">
                  <p className="text-sm font-medium">Risk Factors</p>
                  {securityRisk.risk_factors.map((factor: string, i: number) => (
                    <div
                      key={i}
                      className="flex items-start gap-2 p-3 rounded-lg bg-orange-500/5 border border-orange-500/10"
                    >
                      <AlertTriangle className="w-4 h-4 text-orange-400 mt-0.5 flex-shrink-0" />
                      <p className="text-sm text-foreground">{factor}</p>
                    </div>
                  ))}
                </div>
              )}

              {/* Remediation Steps */}
              {securityRisk.remediation_steps?.length > 0 && (
                <div className="space-y-2">
                  <p className="text-sm font-medium">Recommended Actions</p>
                  {securityRisk.remediation_steps.map((step: string, i: number) => (
                    <div
                      key={i}
                      className="flex items-start gap-2 p-3 rounded-lg bg-blue-500/5 border border-blue-500/10"
                    >
                      <CheckCircle2 className="w-4 h-4 text-blue-400 mt-0.5 flex-shrink-0" />
                      <p className="text-sm text-foreground">{step}</p>
                    </div>
                  ))}
                </div>
              )}

              {/* Actionable Recommendations */}
              {securityRisk.actionable_recommendations?.length > 0 && (
                <div className="space-y-2">
                  <p className="text-sm font-medium flex items-center gap-2">
                    <Target className="w-4 h-4" />
                    Quick Actions
                  </p>
                  {securityRisk.actionable_recommendations.map((rec: any) => (
                    <div
                      key={rec.id}
                      className="flex items-center justify-between p-3 rounded-lg bg-muted/50 border"
                    >
                      <div className="flex-1">
                        <p className="text-sm font-medium">{rec.title}</p>
                        <p className="text-xs text-muted-foreground mt-1">
                          {rec.description}
                        </p>
                      </div>
                      <ActionButton
                        recommendation={rec}
                        onSuccess={() => {
                          refetchSecurity();
                        }}
                      />
                    </div>
                  ))}
                </div>
              )}

              {/* Scan Info */}
              {securityRisk.scan_coverage && (
                <div className="flex items-center gap-4 p-3 rounded-lg bg-muted/30 text-xs text-muted-foreground">
                  <span>Last scan: {securityRisk.scan_coverage.scan_age_days} days ago</span>
                  <span>•</span>
                  <span>Total scans: {securityRisk.scan_coverage.total_scans}</span>
                  <span>•</span>
                  <span>Confidence: {securityRisk.confidence}</span>
                </div>
              )}
            </div>
          )}
        </div>
      </AnimatedCard>
    </div>
  );
}
