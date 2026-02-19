"use client";

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useMutation } from '@tanstack/react-query';
import { Button } from '@/components/ui/button';
import { api } from '@/lib/api';
import { ArrowLeft, GitBranch, Server, Shield, Key, CheckCircle2, Rocket, Sparkles } from 'lucide-react';
import { WizardContainer } from '@/components/wizard/wizard-container';
import { RepositoryStep } from '@/components/wizard/steps/repository-step';
import { InstanceStep } from '@/components/wizard/steps/instance-step';
import { StrategyStep } from '@/components/wizard/steps/strategy-step';
import { EnvironmentStep } from '@/components/wizard/steps/environment-step';
import { ReviewStep } from '@/components/wizard/steps/review-step';
import { DeployStep } from '@/components/wizard/steps/deploy-step';

const WIZARD_STEPS = [
  {
    id: 'repository',
    title: 'Repository',
    description: 'Source code',
    icon: GitBranch,
  },
  {
    id: 'instance',
    title: 'Instance',
    description: 'Target server',
    icon: Server,
  },
  {
    id: 'strategy',
    title: 'Strategy',
    description: 'Deployment method',
    icon: Shield,
  },
  {
    id: 'environment',
    title: 'Environment',
    description: 'Variables',
    icon: Key,
  },
  {
    id: 'review',
    title: 'Review',
    description: 'Final check',
    icon: CheckCircle2,
  },
  {
    id: 'deploy',
    title: 'Deploy',
    description: 'Launch',
    icon: Rocket,
  },
];

export default function NewDeploymentPage() {
  const router = useRouter();
  const [currentStep, setCurrentStep] = useState(0);
  const [deploymentId, setDeploymentId] = useState<string>('');
  const [deploymentStatus, setDeploymentStatus] = useState<string>('pending');

  // Wizard data state
  const [wizardData, setWizardData] = useState({
    repository: {
      repository: '',
      branch: 'main',
      commit_sha: '',
    },
    instance: {
      instance_id: '',
      instance_type: undefined as string | undefined,
      region: 'us-east-1',
    },
    strategy: {
      strategy: 'rolling',
    },
    environment: {
      environment_variables: [] as Array<{ key: string; value: string; isSecret: boolean }>,
    },
    review: {
      enable_security_scan: true,
      auto_rollback: true,
      health_check_enabled: true,
    },
  });

  // Create deployment mutation
  const createDeploymentMutation = useMutation({
    mutationFn: async () => {
      // Prepare deployment data
      const deploymentData = {
        repository: wizardData.repository.repository,
        branch: wizardData.repository.branch,
        commit_sha: wizardData.repository.commit_sha || undefined,
        instance_id: wizardData.instance.instance_id || undefined,
        instance_type: wizardData.instance.instance_type,
        region: wizardData.instance.region,
        strategy: wizardData.strategy.strategy,
        environment: 'production',
        environment_variables: wizardData.environment.environment_variables.reduce(
          (acc, { key, value }) => {
            if (key && value) {
              acc[key] = value;
            }
            return acc;
          },
          {} as Record<string, string>
        ),
        enable_security_scan: wizardData.review.enable_security_scan,
        auto_rollback: wizardData.review.auto_rollback,
      };

      const response = await api.deployments.create(deploymentData);
      return response.data;
    },
    onSuccess: (data) => {
      setDeploymentId(data.id);
      setDeploymentStatus(data.status);
      setCurrentStep(5); // Move to deploy step

      // Poll for status updates (in real app, use WebSocket)
      const pollInterval = setInterval(async () => {
        try {
          const statusResponse = await api.deployments.get(data.id);
          setDeploymentStatus(statusResponse.data.status);

          // Stop polling when deployment is complete or failed
          if (['deployed', 'failed', 'security_failed', 'build_failed'].includes(statusResponse.data.status)) {
            clearInterval(pollInterval);
          }
        } catch (error) {
          clearInterval(pollInterval);
        }
      }, 2000);
    },
    onError: (error) => {
      console.error('Deployment failed:', error);
    },
  });

  const handleNext = () => {
    if (currentStep < WIZARD_STEPS.length - 1) {
      if (currentStep === 4) {
        // Review step - trigger deployment
        createDeploymentMutation.mutate();
      } else {
        setCurrentStep(currentStep + 1);
      }
    }
  };

  const handleBack = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
    }
  };

  const updateStepData = (stepKey: string, data: any) => {
    setWizardData((prev) => ({
      ...prev,
      [stepKey]: data,
    }));
  };

  const renderStep = () => {
    switch (currentStep) {
      case 0:
        return (
          <RepositoryStep
            data={wizardData.repository}
            onChange={(data) => updateStepData('repository', data)}
            onNext={handleNext}
          />
        );
      case 1:
        return (
          <InstanceStep
            data={wizardData.instance}
            repositoryData={wizardData.repository}
            onChange={(data) => updateStepData('instance', data)}
            onNext={handleNext}
            onBack={handleBack}
          />
        );
      case 2:
        return (
          <StrategyStep
            data={wizardData.strategy}
            onChange={(data) => updateStepData('strategy', data)}
            onNext={handleNext}
            onBack={handleBack}
          />
        );
      case 3:
        return (
          <EnvironmentStep
            data={wizardData.environment}
            onChange={(data) => updateStepData('environment', data)}
            onNext={handleNext}
            onBack={handleBack}
          />
        );
      case 4:
        return (
          <ReviewStep
            data={wizardData.review}
            allData={wizardData}
            onChange={(data) => updateStepData('review', data)}
            onNext={handleNext}
            onBack={handleBack}
            isDeploying={createDeploymentMutation.isPending}
          />
        );
      case 5:
        return (
          <DeployStep
            deploymentId={deploymentId}
            status={deploymentStatus}
            onViewDetails={() => router.push(`/dashboard/deployments/${deploymentId}`)}
          />
        );
      default:
        return null;
    }
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
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

        <div className="flex-1">
          <h2 className="text-3xl font-semibold tracking-tight flex items-center gap-3">
            <Sparkles className="w-8 h-8 text-primary" />
            New Deployment
          </h2>
          <p className="text-muted-foreground mt-1">
            Deploy your application with AI-powered recommendations
          </p>
        </div>
      </div>

      {/* Wizard */}
      <WizardContainer steps={WIZARD_STEPS} currentStep={currentStep}>
        {renderStep()}
      </WizardContainer>
    </div>
  );
}
