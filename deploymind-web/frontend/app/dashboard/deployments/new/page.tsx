"use client";

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useMutation } from '@tanstack/react-query';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { api } from '@/lib/api';
import { ArrowLeft, Rocket, GitBranch, Server, Loader2 } from 'lucide-react';
import { motion } from 'framer-motion';

export default function NewDeploymentPage() {
  const router = useRouter();
  const [formData, setFormData] = useState({
    repository: '',
    instance_id: '',
    environment: 'production',
  });

  const createDeploymentMutation = useMutation({
    mutationFn: async (data: any) => {
      const response = await api.deployments.create(data);
      return response.data;
    },
    onSuccess: (data) => {
      router.push(`/dashboard/deployments/${data.id}`);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    createDeploymentMutation.mutate(formData);
  };

  return (
    <div className="space-y-6 max-w-2xl">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Button
          variant="ghost"
          size="icon"
          className="hover:bg-white/5"
          onClick={() => router.push('/dashboard/deployments')}
        >
          <ArrowLeft className="w-5 h-5" />
        </Button>

        <div>
          <h2 className="text-3xl font-semibold tracking-tight">New Deployment</h2>
          <p className="text-muted-foreground mt-1">
            Deploy your application to AWS EC2
          </p>
        </div>
      </div>

      {/* Form Card */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
      >
        <Card className="relative overflow-hidden border border-border/50">
          {/* Gradient background */}
          <div className="absolute inset-0 bg-gradient-to-br from-primary/5 to-transparent" />

          <form onSubmit={handleSubmit} className="relative p-6 space-y-6">
            {/* Repository */}
            <div className="space-y-2">
              <Label htmlFor="repository" className="flex items-center gap-2">
                <GitBranch className="w-4 h-4 text-primary" />
                GitHub Repository
              </Label>
              <Input
                id="repository"
                placeholder="owner/repository"
                value={formData.repository}
                onChange={(e) => setFormData({ ...formData, repository: e.target.value })}
                className="font-mono"
                required
              />
              <p className="text-xs text-muted-foreground">
                Example: deploymind/sample-app
              </p>
            </div>

            {/* Instance ID */}
            <div className="space-y-2">
              <Label htmlFor="instance_id" className="flex items-center gap-2">
                <Server className="w-4 h-4 text-primary" />
                EC2 Instance ID
              </Label>
              <Input
                id="instance_id"
                placeholder="i-1234567890abcdef0"
                value={formData.instance_id}
                onChange={(e) => setFormData({ ...formData, instance_id: e.target.value })}
                className="font-mono"
                required
              />
              <p className="text-xs text-muted-foreground">
                AWS EC2 instance ID where the application will be deployed
              </p>
            </div>

            {/* Environment */}
            <div className="space-y-2">
              <Label htmlFor="environment">Environment</Label>
              <select
                id="environment"
                value={formData.environment}
                onChange={(e) => setFormData({ ...formData, environment: e.target.value })}
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <option value="production">Production</option>
                <option value="staging">Staging</option>
                <option value="development">Development</option>
              </select>
            </div>

            {/* Submit Button */}
            <div className="flex gap-3 pt-4">
              <Button
                type="submit"
                className="gap-2 bg-gradient-to-r from-primary to-primary/80 hover:from-primary/90 hover:to-primary/70"
                disabled={createDeploymentMutation.isPending}
              >
                {createDeploymentMutation.isPending ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Creating...
                  </>
                ) : (
                  <>
                    <Rocket className="w-4 h-4" />
                    Deploy Now
                  </>
                )}
              </Button>

              <Button
                type="button"
                variant="outline"
                onClick={() => router.push('/dashboard/deployments')}
                disabled={createDeploymentMutation.isPending}
              >
                Cancel
              </Button>
            </div>

            {/* Error Message */}
            {createDeploymentMutation.isError && (
              <div className="p-4 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
                Failed to create deployment. Please check your input and try again.
              </div>
            )}
          </form>
        </Card>
      </motion.div>

      {/* Help Card */}
      <Card className="p-6 bg-muted/50 border-dashed">
        <h3 className="font-semibold mb-2">Need help?</h3>
        <ul className="text-sm text-muted-foreground space-y-1">
          <li>• Make sure your GitHub repository is accessible</li>
          <li>• EC2 instance must be running and accessible</li>
          <li>• Security groups should allow inbound traffic</li>
        </ul>
      </Card>
    </div>
  );
}
