import { Sheet } from "@infrahub/ui";

import { SlideOverTitle } from "@/shared/components/display/slide-over";
import ObjectForm from "@/shared/components/form/object-form";

import type { NodeAttributeWithMetadata } from "@/entities/nodes/object/domain/model/node";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

export interface IpPrefixCreateSheetProps {
  schema: ModelSchema;
  prefix: string | null | undefined;
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
  onSuccess: () => void;
}

function buildPrefixAttribute(prefix: string): NodeAttributeWithMetadata {
  return {
    value: prefix,
    is_default: false,
    is_from_profile: false,
    is_protected: false,
    is_visible: true,
    owner: null,
    source: null,
    updated_at: new Date().toISOString(),
  };
}

export function IpPrefixCreateSheet({
  schema,
  prefix,
  isOpen,
  onOpenChange,
  onSuccess,
}: IpPrefixCreateSheetProps) {
  const kind = schema.kind;

  return (
    <Sheet isOpen={isOpen} onOpenChange={onOpenChange}>
      <SlideOverTitle
        schema={schema}
        currentObjectLabel="New"
        title={`Create ${schema.label}`}
        subtitle={schema.description}
      />
      {typeof kind === "string" && (
        <ObjectForm
          onSuccess={onSuccess}
          currentObject={
            typeof prefix === "string" ? { prefix: buildPrefixAttribute(prefix) } : undefined
          }
          onCancel={() => onOpenChange(false)}
          kind={kind}
        />
      )}
    </Sheet>
  );
}
