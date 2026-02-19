"use client";

import { useState } from 'react';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Plus, Trash2, Key, Eye, EyeOff, AlertTriangle } from 'lucide-react';
import { WizardStep } from '../wizard-step';
import { Card } from '@/components/ui/card';

interface EnvironmentStepProps {
  data: {
    environment_variables: Array<{ key: string; value: string; isSecret: boolean }>;
  };
  onChange: (data: any) => void;
  onNext: () => void;
  onBack: () => void;
}

export function EnvironmentStep({ data, onChange, onNext, onBack }: EnvironmentStepProps) {
  const [showSecrets, setShowSecrets] = useState<{ [key: number]: boolean }>({});

  const addVariable = () => {
    onChange({
      ...data,
      environment_variables: [
        ...data.environment_variables,
        { key: '', value: '', isSecret: false },
      ],
    });
  };

  const removeVariable = (index: number) => {
    onChange({
      ...data,
      environment_variables: data.environment_variables.filter((_, i) => i !== index),
    });
  };

  const updateVariable = (index: number, field: string, value: any) => {
    const updated = [...data.environment_variables];
    updated[index] = { ...updated[index], [field]: value };
    onChange({ ...data, environment_variables: updated });
  };

  const addCommonVariable = (key: string, isSecret: boolean = false) => {
    onChange({
      ...data,
      environment_variables: [
        ...data.environment_variables,
        { key, value: '', isSecret },
      ],
    });
  };

  const toggleSecretVisibility = (index: number) => {
    setShowSecrets({ ...showSecrets, [index]: !showSecrets[index] });
  };

  return (
    <WizardStep
      title="Environment Variables"
      description="Configure environment variables for your application"
      onNext={onNext}
      onBack={onBack}
      nextLabel="Continue"
    >
      {/* Common Variables */}
      <div className="space-y-2">
        <Label className="text-xs text-muted-foreground">Quick Add Common Variables:</Label>
        <div className="flex flex-wrap gap-2">
          {[
            { key: 'NODE_ENV', secret: false },
            { key: 'PORT', secret: false },
            { key: 'DATABASE_URL', secret: true },
            { key: 'API_KEY', secret: true },
            { key: 'SECRET_KEY', secret: true },
            { key: 'REDIS_URL', secret: true },
          ].map((variable) => (
            <Badge
              key={variable.key}
              variant="outline"
              className="cursor-pointer hover:bg-primary/20"
              onClick={() => addCommonVariable(variable.key, variable.secret)}
            >
              <Plus className="w-3 h-3 mr-1" />
              {variable.key}
            </Badge>
          ))}
        </div>
      </div>

      {/* Variables List */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <Label>Environment Variables ({data.environment_variables.length})</Label>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={addVariable}
            className="gap-2"
          >
            <Plus className="w-4 h-4" />
            Add Variable
          </Button>
        </div>

        {data.environment_variables.length === 0 ? (
          <Card className="p-8 text-center border-dashed">
            <Key className="w-12 h-12 mx-auto mb-3 text-muted-foreground opacity-50" />
            <p className="text-sm text-muted-foreground mb-4">
              No environment variables configured yet
            </p>
            <Button
              type="button"
              variant="outline"
              onClick={addVariable}
              className="gap-2"
            >
              <Plus className="w-4 h-4" />
              Add Your First Variable
            </Button>
          </Card>
        ) : (
          <div className="space-y-3">
            {data.environment_variables.map((variable, index) => (
              <Card key={index} className="p-4 border border-border/50">
                <div className="grid grid-cols-[1fr_2fr_auto] gap-3 items-start">
                  {/* Key */}
                  <div className="space-y-1">
                    <Label htmlFor={`var-key-${index}`} className="text-xs text-muted-foreground">
                      Key
                    </Label>
                    <Input
                      id={`var-key-${index}`}
                      placeholder="VARIABLE_NAME"
                      value={variable.key}
                      onChange={(e) => updateVariable(index, 'key', e.target.value)}
                      className="font-mono text-sm uppercase"
                    />
                  </div>

                  {/* Value */}
                  <div className="space-y-1">
                    <Label htmlFor={`var-value-${index}`} className="text-xs text-muted-foreground">
                      Value
                    </Label>
                    <div className="relative">
                      <Input
                        id={`var-value-${index}`}
                        type={variable.isSecret && !showSecrets[index] ? 'password' : 'text'}
                        placeholder="value"
                        value={variable.value}
                        onChange={(e) => updateVariable(index, 'value', e.target.value)}
                        className="font-mono text-sm pr-8"
                      />
                      {variable.isSecret && (
                        <button
                          type="button"
                          onClick={() => toggleSecretVisibility(index)}
                          className="absolute right-2 top-2.5 text-muted-foreground hover:text-foreground"
                        >
                          {showSecrets[index] ? (
                            <EyeOff className="w-4 h-4" />
                          ) : (
                            <Eye className="w-4 h-4" />
                          )}
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="space-y-1">
                    <Label className="text-xs text-muted-foreground invisible">Actions</Label>
                    <div className="flex items-center gap-2">
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => updateVariable(index, 'isSecret', !variable.isSecret)}
                        className={variable.isSecret ? 'bg-yellow-500/10 border-yellow-500/20' : ''}
                      >
                        <Key className="w-4 h-4" />
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => removeVariable(index)}
                        className="text-red-400 hover:bg-red-500/10"
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                </div>

                {variable.isSecret && (
                  <div className="mt-2 flex items-center gap-2 text-xs text-yellow-400">
                    <Key className="w-3 h-3" />
                    <span>This variable will be stored securely</span>
                  </div>
                )}
              </Card>
            ))}
          </div>
        )}
      </div>

      {/* Security Warning */}
      <Card className="p-4 bg-yellow-500/10 border-yellow-500/20">
        <div className="flex items-start gap-2">
          <AlertTriangle className="w-4 h-4 text-yellow-400 mt-0.5 flex-shrink-0" />
          <div className="text-sm text-yellow-400">
            <p className="font-medium mb-1">Security Best Practices</p>
            <ul className="text-xs text-yellow-300 space-y-1">
              <li>• Mark sensitive values (passwords, API keys) as secrets</li>
              <li>• Never commit secrets to version control</li>
              <li>• Use unique credentials for each environment</li>
              <li>• Rotate secrets regularly</li>
            </ul>
          </div>
        </div>
      </Card>
    </WizardStep>
  );
}
