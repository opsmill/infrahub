import { Card } from "@infrahub/ui";
import type React from "react";
import { useFormContext, useWatch } from "react-hook-form";

import { Col } from "@/shared/components/container";
import { FormField, FormMessage } from "@/shared/components/ui/form";

import { canNumberPoolHaveAllocationScope } from "@/entities/resource-manager/domain/rules/can-number-pool-have-allocation-scope";
import { NumberPoolAllocationScopeSelect } from "@/entities/resource-manager/ui/number-pool/form/number-pool-allocation-scope-select";
import type { NumberPoolFormData } from "@/entities/resource-manager/ui/number-pool/form/number-pool-form";
import { NumberPoolNodeAttributeSelect } from "@/entities/resource-manager/ui/number-pool/form/number-pool-node-attribute-select";
import { NumberPoolNodeSelect } from "@/entities/resource-manager/ui/number-pool/form/number-pool-node-select";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

const REQUIRED = { required: "Required" };

export interface NumberPoolAllocatesInputProps {
  isReadOnly?: boolean;
}

export function NumberPoolAllocatesInput({ isReadOnly }: NumberPoolAllocatesInputProps) {
  const { control, setValue } = useFormContext<NumberPoolFormData>();
  const [nodeKind, nodeAttribute, allocationScope] = useWatch({
    control,
    name: ["node.value", "node_attribute.value", "allocation_scope.value"],
  });
  const { schema } = useSchema(nodeKind);
  const attributeSchema = schema?.attributes?.find(({ name }) => name === nodeAttribute);

  if (isReadOnly) {
    return (
      <AllocatesCard>
        <AllocatesRow label="Node">
          <span className="font-medium">{schema?.label ?? nodeKind}</span>
        </AllocatesRow>
        <AllocatesRow label="Attribute">
          <span className="font-medium">{attributeSchema?.label ?? nodeAttribute}</span>
        </AllocatesRow>
        <AllocatesRow label="Scoped by">
          {schema && attributeSchema && (
            <NumberPoolAllocationScopeSelect
              isReadOnly
              schema={schema}
              attribute={attributeSchema}
              value={allocationScope ?? []}
            />
          )}
        </AllocatesRow>
      </AllocatesCard>
    );
  }

  return (
    <AllocatesCard>
      <AllocatesRow label="Node" isRequired>
        <FormField
          name="node.value"
          rules={REQUIRED}
          render={({ field, fieldState }) => (
            <Col className="gap-1">
              <NumberPoolNodeSelect
                value={field.value || null}
                isInvalid={fieldState.invalid}
                onChange={(kind) => {
                  field.onChange(kind ?? "");
                  setValue("node_attribute.value", "");
                  setValue("allocation_scope.value", []);
                }}
              />
              <FormMessage />
              {!field.value && (
                <p className="text-foreground-muted text-xs">
                  Pick a node to choose its attribute and scope.
                </p>
              )}
            </Col>
          )}
        />
      </AllocatesRow>

      {nodeKind && (
        <>
          <AllocatesRow label="Attribute" isRequired>
            <FormField
              name="node_attribute.value"
              rules={REQUIRED}
              render={({ field, fieldState }) => (
                <Col className="gap-1">
                  <NumberPoolNodeAttributeSelect
                    schema={schema}
                    value={field.value || null}
                    isInvalid={fieldState.invalid}
                    onChange={(name) => {
                      field.onChange(name ?? "");
                      const nextAttribute = schema?.attributes?.find((a) => a.name === name);
                      setValue(
                        "allocation_scope.value",
                        nextAttribute && canNumberPoolHaveAllocationScope(nextAttribute)
                          ? (allocationScope ?? []).filter((fieldName) => fieldName !== name)
                          : []
                      );
                    }}
                  />
                  <FormMessage />
                </Col>
              )}
            />
          </AllocatesRow>

          {schema && attributeSchema && (
            <AllocatesRow label="Scoped by">
              <FormField
                name="allocation_scope.value"
                render={({ field, fieldState }) => (
                  <Col className="gap-1">
                    <NumberPoolAllocationScopeSelect
                      schema={schema}
                      attribute={attributeSchema}
                      value={field.value ?? []}
                      onChange={field.onChange}
                      isInvalid={fieldState.invalid}
                    />
                    <FormMessage />
                  </Col>
                )}
              />
            </AllocatesRow>
          )}
        </>
      )}
    </AllocatesCard>
  );
}

function AllocatesCard({ children }: { children: React.ReactNode }) {
  return (
    <Col>
      <span className="font-medium text-sm">What it allocates</span>
      <Card className="gap-2 p-2.5 text-sm">{children}</Card>
    </Col>
  );
}

interface AllocatesRowProps {
  label: string;
  isRequired?: boolean;
  children: React.ReactNode;
}

function AllocatesRow({ label, isRequired, children }: AllocatesRowProps) {
  return (
    <dl className="flex items-start gap-2">
      <dt className="flex min-h-8 w-20 shrink-0 items-center text-foreground-muted">
        {label} {isRequired && "*"}
      </dt>
      <dd className="flex min-h-8 min-w-0 flex-1 flex-col justify-center gap-2">{children}</dd>
    </dl>
  );
}
