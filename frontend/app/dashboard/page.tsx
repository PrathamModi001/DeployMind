"use client";

import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { api } from '@/lib/api';
import { Rocket, CheckCircle2, XCircle, Clock } from 'lucide-react';

export default function DashboardPage() {
  const { data: analytics, isLoading } = useQuery({
    queryKey: ['analytics', 'overview'],
    queryFn: async () => {
      const response = await api.analytics.overview(7);
      return response.data;
    },
  });

  if (isLoading) {
    return <div className="text-muted-foreground">Loading...</div>;
  }

  const stats = [
    {
      name: 'Total Deployments',
      value: analytics?.total_deployments || 0,
      icon: Rocket,
      color: 'text-primary',
    },
    {
      name: 'Success Rate',
      value: `${analytics?.success_rate?.toFixed(1) || 0}%`,
      icon: CheckCircle2,
      color: 'text-primary',
    },
    {
      name: 'Failed',
      value: analytics?.deployments_by_status?.FAILED || 0,
      icon: XCircle,
      color: 'text-destructive',
    },
    {
      name: 'Avg Duration',
      value: `${Math.floor((analytics?.average_duration_seconds || 0) / 60)}m`,
      icon: Clock,
      color: 'text-primary',
    },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-semibold tracking-tight">Dashboard</h2>
        <p className="text-muted-foreground mt-2">
          Overview of your deployment metrics and activity
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => {
          const Icon = stat.icon;
          return (
            <Card key={stat.name}>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  {stat.name}
                </CardTitle>
                <Icon className={`h-4 w-4 ${stat.color}`} />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-semibold">{stat.value}</div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Recent Activity</CardTitle>
          <CardDescription>
            Your latest deployments and their status
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="text-muted-foreground text-center py-8">
            Recent deployments will appear here
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
