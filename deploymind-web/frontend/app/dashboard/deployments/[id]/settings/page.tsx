"use client";

import { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { api } from '@/lib/api';
import {
  ArrowLeft, Plus, Trash2, Eye, EyeOff, Key, Lock, Save
} from 'lucide-react';
import { motion } from 'framer-motion';

export default function DeploymentSettingsPage() {
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [newVar, setNewVar] = useState({ key: '', value: '', is_secret: false });
  const [showSecrets, setShowSecrets] = useState<Record<number, boolean>>({});

  const { data: envVars, isLoading } = useQuery({
    queryKey: ['env-vars', params.id],
    queryFn: async () => {
      const response = await api.deployments.listEnvVars(params.id as string);
      return response.data;
    },
  });

  const createMutation = useMutation({
    mutationFn: async (data: { key: string; value: string; is_secret: boolean }) => {
      const response = await api.deployments.createEnvVar(params.id as string, data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['env-vars', params.id] });
      setNewVar({ key: '', value: '', is_secret: false });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (envId: number) => {
      await api.deployments.deleteEnvVar(params.id as string, envId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['env-vars', params.id] });
    },
  });

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault();
    if (newVar.key && newVar.value) {
      createMutation.mutate(newVar);
    }
  };

  const toggleShowSecret = (id: number) => {
    setShowSecrets(prev => ({ ...prev, [id]: !prev[id] }));
  };

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Button
          variant="ghost"
          size="icon"
          className="hover:bg-white/5"
          onClick={() => router.push(`/dashboard/deployments/${params.id}`)}
        >
          <ArrowLeft className="w-5 h-5" />
        </Button>

        <div>
          <h2 className="text-3xl font-semibold tracking-tight">Deployment Settings</h2>
          <p className="text-muted-foreground mt-1">
            Manage environment variables for this deployment
          </p>
        </div>
      </div>

      {/* Add New Variable */}
      <Card className="relative overflow-hidden border border-border/50">
        <div className="absolute inset-0 bg-gradient-to-br from-primary/5 to-transparent" />

        <form onSubmit={handleCreate} className="relative p-6 space-y-4">
          <div className="flex items-center gap-2 mb-4">
            <Plus className="w-5 h-5 text-primary" />
            <h3 className="text-lg font-semibold">Add Environment Variable</h3>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="key">Key</Label>
              <Input
                id="key"
                placeholder="DATABASE_URL"
                value={newVar.key}
                onChange={(e) => setNewVar({ ...newVar, key: e.target.value })}
                className="font-mono"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="value">Value</Label>
              <Input
                id="value"
                type={newVar.is_secret ? 'password' : 'text'}
                placeholder="postgres://..."
                value={newVar.value}
                onChange={(e) => setNewVar({ ...newVar, value: e.target.value })}
                className="font-mono"
              />
            </div>
          </div>

          <div className="flex items-center justify-between">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={newVar.is_secret}
                onChange={(e) => setNewVar({ ...newVar, is_secret: e.target.checked })}
                className="w-4 h-4 rounded border-border"
              />
              <span className="text-sm text-muted-foreground flex items-center gap-1.5">
                <Lock className="w-3.5 h-3.5" />
                Mark as secret
              </span>
            </label>

            <Button
              type="submit"
              className="gap-2"
              disabled={!newVar.key || !newVar.value || createMutation.isPending}
            >
              <Plus className="w-4 h-4" />
              Add Variable
            </Button>
          </div>
        </form>
      </Card>

      {/* Environment Variables List */}
      <Card className="relative overflow-hidden border border-border/50">
        <div className="p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Key className="w-5 h-5 text-muted-foreground" />
              <h3 className="text-lg font-semibold">Environment Variables</h3>
            </div>
            <Badge variant="outline">
              {envVars?.length || 0} variables
            </Badge>
          </div>

          {isLoading ? (
            <p className="text-sm text-muted-foreground">Loading...</p>
          ) : envVars && envVars.length > 0 ? (
            <div className="space-y-2">
              {envVars.map((envVar: any) => (
                <motion.div
                  key={envVar.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="flex items-center gap-3 p-4 rounded-lg bg-muted/30 hover:bg-muted/50 transition-colors group"
                >
                  {/* Secret indicator */}
                  {envVar.is_secret && (
                    <Lock className="w-4 h-4 text-yellow-500 flex-shrink-0" />
                  )}

                  {/* Key */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-sm font-medium truncate">
                        {envVar.key}
                      </span>
                      {envVar.is_secret && (
                        <Badge variant="outline" className="text-xs bg-yellow-500/10 border-yellow-500/20 text-yellow-500">
                          SECRET
                        </Badge>
                      )}
                    </div>
                    <p className="font-mono text-xs text-muted-foreground mt-1">
                      {envVar.is_secret && !showSecrets[envVar.id]
                        ? envVar.value
                        : envVar.value}
                    </p>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                    {envVar.is_secret && (
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                        onClick={() => toggleShowSecret(envVar.id)}
                      >
                        {showSecrets[envVar.id] ? (
                          <EyeOff className="w-4 h-4" />
                        ) : (
                          <Eye className="w-4 h-4" />
                        )}
                      </Button>
                    )}

                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 text-red-400 hover:text-red-300 hover:bg-red-500/10"
                      onClick={() => deleteMutation.mutate(envVar.id)}
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </div>
                </motion.div>
              ))}
            </div>
          ) : (
            <div className="text-center py-12 text-muted-foreground">
              <Key className="w-12 h-12 mx-auto mb-3 opacity-50" />
              <p className="text-sm">No environment variables configured</p>
              <p className="text-xs mt-1">Add your first variable above</p>
            </div>
          )}
        </div>
      </Card>

      {/* Help */}
      <Card className="p-6 bg-muted/50 border-dashed">
        <h3 className="font-semibold mb-2">Environment Variables Guide</h3>
        <ul className="text-sm text-muted-foreground space-y-1">
          <li>• Use secrets for sensitive data like API keys, passwords, and tokens</li>
          <li>• Variables are injected at deployment time</li>
          <li>• Changes require redeployment to take effect</li>
        </ul>
      </Card>
    </div>
  );
}
