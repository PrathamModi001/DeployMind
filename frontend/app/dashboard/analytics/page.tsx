"use client";

import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { api } from '@/lib/api';
import { BarChart, Bar, LineChart, Line, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

const COLORS = ['#A78BFA', '#60A5FA', '#4ADE80', '#FBBF24', '#F87171'];

export default function AnalyticsPage() {
  const { data: overview } = useQuery({
    queryKey: ['analytics', 'overview'],
    queryFn: async () => {
      const response = await api.analytics.overview(30);
      return response.data;
    },
  });

  const { data: timeline } = useQuery({
    queryKey: ['analytics', 'timeline'],
    queryFn: async () => {
      const response = await api.analytics.timeline(7);
      return response.data;
    },
  });

  const { data: performance } = useQuery({
    queryKey: ['analytics', 'performance'],
    queryFn: async () => {
      const response = await api.analytics.performance();
      return response.data;
    },
  });

  // Transform data for charts
  const statusData = overview?.deployments_by_status
    ? Object.entries(overview.deployments_by_status).map(([name, value]) => ({
        name,
        value,
      }))
    : [];

  const environmentData = overview?.deployments_by_environment
    ? Object.entries(overview.deployments_by_environment).map(([name, value]) => ({
        name: name.charAt(0).toUpperCase() + name.slice(1),
        value,
      }))
    : [];

  const timelineData = timeline?.timeline || [];

  const buildTimeData = performance?.build_times_by_language
    ? Object.entries(performance.build_times_by_language).map(([language, time]: [string, any]) => ({
        language: language.charAt(0).toUpperCase() + language.slice(1),
        seconds: typeof time === 'object' ? time.avg || time.value || 0 : time,
      }))
    : [];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-semibold tracking-tight">Analytics</h2>
        <p className="text-muted-foreground mt-2">
          Insights and metrics for your deployments
        </p>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Total Deployments</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-semibold">{overview?.total_deployments || 0}</div>
            <p className="text-xs text-muted-foreground mt-1">Last 30 days</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Success Rate</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-semibold text-primary">
              {overview?.success_rate?.toFixed(1) || 0}%
            </div>
            <p className="text-xs text-muted-foreground mt-1">Overall performance</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Avg Duration</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-semibold">
              {Math.floor((overview?.average_duration_seconds || 0) / 60)}m
            </div>
            <p className="text-xs text-muted-foreground mt-1">Per deployment</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Active Deployments</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-semibold">
              {overview?.deployments_by_status?.DEPLOYED || 0}
            </div>
            <p className="text-xs text-muted-foreground mt-1">Currently running</p>
          </CardContent>
        </Card>
      </div>

      {/* Charts Row 1 */}
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Deployment Timeline</CardTitle>
            <CardDescription>Deployments over the last 7 days</CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={timelineData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#404040" />
                <XAxis
                  dataKey="date"
                  stroke="#A3A3A3"
                  tick={{ fill: '#A3A3A3' }}
                />
                <YAxis
                  stroke="#A3A3A3"
                  tick={{ fill: '#A3A3A3' }}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#2A2A2A',
                    border: '1px solid #404040',
                    borderRadius: '8px',
                    color: '#E5E5E5',
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="count"
                  stroke="#A78BFA"
                  strokeWidth={2}
                  dot={{ fill: '#A78BFA', r: 4 }}
                  activeDot={{ r: 6 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Deployments by Status</CardTitle>
            <CardDescription>Distribution of deployment outcomes</CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={statusData}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ name, percent }) => `${name} ${((percent || 0) * 100).toFixed(0)}%`}
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {statusData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#2A2A2A',
                    border: '1px solid #404040',
                    borderRadius: '8px',
                    color: '#E5E5E5',
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      {/* Charts Row 2 */}
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Build Times by Language</CardTitle>
            <CardDescription>Average build duration per language</CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={buildTimeData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#404040" />
                <XAxis
                  dataKey="language"
                  stroke="#A3A3A3"
                  tick={{ fill: '#A3A3A3' }}
                />
                <YAxis
                  stroke="#A3A3A3"
                  tick={{ fill: '#A3A3A3' }}
                  label={{ value: 'Seconds', angle: -90, position: 'insideLeft', fill: '#A3A3A3' }}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#2A2A2A',
                    border: '1px solid #404040',
                    borderRadius: '8px',
                    color: '#E5E5E5',
                  }}
                  formatter={(value: any) => {
                    if (typeof value === 'object') {
                      return value.avg || value.value || 0;
                    }
                    return value;
                  }}
                />
                <Bar dataKey="seconds" fill="#A78BFA" />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Deployments by Environment</CardTitle>
            <CardDescription>Environment distribution</CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={environmentData} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#404040" />
                <XAxis
                  type="number"
                  stroke="#A3A3A3"
                  tick={{ fill: '#A3A3A3' }}
                />
                <YAxis
                  type="category"
                  dataKey="name"
                  stroke="#A3A3A3"
                  tick={{ fill: '#A3A3A3' }}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#2A2A2A',
                    border: '1px solid #404040',
                    borderRadius: '8px',
                    color: '#E5E5E5',
                  }}
                />
                <Bar dataKey="value" fill="#60A5FA" />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
