"use client";

import { Badge } from '@/components/ui/badge';
import { Card } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import {
  GitBranch, Server, Shield, Key, CheckCircle2,
  AlertTriangle, Info, Lock, Scan
} from 'lucide-react';
import { WizardStep } from '../wizard-step';

interface ReviewStepProps {
  data: {
    enable_security_scan: boolean;
    auto_rollback: boolean;
    health_check_enabled: boolean;
  };
  allData: any;
  onChange: (data: any) => void;
  onNext: () => void;
  onBack: () => void;
  isDeploying: boolean;
}

export function ReviewStep({
  data,
  allData,
  onChange,
  onNext,
  onBack,
  isDeploying
}: ReviewStepProps) {
  return (
    <WizardStep
      title="Review & Deploy"
      description="Review your configuration and deployment settings"
      onNext={onNext}
      onBack={onBack}
      nextLabel={isDeploying ? "Deploying..." : "Deploy Now 🚀"}
      isLoading={isDeploying}
    >
      {/* Configuration Summary */}
      <div className="space-y-4">
        {/* Repository */}
        <Card className="p-4 border border-border/50">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center flex-shrink-0">
              <GitBranch className="w-5 h-5 text-primary" />
            </div>
            <div className="flex-1">
              <Label className="text-sm font-medium">Repository</Label>
              <p className="text-sm text-muted-foreground mt-1">
                <span className="font-mono">{allData.repository.repository}</span>
                {' @ '}
                <Badge variant="outline" className="font-mono">
                  {allData.repository.branch}
                </Badge>
              </p>
              {allData.repository.commit_sha && (
                <p className="text-xs text-muted-foreground mt-1">
                  Commit: <span className="font-mono">{allData.repository.commit_sha.substring(0, 8)}</span>
                </p>
              )}
            </div>
          </div>
        </Card>

        {/* Instance */}
        <Card className="p-4 border border-border/50">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-lg bg-blue-500/10 flex items-center justify-center flex-shrink-0">
              <Server className="w-5 h-5 text-blue-400" />
            </div>
            <div className="flex-1">
              <Label className="text-sm font-medium">Instance</Label>
              <p className="text-sm text-muted-foreground mt-1">
                {allData.instance.instance_type ? (
                  <>
                    Type: <span className="font-mono font-semibold">{allData.instance.instance_type}</span>
                  </>
                ) : (
                  <>
                    Instance ID: <span className="font-mono">{allData.instance.instance_id}</span>
                  </>
                )}
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                Region: {allData.instance.region || 'us-east-1'}
              </p>
            </div>
          </div>
        </Card>

        {/* Strategy */}
        <Card className="p-4 border border-border/50">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-lg bg-green-500/10 flex items-center justify-center flex-shrink-0">
              <Shield className="w-5 h-5 text-green-400" />
            </div>
            <div className="flex-1">
              <Label className="text-sm font-medium">Deployment Strategy</Label>
              <p className="text-sm text-muted-foreground mt-1">
                <Badge variant="outline" className="uppercase">
                  {allData.strategy.strategy.replace('_', ' ')}
                </Badge>
              </p>
            </div>
          </div>
        </Card>

        {/* Environment Variables */}
        <Card className="p-4 border border-border/50">
          <div className="flex items-start gap-3">
            <div className="w-10 h-10 rounded-lg bg-purple-500/10 flex items-center justify-center flex-shrink-0">
              <Key className="w-5 h-5 text-purple-400" />
            </div>
            <div className="flex-1">
              <Label className="text-sm font-medium">Environment Variables</Label>
              <p className="text-sm text-muted-foreground mt-1">
                {allData.environment.environment_variables.length} variables configured
              </p>
              {allData.environment.environment_variables.some((v: any) => v.isSecret) && (
                <div className="flex items-center gap-2 mt-2 text-xs text-yellow-400">
                  <Lock className="w-3 h-3" />
                  <span>
                    {allData.environment.environment_variables.filter((v: any) => v.isSecret).length} secret(s) will be encrypted
                  </span>
                </div>
              )}
            </div>
          </div>
        </Card>
      </div>

      {/* Security & Safety Options */}
      <div className="space-y-3">
        <Label>Security & Safety Options</Label>

        {/* Security Scan */}
        <Card className="p-4 border border-border/50">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Scan className="w-5 h-5 text-primary" />
              <div>
                <p className="text-sm font-medium">Run Security Scan</p>
                <p className="text-xs text-muted-foreground">
                  Scan for vulnerabilities before deployment
                </p>
              </div>
            </div>
            <Switch
              checked={data.enable_security_scan}
              onCheckedChange={(checked) =>
                onChange({ ...data, enable_security_scan: checked })
              }
            />
          </div>
        </Card>

        {/* Auto Rollback */}
        <Card className="p-4 border border-border/50">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Shield className="w-5 h-5 text-green-400" />
              <div>
                <p className="text-sm font-medium">Automatic Rollback</p>
                <p className="text-xs text-muted-foreground">
                  Rollback if health checks fail
                </p>
              </div>
            </div>
            <Switch
              checked={data.auto_rollback}
              onCheckedChange={(checked) =>
                onChange({ ...data, auto_rollback: checked })
              }
            />
          </div>
        </Card>

        {/* Health Checks */}
        <Card className="p-4 border border-border/50">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <CheckCircle2 className="w-5 h-5 text-blue-400" />
              <div>
                <p className="text-sm font-medium">Health Checks</p>
                <p className="text-xs text-muted-foreground">
                  Monitor application health after deployment
                </p>
              </div>
            </div>
            <Switch
              checked={data.health_check_enabled}
              onCheckedChange={(checked) =>
                onChange({ ...data, health_check_enabled: checked })
              }
            />
          </div>
        </Card>
      </div>

      {/* Pre-deployment Checklist */}
      <Card className="p-4 bg-blue-500/10 border-blue-500/20">
        <div className="flex items-start gap-2">
          <Info className="w-4 h-4 text-blue-400 mt-0.5 flex-shrink-0" />
          <div className="text-sm text-blue-400">
            <p className="font-medium mb-2">Pre-deployment Checklist</p>
            <ul className="text-xs text-blue-300 space-y-1.5">
              <li className="flex items-center gap-2">
                <CheckCircle2 className="w-3 h-3" />
                Repository is accessible
              </li>
              <li className="flex items-center gap-2">
                <CheckCircle2 className="w-3 h-3" />
                Instance configuration validated
              </li>
              <li className="flex items-center gap-2">
                <CheckCircle2 className="w-3 h-3" />
                Environment variables configured
              </li>
              {data.enable_security_scan && (
                <li className="flex items-center gap-2">
                  <CheckCircle2 className="w-3 h-3" />
                  Security scan will run before deployment
                </li>
              )}
            </ul>
          </div>
        </div>
      </Card>

      {/* Warning */}
      {!data.auto_rollback && (
        <Card className="p-4 bg-yellow-500/10 border-yellow-500/20">
          <div className="flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-yellow-400 mt-0.5 flex-shrink-0" />
            <div className="text-sm text-yellow-400">
              <p className="font-medium mb-1">Auto-rollback is disabled</p>
              <p className="text-xs text-yellow-300">
                You'll need to manually rollback if the deployment fails. Consider enabling
                auto-rollback for safer deployments.
              </p>
            </div>
          </div>
        </Card>
      )}
    </WizardStep>
  );
}
