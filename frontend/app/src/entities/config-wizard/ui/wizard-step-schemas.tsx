import { useState } from "react";

import { Button } from "@/shared/components/ui/button";

import { MarketplaceBrowser } from "@/entities/marketplace/ui/marketplace-browser";

interface WizardStepSchemasProps {
  selectedSchemaRefs: string[];
  selectedCollectionRefs: string[];
  onNext: (selectedSchemaRefs: string[], selectedCollectionRefs: string[]) => void;
  onBack: () => void;
}

export function WizardStepSchemas({
  selectedSchemaRefs,
  selectedCollectionRefs,
  onNext,
  onBack,
}: WizardStepSchemasProps) {
  const [selectedSchemas, setSelectedSchemas] = useState<Set<string>>(new Set(selectedSchemaRefs));
  const [selectedCollections, setSelectedCollections] = useState<Set<string>>(
    new Set(selectedCollectionRefs)
  );

  const totalSelected = selectedSchemas.size + selectedCollections.size;

  return (
    <div className="flex flex-col gap-6 p-6">
      <div>
        <h2 className="font-semibold text-gray-900 text-lg">Select Schemas</h2>
        <p className="mt-1 text-gray-600 text-sm">
          Browse the Infrahub Marketplace and select schemas or collections to install in your
          repository.
        </p>
      </div>

      <div className="max-h-[400px] overflow-y-auto">
        <MarketplaceBrowser
          selectedSchemaRefs={selectedSchemas}
          onSelectionChange={setSelectedSchemas}
          selectedCollectionRefs={selectedCollections}
          onCollectionSelectionChange={setSelectedCollections}
        />
      </div>

      <div className="flex justify-between">
        <Button variant="outline" onClick={onBack}>
          Back
        </Button>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => onNext([], [])}>
            Skip
          </Button>
          <Button
            disabled={totalSelected === 0}
            onClick={() => onNext(Array.from(selectedSchemas), Array.from(selectedCollections))}
          >
            Next ({totalSelected} selected)
          </Button>
        </div>
      </div>
    </div>
  );
}
