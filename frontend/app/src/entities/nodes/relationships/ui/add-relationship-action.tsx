import type React from "react";
import { useState } from "react";

import { Button } from "@/shared/components/buttons/button-primitive";
import SlideOver, { SlideOverTitle } from "@/shared/components/display/slide-over";
import ObjectForm, { type ObjectFormProps } from "@/shared/components/form/object-form";

import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

export interface AddRelationshipActionProps {
  peer: string;
  onSuccess?: ObjectFormProps["onSuccess"];
}

export const AddRelationshipAction: React.FC<AddRelationshipActionProps> = ({
  peer,
  onSuccess,
}) => {
  const { schema } = useSchema(peer);
  const [open, setOpen] = useState(false);

  if (!schema) return null;

  return (
    <div className="p-2 pt-0">
      <Button
        className="w-full border border-custom-blue-700/20 bg-custom-blue-700/10 text-custom-blue-700 enabled:hover:bg-custom-blue-700/20"
        onClick={() => setOpen(!open)}
      >
        + Add new <span className="ml-1 truncate">{schema.label}</span>
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
