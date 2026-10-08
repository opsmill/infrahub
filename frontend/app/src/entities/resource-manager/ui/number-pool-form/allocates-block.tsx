import { useAtomValue } from "jotai";
import { type ReactNode, useState } from "react";
import { useFormContext, useWatch } from "react-hook-form";

import { Col } from "@/shared/components/container";
import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import { LabelFormField } from "@/shared/components/form/fields/common";
import type { FormAttributeValue } from "@/shared/components/form/type";
import { updateFormFieldValue } from "@/shared/components/form/utils/updateFormFieldValue";
import { isRequired } from "@/shared/components/form/utils/validation";
import { Badge } from "@/shared/components/ui/badge";
import {
  Combobox,
  ComboboxContent,
  ComboboxItem,
  ComboboxList,
  ComboboxTrigger,
} from "@/shared/components/ui/combobox";
import { FormField, FormInput, FormMessage } from "@/shared/components/ui/form";

import {
  NUMBER_POOL_ALLOCATION_SCOPE_FIELD,
  NUMBER_POOL_NODE_ATTRIBUTE_FIELD,
  NUMBER_POOL_NODE_FIELD,
} from "@/entities/resource-manager/domain/model/pool";
import { ATTRIBUTE_KIND } from "@/entities/schema/domain/model/attribute-kind";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";
import { genericSchemasAtom, nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

interface AllocatedValues {
  node: string;
  attribute: string;
  scope: string[];
}

type AllocatesBlockProps =
  | { variant: "input"; scopeField?: ReactNode }
  | ({ variant: "read-only" } & AllocatedValues);

export function AllocatesBlock(props: AllocatesBlockProps) {
  if (props.variant === "read-only") {
    return (
      <AllocatesLayout note="The kind and attribute are set when the pool is created.">
        <ReadOnlyAllocates node={props.node} attribute={props.attribute} scope={props.scope} />
      </AllocatesLayout>
    );
  }

  return (
    <AllocatesLayout
      note={
        props.scopeField
          ? "The scope is optional. Only required fields can be used, and every object needs a value for them."
          : undefined
      }
    >
      <AllocatesInputs scopeField={props.scopeField} />
    </AllocatesLayout>
  );
}

function AllocatesLayout({ children, note }: { children: ReactNode; note?: string }) {
  return (
    <Col className="gap-1.5">
      <span className="font-medium text-sm">What it allocates</span>
      <div
        // biome-ignore lint/nursery/noTailwindArbitraryValue: structure: label column sized to its content, value column takes the rest
        className="grid grid-cols-[auto_minmax(0,1fr)] items-center gap-x-4 gap-y-2 rounded-xl border bg-card p-2.5 text-sm"
      >
        {children}
      </div>
      {note && <p className="text-foreground-muted text-xs">{note}</p>}
    </Col>
  );
}

function useModelSchemas(): ModelSchema[] {
  const nodes = useAtomValue(nodeSchemasAtom);
  const generics = useAtomValue(genericSchemasAtom);
  return [...generics, ...nodes];
}

function NodeLabel({ schema }: { schema: ModelSchema }) {
  return (
    <span className="flex w-full justify-between">
      {schema.label} <Badge>{schema.namespace}</Badge>
    </span>
  );
}

function ReadOnlyAllocates({ node, attribute, scope }: AllocatedValues) {
  const schema = useModelSchemas().find((model) => model.kind === node);
  const attributeLabel = schema?.attributes?.find(({ name }) => name === attribute)?.label;

  return (
    <>
      <span className="text-foreground-muted">Node</span>
      <span className="font-medium">{schema ? <NodeLabel schema={schema} /> : node}</span>
      <span className="text-foreground-muted">Attribute</span>
      <span>{attributeLabel ?? attribute}</span>
      <span className="self-start text-foreground-muted">Scoped by</span>
      <span className="flex flex-wrap gap-1">
        {scope.length === 0 && <span className="text-foreground-muted">Not scoped</span>}
        {scope.map((field) => (
          <Badge key={field}>{field}</Badge>
        ))}
      </span>
    </>
  );
}

function AllocatesInputs({ scopeField }: { scopeField?: ReactNode }) {
  const form = useFormContext();
  const options = useModelSchemas();
  const selectedNodeField: FormAttributeValue | undefined = useWatch({
    name: NUMBER_POOL_NODE_FIELD,
  });
  const selectedNode = options.find((node) => node.kind === selectedNodeField?.value);

  const nodesWithNumberAttributes = options.filter((node) =>
    node.attributes?.some(
      (attribute) => attribute.kind === ATTRIBUTE_KIND.NUMBER && !attribute.read_only
    )
  );
  const numberAttributeOptions =
    selectedNode?.attributes?.filter((attribute) => attribute.kind === ATTRIBUTE_KIND.NUMBER) ?? [];

  function removeFromScope(fieldName: string) {
    const scope: string[] = form.getValues(NUMBER_POOL_ALLOCATION_SCOPE_FIELD) ?? [];
    if (scope.includes(fieldName)) {
      form.setValue(
        NUMBER_POOL_ALLOCATION_SCOPE_FIELD,
        scope.filter((name) => name !== fieldName)
      );
    }
  }

  return (
    <>
      <FormField
        name={NUMBER_POOL_NODE_FIELD}
        rules={{ validate: { required: isRequired } }}
        defaultValue={DEFAULT_FORM_FIELD_VALUE}
        render={({ field }) => {
          const [open, setOpen] = useState(false);

          return (
            <>
              <LabelFormField label="Node" required />
              <Col className="gap-1">
                <Combobox open={open} onOpenChange={setOpen}>
                  <FormInput>
                    <ComboboxTrigger>
                      {selectedNode && <NodeLabel schema={selectedNode} />}
                    </ComboboxTrigger>
                  </FormInput>
                  <ComboboxContent>
                    <ComboboxList>
                      {nodesWithNumberAttributes.map((node) => (
                        <ComboboxItem
                          key={node.id}
                          selectedValue={selectedNode?.kind}
                          value={node.kind!}
                          keywords={[node.label as string]}
                          onSelect={() => {
                            const newValue = node.kind === selectedNode?.kind ? null : node.kind;
                            field.onChange(
                              updateFormFieldValue(newValue ?? null, DEFAULT_FORM_FIELD_VALUE)
                            );
                            form.setValue(
                              NUMBER_POOL_NODE_ATTRIBUTE_FIELD,
                              DEFAULT_FORM_FIELD_VALUE
                            );
                            form.setValue(NUMBER_POOL_ALLOCATION_SCOPE_FIELD, []);
                            setOpen(false);
                          }}
                        >
                          <NodeLabel schema={node} />
                        </ComboboxItem>
                      ))}
                    </ComboboxList>
                  </ComboboxContent>
                </Combobox>
                <FormMessage />
              </Col>
            </>
          );
        }}
      />

      <FormField
        name={NUMBER_POOL_NODE_ATTRIBUTE_FIELD}
        rules={{ validate: { required: isRequired } }}
        defaultValue={DEFAULT_FORM_FIELD_VALUE}
        render={({ field }) => {
          const [open, setOpen] = useState(false);
          const selectedAttribute: FormAttributeValue | undefined = field.value;

          return (
            <>
              <LabelFormField label="Attribute" required />
              <Col className="gap-1">
                <Combobox open={open} onOpenChange={setOpen}>
                  <FormInput>
                    <ComboboxTrigger disabled={!selectedNode}>
                      {
                        numberAttributeOptions.find(
                          (attribute) => attribute.name === selectedAttribute?.value
                        )?.label
                      }
                    </ComboboxTrigger>
                  </FormInput>
                  <ComboboxContent>
                    <ComboboxList>
                      {numberAttributeOptions.map((attribute) => (
                        <ComboboxItem
                          key={attribute.id ?? attribute.name}
                          selectedValue={selectedAttribute?.value?.toString()}
                          value={attribute.name}
                          keywords={[attribute.label as string]}
                          onSelect={() => {
                            field.onChange(
                              updateFormFieldValue(attribute.name, DEFAULT_FORM_FIELD_VALUE)
                            );
                            removeFromScope(attribute.name);
                            setOpen(false);
                          }}
                        >
                          {attribute.label}
                        </ComboboxItem>
                      ))}
                    </ComboboxList>
                  </ComboboxContent>
                </Combobox>
                <FormMessage />
              </Col>
            </>
          );
        }}
      />

      {scopeField && (
        <>
          <span className="self-start pt-1.5 text-foreground-muted">Scoped by</span>
          {scopeField}
        </>
      )}
    </>
  );
}
