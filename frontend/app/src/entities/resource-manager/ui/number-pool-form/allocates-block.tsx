import { Card } from "@infrahub/ui";
import { type ReactNode, useId } from "react";
import { useFormContext, useWatch } from "react-hook-form";

import { Col, Row } from "@/shared/components/container";
import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import { LabelFormField } from "@/shared/components/form/fields/common";
import type { FormAttributeValue } from "@/shared/components/form/type";
import { updateFormFieldValue } from "@/shared/components/form/utils/updateFormFieldValue";
import { isRequired } from "@/shared/components/form/utils/validation";
import { Badge } from "@/shared/components/ui/badge";
import { FormField, FormMessage } from "@/shared/components/ui/form";

import {
  NUMBER_POOL_ALLOCATION_SCOPE_FIELD,
  NUMBER_POOL_NODE_ATTRIBUTE_FIELD,
  NUMBER_POOL_NODE_FIELD,
} from "@/entities/resource-manager/domain/model/pool";
import { getScopeCandidates } from "@/entities/resource-manager/domain/rules/get-scope-candidates";
import { AttributeCombobox } from "@/entities/resource-manager/ui/number-pool-form/attribute-combobox";
import {
  NodeCombobox,
  NodeLabel,
} from "@/entities/resource-manager/ui/number-pool-form/node-combobox";
import { ScopeField } from "@/entities/resource-manager/ui/number-pool-form/scope-field";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

interface AllocatedValues {
  node: string;
  attribute: string;
  scope: string[];
}

type AllocatesBlockProps = { variant: "input" } | ({ variant: "read-only" } & AllocatedValues);

export function AllocatesBlock(props: AllocatesBlockProps) {
  if (props.variant === "read-only") {
    return (
      <AllocatesLayout note="The node, attribute and scope are set when the pool is created.">
        <ReadOnlyAllocates node={props.node} attribute={props.attribute} scope={props.scope} />
      </AllocatesLayout>
    );
  }

  return (
    <AllocatesLayout note="The scope is optional. Only required fields can be used, and every object needs a value for them.">
      <AllocatesInputs />
    </AllocatesLayout>
  );
}

function AllocatesLayout({ children, note }: { children: ReactNode; note: string }) {
  const headingId = useId();

  return (
    <Col role="group" aria-labelledby={headingId} className="gap-1.5">
      <h3 id={headingId} className="font-medium text-sm">
        What it allocates
      </h3>
      <Card
        // biome-ignore lint/nursery/noTailwindArbitraryValue: structure: label column sized to its content, value column takes the rest
        className="grid grid-cols-[auto_minmax(0,1fr)] items-center gap-x-4 gap-y-2 rounded-xl p-2.5 text-sm"
      >
        {children}
      </Card>
      <p className="text-foreground-muted text-xs">{note}</p>
    </Col>
  );
}

function ReadOnlyAllocates({ node, attribute, scope }: AllocatedValues) {
  const { schema } = useSchema(node);
  const attributeLabel = schema?.attributes?.find(({ name }) => name === attribute)?.label;
  const candidates = schema ? getScopeCandidates(schema, attribute) : [];
  const scopeLabelOf = (name: string) =>
    candidates.find((candidate) => candidate.name === name)?.label ?? name;

  return (
    <>
      <span className="text-foreground-muted">Node</span>
      <span className="font-medium">{schema ? <NodeLabel schema={schema} /> : node}</span>
      <span className="text-foreground-muted">Attribute</span>
      <span>{attributeLabel ?? attribute}</span>
      <span className="self-start text-foreground-muted">Scoped by</span>
      <Row className="flex-wrap gap-1">
        {scope.length === 0 && <span className="text-foreground-muted">Not scoped</span>}
        {scope.map((field) => (
          <Badge key={field}>{scopeLabelOf(field)}</Badge>
        ))}
      </Row>
    </>
  );
}

function AllocatesInputs() {
  const form = useFormContext();
  const scopeLabelId = useId();
  const selectedNode: FormAttributeValue | undefined = useWatch({ name: NUMBER_POOL_NODE_FIELD });
  const nodeKind = selectedNode?.value?.toString();
  const { schema } = useSchema(nodeKind);

  function updateScopeForAttribute(attributeName: string) {
    const scope: string[] = form.getValues(NUMBER_POOL_ALLOCATION_SCOPE_FIELD) ?? [];
    const isUnique = schema?.attributes?.find(({ name }) => name === attributeName)?.unique;
    const kept = isUnique ? [] : scope.filter((name) => name !== attributeName);
    if (kept.length !== scope.length) form.setValue(NUMBER_POOL_ALLOCATION_SCOPE_FIELD, kept);
  }

  return (
    <>
      <FormField
        name={NUMBER_POOL_NODE_FIELD}
        rules={{ validate: { required: isRequired } }}
        defaultValue={DEFAULT_FORM_FIELD_VALUE}
        render={({ field }) => (
          <>
            <LabelFormField label="Node" required />
            <Col className="gap-1">
              <NodeCombobox
                value={nodeKind}
                onSelect={(kind) => {
                  field.onChange(updateFormFieldValue(kind, DEFAULT_FORM_FIELD_VALUE));
                  form.setValue(NUMBER_POOL_NODE_ATTRIBUTE_FIELD, DEFAULT_FORM_FIELD_VALUE);
                  form.setValue(NUMBER_POOL_ALLOCATION_SCOPE_FIELD, []);
                }}
              />
              <FormMessage />
            </Col>
          </>
        )}
      />

      <FormField
        name={NUMBER_POOL_NODE_ATTRIBUTE_FIELD}
        rules={{ validate: { required: isRequired } }}
        defaultValue={DEFAULT_FORM_FIELD_VALUE}
        render={({ field }) => (
          <>
            <LabelFormField label="Attribute" required />
            <Col className="gap-1">
              <AttributeCombobox
                nodeKind={nodeKind}
                value={field.value?.value?.toString()}
                onSelect={(attributeName) => {
                  field.onChange(updateFormFieldValue(attributeName, DEFAULT_FORM_FIELD_VALUE));
                  updateScopeForAttribute(attributeName);
                }}
              />
              <FormMessage />
            </Col>
          </>
        )}
      />

      <span id={scopeLabelId} className="self-start pt-1.5 text-foreground-muted">
        Scoped by
      </span>
      <ScopeField labelledBy={scopeLabelId} />
    </>
  );
}
