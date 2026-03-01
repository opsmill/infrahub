import { useState } from "react";

import { Modal } from "@/shared/components/aria/modal";

import type { WizardState, WizardStep } from "@/entities/config-wizard/types";
import { INITIAL_WIZARD_STATE } from "@/entities/config-wizard/types";
import { WizardStepConfirm } from "@/entities/config-wizard/ui/wizard-step-confirm";
import { WizardStepCredentials } from "@/entities/config-wizard/ui/wizard-step-credentials";
import { WizardStepRepository } from "@/entities/config-wizard/ui/wizard-step-repository";
import { WizardStepSchemas } from "@/entities/config-wizard/ui/wizard-step-schemas";
import { WizardStepWelcome } from "@/entities/config-wizard/ui/wizard-step-welcome";

const STEPS: WizardStep[] = ["welcome", "credentials", "repository", "schemas", "confirm"];

const STEP_LABELS: Record<WizardStep, string> = {
  welcome: "Welcome",
  credentials: "Credentials",
  repository: "Repository",
  schemas: "Schemas",
  confirm: "Confirm",
};

interface ConfigWizardProps {
  isOpen: boolean;
  onDismiss: () => void;
}

export function ConfigWizard({ isOpen, onDismiss }: ConfigWizardProps) {
  const [state, setState] = useState<WizardState>(INITIAL_WIZARD_STATE);

  const currentStepIndex = STEPS.indexOf(state.currentStep);

  const goToStep = (step: WizardStep) => {
    setState((prev) => ({ ...prev, currentStep: step }));
  };

  const handleCredentialsComplete = (credentialId: string) => {
    setState((prev) => ({ ...prev, credentialId, currentStep: "repository" }));
  };

  const handleRepositoryComplete = (
    repositoryId: string,
    repositoryName: string,
    branchName: string
  ) => {
    setState((prev) => ({
      ...prev,
      repositoryId,
      repositoryName,
      branchName,
      currentStep: "schemas",
    }));
  };

  const handleSchemasComplete = (
    selectedSchemaRefs: string[],
    selectedCollectionRefs: string[]
  ) => {
    setState((prev) => ({
      ...prev,
      selectedSchemaRefs,
      selectedCollectionRefs,
      currentStep: "confirm",
    }));
  };

  const handleInstallComplete = () => {
    setState(INITIAL_WIZARD_STATE);
    onDismiss();
  };

  return (
    <Modal isOpen={isOpen} onOpenChange={(open) => !open && onDismiss()} className="w-[640px]">
      <div className="flex flex-col">
        {state.currentStep !== "welcome" && (
          <div className="flex items-center gap-1 border-gray-200 border-b px-6 py-3">
            {STEPS.filter((s) => s !== "welcome").map((step, index) => {
              const stepIndex = index + 1;
              const isActive = STEPS.indexOf(step) === currentStepIndex;
              const isCompleted = STEPS.indexOf(step) < currentStepIndex;

              return (
                <div key={step} className="flex items-center gap-1">
                  {index > 0 && <div className="mx-1 h-px w-6 bg-gray-200" />}
                  <div
                    className={`flex h-6 w-6 items-center justify-center rounded-full text-xs ${
                      isActive
                        ? "bg-custom-blue-700 text-white"
                        : isCompleted
                          ? "bg-green-100 text-green-700"
                          : "bg-gray-100 text-gray-500"
                    }`}
                  >
                    {isCompleted ? "\u2713" : stepIndex}
                  </div>
                  <span
                    className={`text-sm ${isActive ? "font-medium text-gray-900" : "text-gray-500"}`}
                  >
                    {STEP_LABELS[step]}
                  </span>
                </div>
              );
            })}
          </div>
        )}

        {state.currentStep === "welcome" && (
          <WizardStepWelcome onNext={() => goToStep("credentials")} onSkip={onDismiss} />
        )}

        {state.currentStep === "credentials" && (
          <WizardStepCredentials
            onNext={handleCredentialsComplete}
            onBack={() => goToStep("welcome")}
          />
        )}

        {state.currentStep === "repository" && (
          <WizardStepRepository
            credentialId={state.credentialId}
            onNext={handleRepositoryComplete}
            onBack={() => goToStep("credentials")}
          />
        )}

        {state.currentStep === "schemas" && (
          <WizardStepSchemas
            selectedSchemaRefs={state.selectedSchemaRefs}
            selectedCollectionRefs={state.selectedCollectionRefs}
            onNext={handleSchemasComplete}
            onBack={() => goToStep("repository")}
          />
        )}

        {state.currentStep === "confirm" && state.repositoryId && state.repositoryName && (
          <WizardStepConfirm
            repositoryId={state.repositoryId}
            repositoryName={state.repositoryName}
            branchName={state.branchName}
            selectedSchemaRefs={state.selectedSchemaRefs}
            selectedCollectionRefs={state.selectedCollectionRefs}
            onInstallComplete={handleInstallComplete}
            onBack={() => goToStep("schemas")}
          />
        )}
      </div>
    </Modal>
  );
}
