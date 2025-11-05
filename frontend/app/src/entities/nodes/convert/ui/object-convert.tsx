import { Icon } from "@iconify-icon/react";
import { useState } from "react";

import { Row } from "@/shared/components/container";
import ErrorScreen from "@/shared/components/errors/error-screen";
import Content from "@/shared/components/layout/content";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { Badge } from "@/shared/components/ui/badge";
import { Card, CardWithBorder } from "@/shared/components/ui/card";
import { Combobox, ComboboxContent, ComboboxTrigger } from "@/shared/components/ui/combobox";

import ConvertForm from "@/entities/nodes/convert/ui/convert-form";
import { TargetSchemaComboboxList } from "@/entities/nodes/convert/ui/target-schema-combobox-list";
import { useGetObject } from "@/entities/nodes/object/domain/get-object.query";
import { ObjectDetailsContent } from "@/entities/nodes/object/ui/object-details-content";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
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
    <Content.Card className="flex flex-col">
      <Content.CardTitle
        title="Object convert type"
        description={
          <span>
            Converting <strong>{getNodeLabel(objectDetailsData)}</strong> from{" "}
            <strong>{objectSchema.label}</strong> to <strong>{targetSchema?.label ?? "..."}</strong>
          </span>
        }
      />

      <div className="grid grid-cols-2 gap-2 overflow-auto p-2" data-testid="convert-source">
        <Card className="col-span-0 p-0">
          <CardWithBorder.Title>
            <h3 className="font-normal">SOURCE</h3>
            <h4 className="leading-10">{objectSchema.label}</h4>
          </CardWithBorder.Title>

          <ObjectDetailsContent
            schema={objectSchema}
            objectDetailsData={objectDetailsData}
            permission={permission}
          />
        </Card>

        <Card className="col-span-1 p-0">
          <CardWithBorder.Title>
            <h3 className="font-normal">DESTINATION</h3>
            <Combobox open={isOpen} onOpenChange={setIsOpen}>
              <ComboboxTrigger>
                {targetSchema ? (
                  <Row className="grow">
                    <span className="truncate font-semibold">{targetSchema.label}</span>
                    <Badge className="ml-auto font-medium">{targetSchema.namespace}</Badge>
                  </Row>
                ) : (
                  "Select target object type"
                )}
              </ComboboxTrigger>

              <ComboboxContent portal>
                <TargetSchemaComboboxList
                  onSelect={(newSchema) => {
                    setTargetSchema(newSchema);
                    setIsOpen(false);
                  }}
                />
              </ComboboxContent>
            </Combobox>
          </CardWithBorder.Title>

          {targetSchema ? (
            <ConvertForm
              sourceObject={objectDetailsData}
              sourceSchema={objectSchema}
              targetSchema={targetSchema}
            />
          ) : (
            <div className="col-span-full flex flex-col items-center justify-center py-12 text-stone-500">
              <Icon icon="mdi:table-off" className="mb-2 text-3xl" />
              <div className="font-medium text-lg">No kind selected</div>
              <div className="text-sm">Please select a kind for the conversion target</div>
            </div>
          )}
        </Card>
      </div>
    </Content.Card>
  );
}
