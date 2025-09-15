import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { useState } from "react";

import ErrorScreen from "@/shared/components/errors/error-screen";
import ConvertForm from "@/shared/components/form/convert-form";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { Card, CardWithBorder } from "@/shared/components/ui/card";
import { Combobox, ComboboxContent, ComboboxTrigger } from "@/shared/components/ui/combobox";

import { useGetObject } from "@/entities/nodes/object/domain/get-object.query";
import { KindComboboxList } from "@/entities/nodes/object/ui/filters/kind-combobox-list";
import { ObjectDetailsContent } from "@/entities/nodes/object/ui/object-details-content";
import { Permission } from "@/entities/permission/types";
import { schemaKindLabelState } from "@/entities/schema/stores/schemaKindLabel.atom";
import { ModelSchema } from "@/entities/schema/types";

export interface ObjectConvertProps {
  objectId: string;
  objectSchema: ModelSchema;
  permission: Permission;
}

export function ObjectConvert({ objectSchema, objectId, permission }: ObjectConvertProps) {
  const { data: objectDetailsData, isPending, error } = useGetObject({ objectSchema, objectId });
  const [targetKind, setKind] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const schemaKindLabel = useAtomValue(schemaKindLabelState);

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
      <Card className="w-1/2 p-0">
        <CardWithBorder.Title className="flex h-19 flex-col">
          <span className="font-normal">SOURCE</span>{" "}
          <div className="flex h-full items-center">
            {objectDetailsData.display_label ?? objectDetailsData.hfid}
          </div>
        </CardWithBorder.Title>

        <ObjectDetailsContent
          schema={objectSchema}
          objectDetailsData={objectDetailsData}
          permission={permission}
        />
      </Card>

      <Card className="w-1/2 p-0">
        <CardWithBorder.Title className="flex flex-col">
          <span className="font-normal">DESTINATION</span>
          <Combobox open={isOpen} onOpenChange={setIsOpen}>
            <ComboboxTrigger>
              {targetKind ? (schemaKindLabel[targetKind] ?? targetKind) : "Select destination kind"}
            </ComboboxTrigger>
            <ComboboxContent fitTriggerWidth={false}>
              <KindComboboxList
                onSelect={(newKind) => {
                  setKind(newKind);
                  setIsOpen(false);
                }}
              />
            </ComboboxContent>
          </Combobox>
        </CardWithBorder.Title>

        {!targetKind && (
          <div className="col-span-full flex flex-col items-center justify-center py-12 text-stone-500">
            <Icon icon="mdi:table-off" className="mb-2 text-3xl" />
            <div className="font-medium text-lg">No kind selected</div>
            <div className="text-sm">Please select a kind for the convertion target</div>
          </div>
        )}

        {targetKind && objectSchema.kind && (
          <div className="p-2">
            <ConvertForm
              objectDetailsData={objectDetailsData}
              sourceKind={objectSchema.kind}
              targetKind={targetKind}
            />
          </div>
        )}
      </Card>
    </div>
  );
}
