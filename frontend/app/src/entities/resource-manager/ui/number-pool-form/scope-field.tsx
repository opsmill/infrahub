import { Button, Tooltip } from "@infrahub/ui";
import { PlusIcon, TriangleAlertIcon, XIcon } from "lucide-react";
import { Fragment, type ReactNode, useState } from "react";
import { useWatch } from "react-hook-form";

import { Col, Row } from "@/shared/components/container";
import type { FormAttributeValue } from "@/shared/components/form/type";
import { Badge } from "@/shared/components/ui/badge";
import { FormField } from "@/shared/components/ui/form";

import {
  NUMBER_POOL_ALLOCATION_SCOPE_FIELD,
  NUMBER_POOL_NODE_ATTRIBUTE_FIELD,
  NUMBER_POOL_NODE_FIELD,
} from "@/entities/resource-manager/domain/model/pool";
import { getScopeCandidates } from "@/entities/resource-manager/domain/rules/get-scope-candidates";
import { CandidatePicker } from "@/entities/resource-manager/ui/number-pool-form/scope-candidate-picker";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

const EMPTY_TOOLTIP =
  "Every object shares one sequence. Click to give each related object or value its own sequence.";

function EmptyScopeButton({ isDisabled }: { isDisabled?: boolean }) {
  return (
    <Button
      variant="ghost"
      size="xs"
      isDisabled={isDisabled}
      className="self-start border-border-strong border-dashed font-normal text-foreground-muted"
    >
      No relationship or attribute
    </Button>
  );
}

interface ScopeFieldProps {
  labelledBy: string;
}

export function ScopeField({ labelledBy }: ScopeFieldProps) {
  const [node, nodeAttribute]: Array<FormAttributeValue | undefined> = useWatch({
    name: [NUMBER_POOL_NODE_FIELD, NUMBER_POOL_NODE_ATTRIBUTE_FIELD],
  });
  const { schema } = useSchema(node?.value?.toString());

  return (
    <FormField
      name={NUMBER_POOL_ALLOCATION_SCOPE_FIELD}
      defaultValue={[]}
      render={({ field }) => (
        <Col role="group" aria-labelledby={labelledBy}>
          <ScopeInput
            schema={schema}
            nodeAttribute={nodeAttribute?.value?.toString() ?? ""}
            scope={field.value ?? []}
            onChange={field.onChange}
          />
        </Col>
      )}
    />
  );
}

interface ScopeInputProps {
  schema: ModelSchema | null;
  nodeAttribute: string;
  scope: string[];
  onChange: (scope: string[]) => void;
}

function ScopeInput({ schema, nodeAttribute, scope, onChange }: ScopeInputProps) {
  const [isOpen, setIsOpen] = useState(false);

  if (!schema) return <EmptyScopeButton isDisabled />;

  const candidates = getScopeCandidates(schema, nodeAttribute);
  const labelOf = (name: string) => candidates.find((c) => c.name === name)?.label ?? name;
  const remaining = candidates.filter((candidate) => !scope.includes(candidate.name));
  const add = (name: string) => onChange([...scope, name]);
  const attribute = schema.attributes?.find(({ name }) => name === nodeAttribute);

  if (scope.length === 0 && remaining.every((candidate) => candidate.unavailableReason)) {
    return (
      <Row className="flex-wrap">
        <EmptyScopeButton isDisabled />
        <span className="text-foreground-muted text-xs">
          {schema.label ?? schema.kind} has no required attribute or relationship to scope by.
        </span>
      </Row>
    );
  }

  if (scope.length === 0) {
    return (
      <CandidatePicker
        candidates={remaining}
        onAdd={add}
        isOpen={isOpen}
        onOpenChange={setIsOpen}
        trigger={
          <Tooltip message={EMPTY_TOOLTIP}>
            <EmptyScopeButton />
          </Tooltip>
        }
      />
    );
  }

  return (
    <Col className="gap-2">
      <Row className="flex-wrap gap-1.5">
        {scope.map((name, index) => (
          <Fragment key={name}>
            {index > 0 && <span className="text-foreground-muted">+</span>}
            <Badge className="max-w-full gap-1 py-0 pr-0.5">
              <span className="truncate">{labelOf(name)}</span>
              <Button
                variant="ghost"
                shape="square"
                size="xxs"
                aria-label={`Remove ${labelOf(name)}`}
                onPress={() => onChange(scope.filter((chosen) => chosen !== name))}
                className="text-foreground-muted"
              >
                <XIcon />
              </Button>
            </Badge>
          </Fragment>
        ))}
        <CandidatePicker
          candidates={remaining}
          onAdd={add}
          isOpen={isOpen}
          onOpenChange={setIsOpen}
          trigger={
            <Button
              variant="ghost"
              size="sm"
              shape="square"
              aria-label="Add a relationship or attribute"
            >
              <PlusIcon />
            </Button>
          }
        />
      </Row>
      {attribute?.unique && (
        <WarningNote>
          {attribute.label ?? attribute.name} must be unique across every{" "}
          {schema.label ?? schema.kind}, so the same number can't be used in two scopes. To reuse
          numbers per scope, make it unique together with the scope fields in the schema.
        </WarningNote>
      )}
    </Col>
  );
}

function WarningNote({ children }: { children: ReactNode }) {
  return (
    <p className="flex gap-2 text-pretty rounded-lg border border-warning-border bg-warning-surface px-2.5 py-2 text-sm text-warning">
      <TriangleAlertIcon className="mt-0.5 size-4 shrink-0" aria-hidden />
      <span>{children}</span>
    </p>
  );
}
