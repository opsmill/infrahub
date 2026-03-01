import { useState } from "react";
import { toast } from "react-toastify";

import { Button } from "@/shared/components/ui/button";
import { Card } from "@/shared/components/ui/card";

import { installMarketplaceSchemas } from "@/entities/marketplace/api/marketplace.queries";

interface WizardStepConfirmProps {
  repositoryId: string;
  repositoryName: string;
  branchName: string;
  selectedSchemaRefs: string[];
  selectedCollectionRefs: string[];
  onInstallComplete: () => void;
  onBack: () => void;
}

export function WizardStepConfirm({
  repositoryId,
  repositoryName,
  branchName,
  selectedSchemaRefs,
  selectedCollectionRefs,
  onInstallComplete,
  onBack,
}: WizardStepConfirmProps) {
  const [isInstalling, setIsInstalling] = useState(false);

  const handleInstall = async () => {
    setIsInstalling(true);
    try {
      const result = await installMarketplaceSchemas({
        repositoryId,
        schemaIds: selectedSchemaRefs,
        collectionIds: selectedCollectionRefs,
        branchName,
      });

      if (result.task_id) {
        toast.success("Schema installation started. You can track progress in the task list.");
        onInstallComplete();
      } else {
        const errorMsg = (result as Record<string, unknown>).detail ?? JSON.stringify(result);
        toast.error(`Install failed: ${errorMsg}`);
      }
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Failed to start schema installation");
    } finally {
      setIsInstalling(false);
    }
  };

  const hasSchemas = selectedSchemaRefs.length > 0;
  const hasCollections = selectedCollectionRefs.length > 0;
  const hasSelections = hasSchemas || hasCollections;

  return (
    <div className="flex flex-col gap-6 p-6">
      <div>
        <h2 className="font-semibold text-gray-900 text-lg">Confirm Setup</h2>
        <p className="mt-1 text-gray-600 text-sm">
          Review your configuration before completing the setup.
        </p>
      </div>

      <Card className="space-y-3 shadow-xs">
        <div>
          <p className="font-medium text-gray-900 text-sm">Repository</p>
          <p className="text-gray-600 text-sm">{repositoryName}</p>
        </div>
        <div>
          <p className="font-medium text-gray-900 text-sm">Branch</p>
          <p className="text-gray-600 text-sm">{branchName}</p>
        </div>
        {hasSchemas && (
          <div>
            <p className="font-medium text-gray-900 text-sm">Schemas to Install</p>
            <p className="text-gray-600 text-sm">
              {selectedSchemaRefs.length} schema
              {selectedSchemaRefs.length !== 1 ? "s" : ""} selected
            </p>
          </div>
        )}
        {hasCollections && (
          <div>
            <p className="font-medium text-gray-900 text-sm">Collections to Install</p>
            <p className="text-gray-600 text-sm">
              {selectedCollectionRefs.length} collection
              {selectedCollectionRefs.length !== 1 ? "s" : ""} selected
            </p>
          </div>
        )}
      </Card>

      <div className="flex justify-between">
        <Button variant="outline" onClick={onBack}>
          Back
        </Button>
        {hasSelections ? (
          <Button disabled={isInstalling} onClick={handleInstall}>
            {isInstalling ? "Installing..." : "Install & Finish"}
          </Button>
        ) : (
          <Button onClick={onInstallComplete}>Finish Setup</Button>
        )}
      </div>
    </div>
  );
}
