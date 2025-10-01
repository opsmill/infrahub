import { Icon } from "@iconify-icon/react";
import { useState } from "react";

import ErrorScreen from "@/shared/components/errors/error-screen";
import ConvertForm from "@/shared/components/form/convert-form";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { Card, CardWithBorder } from "@/shared/components/ui/card";
import { Combobox, ComboboxContent, ComboboxTrigger } from "@/shared/components/ui/combobox";

import { useGetObject } from "@/entities/nodes/object/domain/get-object.query";
import { SchemaComboboxList } from "@/entities/nodes/object/ui/filters/schema-combobox-list";
import { ObjectDetailsContent } from "@/entities/nodes/object/ui/object-details-content";
import type { Permission } from "@/entities/permission/types";
import type { ModelSchema } from "@/entities/schema/types";

export interface ObjectConvertProps {
  objectId: string;
  objectSchema: ModelSchema;
  permission: Permission;
}

export function ObjectConvert({ objectSchema, objectId, permission }: ObjectConvertProps) {
  const { data: objectDetailsData, isPending, error } = useGetObject({ objectSchema, objectId });
  const [targetSchema, setTargetSchema] = useState<ModelSchema | null>(null);
  const [isOpen, setIsOpen] = useState(false);

  if (isPending) {
    return <LoadingIndicator className="h-[calc(100vh-10.5rem)]" />;
  }

  if (error) {
    return <ErrorScreen message={error.message} />;
  }

  if (!objectDetailsData) {
    return <ErrorScreen message="Object not found." />;
  }

  return (
    <div className="flex gap-2 p-2">
      <Card className="w-1/2 rounded p-0">
        <CardWithBorder.Title className="flex h-19 flex-col">
          <span className="font-normal">SOURCE</span>{" "}
          <div className="flex h-full items-center">{objectSchema.label}</div>
        </CardWithBorder.Title>

        <ObjectDetailsContent
          schema={objectSchema}
          objectDetailsData={objectDetailsData}
          permission={permission}
        />
      </Card>

      <Card className="w-1/2 rounded p-0">
        <CardWithBorder.Title className="flex flex-col">
          <span className="font-normal">DESTINATION</span>
          <Combobox open={isOpen} onOpenChange={setIsOpen}>
            <ComboboxTrigger>
              {targetSchema ? targetSchema.label : "Select destination kind"}
            </ComboboxTrigger>
            <ComboboxContent fitTriggerWidth={false}>
              <SchemaComboboxList
                onSelect={(newSchema) => {
                  setTargetSchema(newSchema);
                  setIsOpen(false);
                }}
              />
            </ComboboxContent>
          </Combobox>
        </CardWithBorder.Title>

        {!targetSchema && (
          <div className="col-span-full flex flex-col items-center justify-center py-12 text-stone-500">
            <Icon icon="mdi:table-off" className="mb-2 text-3xl" />
            <div className="font-medium text-lg">No kind selected</div>
            <div className="text-sm">Please select a kind for the conversion target</div>
          </div>
        )}

        {targetSchema?.kind && objectSchema.kind && (
          <ConvertForm
            key={targetSchema.kind}
            objectDetailsData={objectDetailsData}
            sourceSchema={objectSchema}
            targetSchema={targetSchema}
          />
        )}
      </Card>
    </div>
  );
}
