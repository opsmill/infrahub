import { useAtomValue } from "jotai";
import { useState } from "react";

import ErrorScreen from "@/shared/components/errors/error-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { Card, CardWithBorder } from "@/shared/components/ui/card";
import { Combobox, ComboboxContent, ComboboxTrigger } from "@/shared/components/ui/combobox";

import { useGetObject } from "@/entities/nodes/object/domain/get-object.query";
import { KindComboboxList } from "@/entities/nodes/object/ui/filters/kind-combobox-list";
import { Permission } from "@/entities/permission/types";
import { schemaKindLabelState } from "@/entities/schema/stores/schemaKindLabel.atom";
import { ModelSchema } from "@/entities/schema/types";

export interface ObjectConvertProps {
  objectId: string;
  objectSchema: ModelSchema;
  permission: Permission;
}

export function ObjectConvert({ objectSchema, objectId }: ObjectConvertProps) {
  const { data: objectDetailsData, isPending, error } = useGetObject({ objectSchema, objectId });
  const [kind, setKind] = useState("");
  const schemaKindLabel = useAtomValue(schemaKindLabelState);

  if (isPending) {
    return <LoadingIndicator className="h-[calc(100vh-10.5rem)]" />;
  }

  if (error) {
    return <ErrorScreen message={error.message} />;
  }

  return (
    <div className="flex gap-2 p-2">
      <Card className="w-1/2 p-0">
        <CardWithBorder.Title className="flex h-19 flex-col">
          <span className="font-normal">SOURCE</span> {objectDetailsData.display_label}
        </CardWithBorder.Title>
        Details
      </Card>

      <Card className="w-1/2 p-0">
        <CardWithBorder.Title className="flex flex-col">
          <span className="font-normal">DESTINATION</span>
          <Combobox defaultOpen>
            <ComboboxTrigger>{kind && schemaKindLabel[kind]}</ComboboxTrigger>
            <ComboboxContent fitTriggerWidth={false}>
              <KindComboboxList
                onSelect={(kind) => {
                  setKind(kind);
                }}
              />
            </ComboboxContent>
          </Combobox>
        </CardWithBorder.Title>
        Form
      </Card>
    </div>
  );
}
