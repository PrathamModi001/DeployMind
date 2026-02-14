"use client";

import { useQuery } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import { Eye, Plus } from 'lucide-react';

const statusColors = {
  PENDING: 'bg-yellow-500/10 text-yellow-500 border-yellow-500/20',
  BUILDING: 'bg-blue-500/10 text-blue-500 border-blue-500/20',
  DEPLOYING: 'bg-primary/10 text-primary border-primary/20',
  DEPLOYED: 'bg-green-500/10 text-green-500 border-green-500/20',
  FAILED: 'bg-destructive/10 text-destructive border-destructive/20',
  ROLLED_BACK: 'bg-orange-500/10 text-orange-500 border-orange-500/20',
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

  if (isLoading) {
    return <div className="text-muted-foreground">Loading deployments...</div>;
  }

  const deployments = deploymentsData?.deployments || [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-3xl font-semibold tracking-tight">Deployments</h2>
          <p className="text-muted-foreground mt-2">
            Manage and monitor all your deployments
          </p>
        </div>
        <Button className="gap-2">
          <Plus className="h-4 w-4" />
          New Deployment
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>All Deployments</CardTitle>
          <CardDescription>
            {deployments.length} total deployments
          </CardDescription>
        </CardHeader>
        <CardContent>
          {deployments.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              <p className="text-lg mb-2">No deployments yet</p>
              <p className="text-sm">Create your first deployment to get started</p>
            </div>
          ) : (
            <div className="border rounded-lg">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>ID</TableHead>
                    <TableHead>Repository</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Strategy</TableHead>
                    <TableHead>Environment</TableHead>
                    <TableHead>Duration</TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {deployments.map((deployment: any) => (
                    <TableRow key={deployment.id} className="cursor-pointer hover:bg-muted/50">
                      <TableCell className="font-mono text-sm">{deployment.id?.substring(0, 8)}</TableCell>
                      <TableCell className="font-medium">{deployment.repository}</TableCell>
                      <TableCell>
                        <Badge
                          variant="outline"
                          className={statusColors[deployment.status as keyof typeof statusColors] || statusColors.PENDING}
                        >
                          {deployment.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="capitalize">{deployment.strategy || 'rolling'}</TableCell>
                      <TableCell className="capitalize">{deployment.environment || 'production'}</TableCell>
                      <TableCell>
                        {deployment.duration_seconds
                          ? `${Math.floor(deployment.duration_seconds / 60)}m ${deployment.duration_seconds % 60}s`
                          : '-'}
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {deployment.created_at
                          ? new Date(deployment.created_at).toLocaleDateString()
                          : '-'}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => router.push(`/dashboard/deployments/${deployment.id}`)}
                          className="gap-2"
                        >
                          <Eye className="h-4 w-4" />
                          View
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
