"use client";

import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Combobox } from '@/components/ui/combobox';
import { GitBranch, Github, AlertCircle, CheckCircle2, Loader2, RefreshCw } from 'lucide-react';
import { WizardStep } from '../wizard-step';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/button';

interface RepositoryStepProps {
  data: {
    repository: string;
    branch: string;
    commit_sha?: string;
  };
  onChange: (data: any) => void;
  onNext: () => void;
  onBack?: () => void;
}

export function RepositoryStep({ data, onChange, onNext, onBack }: RepositoryStepProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedOwner, setSelectedOwner] = useState('');
  const [selectedRepo, setSelectedRepo] = useState('');

  // Fetch GitHub repositories
  const { data: reposData, isLoading: isLoadingRepos, refetch: refetchRepos } = useQuery({
    queryKey: ['github-repositories', searchQuery],
    queryFn: async () => {
      const response = await api.github.listRepositories(searchQuery);
      return response.data;
    },
    retry: false,
  });

  // Fetch branches for selected repository
  const { data: branchesData, isLoading: isLoadingBranches } = useQuery({
    queryKey: ['github-branches', selectedOwner, selectedRepo],
    queryFn: async () => {
      if (!selectedOwner || !selectedRepo) return { branches: [] };
      const response = await api.github.listBranches(selectedOwner, selectedRepo);
      return response.data;
    },
    enabled: !!(selectedOwner && selectedRepo),
    retry: false,
  });

  // Parse selected repository
  useEffect(() => {
    if (data.repository && data.repository.includes('/')) {
      const [owner, repo] = data.repository.split('/');
      setSelectedOwner(owner);
      setSelectedRepo(repo);
    }
  }, [data.repository]);

  // Prepare repository options for combobox
  const repositoryOptions = reposData?.repositories?.map((repo: any) => ({
    value: repo.full_name,
    label: repo.full_name,
  })) || [];

  // Prepare branch options for combobox
  const branchOptions = branchesData?.branches?.map((branch: any) => ({
    value: branch.name,
    label: branch.name,
  })) || [];

  const isValid = data.repository.includes('/') && data.branch.length > 0;

  return (
    <WizardStep
      title="Select Repository"
      description="Choose the GitHub repository you want to deploy"
      onNext={onNext}
      onBack={onBack}
      isNextDisabled={!isValid}
      showBack={false}
    >
      {/* Repository Selection */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label className="flex items-center gap-2">
            <Github className="w-4 h-4 text-primary" />
            GitHub Repository
          </Label>
          {reposData && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => refetchRepos()}
              className="h-6 px-2"
            >
              <RefreshCw className="w-3 h-3 mr-1" />
              Refresh
            </Button>
          )}
        </div>

        {isLoadingRepos ? (
          <div className="flex items-center justify-center p-8 border rounded-md bg-muted/20">
            <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
            <span className="ml-2 text-sm text-muted-foreground">Loading your repositories...</span>
          </div>
        ) : reposData?.repositories?.length > 0 ? (
          <Combobox
            value={data.repository}
            onValueChange={(value) => {
              onChange({ ...data, repository: value, branch: '' });
            }}
            options={repositoryOptions}
            placeholder="Select a repository..."
            searchPlaceholder="Search repositories..."
            emptyText="No repositories found."
          />
        ) : (
          <div className="space-y-3">
            <div className="p-4 rounded-lg bg-yellow-500/10 border border-yellow-500/20">
              <div className="flex items-start gap-2">
                <AlertCircle className="w-4 h-4 text-yellow-400 mt-0.5 flex-shrink-0" />
                <div className="text-sm text-yellow-400">
                  <p className="font-medium mb-1">No repositories found</p>
                  <p className="text-xs text-yellow-300">
                    Make sure you've connected your GitHub account and have repositories available.
                  </p>
                </div>
              </div>
            </div>

            {/* Manual Input Fallback */}
            <div>
              <Label className="text-sm text-muted-foreground mb-2">Or enter manually:</Label>
              <Input
                placeholder="owner/repository"
                value={data.repository}
                onChange={(e) => onChange({ ...data, repository: e.target.value })}
                className="font-mono"
              />
              <p className="text-xs text-muted-foreground mt-1">
                Format: owner/repository (e.g., facebook/react)
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Branch Selection */}
      {data.repository && (
        <div className="space-y-2">
          <Label className="flex items-center gap-2">
            <GitBranch className="w-4 h-4 text-primary" />
            Branch
          </Label>

          {isLoadingBranches ? (
            <div className="flex items-center p-3 border rounded-md bg-muted/20">
              <Loader2 className="w-4 h-4 animate-spin text-muted-foreground mr-2" />
              <span className="text-sm text-muted-foreground">Loading branches...</span>
            </div>
          ) : branchOptions.length > 0 ? (
            <Combobox
              value={data.branch}
              onValueChange={(value) => onChange({ ...data, branch: value })}
              options={branchOptions}
              placeholder="Select a branch..."
              searchPlaceholder="Search branches..."
              emptyText="No branches found."
            />
          ) : (
            <Input
              placeholder="main"
              value={data.branch}
              onChange={(e) => onChange({ ...data, branch: e.target.value })}
              className="font-mono"
            />
          )}

          {/* Common Branches Quick Select */}
          {branchOptions.length === 0 && (
            <div className="space-y-2">
              <Label className="text-xs text-muted-foreground">Quick Select:</Label>
              <div className="flex gap-2">
                {['main', 'master', 'develop', 'staging'].map((branch) => (
                  <Badge
                    key={branch}
                    variant="outline"
                    className="cursor-pointer hover:bg-primary/20"
                    onClick={() => onChange({ ...data, branch })}
                  >
                    {branch}
                  </Badge>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Optional: Commit SHA */}
      {data.repository && data.branch && (
        <div className="space-y-2">
          <Label htmlFor="commit_sha" className="flex items-center gap-2 text-muted-foreground">
            Commit SHA (Optional)
          </Label>
          <Input
            id="commit_sha"
            placeholder="Leave empty for latest commit"
            value={data.commit_sha || ''}
            onChange={(e) => onChange({ ...data, commit_sha: e.target.value })}
            className="font-mono text-sm"
          />
          <p className="text-xs text-muted-foreground">
            Deploy a specific commit (leave empty for latest)
          </p>
        </div>
      )}

      {/* Success Indicator */}
      {isValid && (
        <div className="p-4 rounded-lg bg-green-500/10 border border-green-500/20">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-green-400" />
            <div className="text-sm text-green-400">
              <p className="font-medium">Repository configured</p>
              <p className="text-xs text-green-300 mt-0.5">
                Ready to deploy {data.repository} from {data.branch} branch
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Info Box */}
      <div className="p-4 rounded-lg bg-blue-500/10 border border-blue-500/20">
        <div className="flex items-start gap-2">
          <AlertCircle className="w-4 h-4 text-blue-400 mt-0.5 flex-shrink-0" />
          <div className="text-sm text-blue-400">
            <p className="font-medium mb-1">Repository Access</p>
            <p className="text-xs text-blue-300">
              Your GitHub token must have access to this repository. The repository will be
              cloned and built during deployment.
            </p>
          </div>
        </div>
      </div>
    </WizardStep>
  );
}
