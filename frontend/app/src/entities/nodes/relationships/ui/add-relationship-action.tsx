import { Button } from "@infrahub/ui";
import type React from "react";
import { useState } from "react";

import SlideOver, { SlideOverTitle } from "@/shared/components/display/slide-over";
import ObjectForm, { type ObjectFormProps } from "@/shared/components/form/object-form";

import type { NodeFieldsWithMetadata } from "@/entities/nodes/types";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

export interface AddRelationshipActionProps {
  peer: string;
  onSuccess?: ObjectFormProps["onSuccess"];
  // Pre-fills the create form (e.g. the common_parent so a created peer satisfies the constraint).
  initialObject?: NodeFieldsWithMetadata;
}

export const AddRelationshipAction: React.FC<AddRelationshipActionProps> = ({
  peer,
  onSuccess,
  initialObject,
}) => {
  const { schema } = useSchema(peer);
  const [open, setOpen] = useState(false);

  if (!schema) return null;

  return (
    <div className="p-2 pt-0">
      <Button
        className="w-full border border-custom-blue-700/20 bg-custom-blue-700/10 text-custom-blue-700 not-data-disabled:data-hovered:bg-custom-blue-700/20"
        onPress={() => setOpen(!open)}
      >
        + Add new <span className="truncate">{schema.label}</span>
      </Button>

      <SlideOver
        title={
          <SlideOverTitle
            schema={schema}
            currentObjectLabel="New"
            title={`Create ${schema.label}`}
            subtitle={schema.description}
          />
        }
        offset={1}
        open={open}
        setOpen={setOpen}
      >
        <ObjectForm
          kind={peer}
          currentObject={initialObject}
          onSuccess={async (newNode) => {
            setOpen(false);
            if (!onSuccess) return;
            await onSuccess(newNode);
          }}
          onCancel={() => setOpen(false)}
          data-testid="new-object-form"
        />
      </SlideOver>
    </div>
  );
};
