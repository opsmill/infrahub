import {
  Autocomplete,
  Button,
  ListBox,
  Popover,
  PopoverTrigger,
  SelectItem,
  Tooltip,
} from "@infrahub/ui";
import { PlusIcon, TriangleAlertIcon, XIcon } from "lucide-react";
import { Fragment, type ReactNode, useState } from "react";
import { Button as AriaButton, Header, ListBoxSection } from "react-aria-components";
import { useWatch } from "react-hook-form";

import { Col, Row } from "@/shared/components/container";
import type { FormAttributeValue } from "@/shared/components/form/type";
import { FormField } from "@/shared/components/ui/form";

import {
  NUMBER_POOL_ALLOCATION_SCOPE_FIELD,
  NUMBER_POOL_NODE_ATTRIBUTE_FIELD,
  NUMBER_POOL_NODE_FIELD,
} from "@/entities/resource-manager/domain/model/pool";
import type { ScopeCandidate } from "@/entities/resource-manager/domain/model/scope-candidate";
import { getScopeCandidates } from "@/entities/resource-manager/domain/rules/get-scope-candidates";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

const EMPTY_CHIP_CLASS =
  "inline-flex h-7 items-center gap-1 self-start rounded-lg border border-border-strong border-dashed px-2 text-foreground-muted text-sm outline-none transition-colors duration-150 focus-visible:ring-2 focus-visible:ring-ring-halo data-disabled:opacity-60 data-hovered:bg-highlight data-hovered:text-foreground";

const EMPTY_LABEL = "No relationship or attribute";

const EMPTY_TOOLTIP =
  "Every object shares one sequence. Click to give each related object or value its own sequence.";

export function ScopeField() {
  const [node, nodeAttribute]: Array<FormAttributeValue | undefined> = useWatch({
    name: [NUMBER_POOL_NODE_FIELD, NUMBER_POOL_NODE_ATTRIBUTE_FIELD],
  });
  const { schema } = useSchema(node?.value?.toString());

  return (
    <FormField
      name={NUMBER_POOL_ALLOCATION_SCOPE_FIELD}
      defaultValue={[]}
      render={({ field }) => (
        <ScopeInput
          schema={schema}
          nodeAttribute={nodeAttribute?.value?.toString() ?? ""}
          scope={field.value ?? []}
          onChange={field.onChange}
        />
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

  if (!schema) {
    return (
      <AriaButton isDisabled className={EMPTY_CHIP_CLASS}>
        {EMPTY_LABEL}
      </AriaButton>
    );
  }

  const candidates = getScopeCandidates(schema, nodeAttribute);
  const labelOf = (name: string) => candidates.find((c) => c.name === name)?.label ?? name;
  const remaining = candidates.filter((candidate) => !scope.includes(candidate.name));
  const add = (name: string) => onChange([...scope, name]);
  const attribute = schema.attributes?.find(({ name }) => name === nodeAttribute);

  if (scope.length === 0 && remaining.every((candidate) => candidate.unavailableReason)) {
    return (
      <Row className="flex-wrap items-center gap-2">
        <AriaButton isDisabled className={EMPTY_CHIP_CLASS}>
          {EMPTY_LABEL}
        </AriaButton>
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
            <AriaButton className={EMPTY_CHIP_CLASS}>{EMPTY_LABEL}</AriaButton>
          </Tooltip>
        }
      />
    );
  }

  return (
    <Col className="gap-2">
      <div className="flex flex-wrap items-center gap-1.5">
        {scope.map((name, index) => (
          <Fragment key={name}>
            {index > 0 && <span className="text-foreground-muted">+</span>}
            <span className="inline-flex h-7 max-w-full items-center gap-1 rounded-lg border border-border-strong bg-card pr-0.5 pl-2 text-sm">
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
            </span>
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
      </div>
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

interface CandidatePickerProps {
  candidates: ScopeCandidate[];
  onAdd: (name: string) => void;
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
  trigger: ReactNode;
}

function CandidatePicker({
  candidates,
  onAdd,
  isOpen,
  onOpenChange,
  trigger,
}: CandidatePickerProps) {
  const sections = [
    {
      id: "relationship",
      title: "Relationships",
      items: candidates.filter((candidate) => candidate.type === "relationship"),
    },
    {
      id: "attribute",
      title: "Attributes",
      items: candidates.filter((candidate) => candidate.type === "attribute"),
    },
  ].filter((section) => section.items.length > 0);
  const disabledKeys = candidates
    .filter((candidate) => candidate.unavailableReason)
    .map((candidate) => candidate.name);

  return (
    <PopoverTrigger isOpen={isOpen} onOpenChange={onOpenChange}>
      {trigger}
      <Popover placement="bottom start" className="w-80">
        <Autocomplete>
          <ListBox
            aria-label="Scope fields"
            items={sections}
            disabledKeys={disabledKeys}
            className="max-h-80"
            onAction={(key) => {
              onAdd(String(key));
              onOpenChange(false);
            }}
          >
            {(section) => (
              <ListBoxSection id={section.id}>
                <Header className="px-2 pt-2 pb-1 font-medium text-foreground-muted text-xs">
                  {section.title}
                </Header>
                {section.items.map((candidate) => (
                  <SelectItem key={candidate.name} id={candidate.name} textValue={candidate.label}>
                    <span className="flex w-full items-baseline gap-2">
                      <span className="min-w-0 flex-1 truncate">{candidate.label}</span>
                      <span className="shrink-0 text-foreground-muted text-xs">
                        {candidate.unavailableReason ?? (
                          <span className="font-mono">{candidate.detail}</span>
                        )}
                      </span>
                    </span>
                  </SelectItem>
                ))}
              </ListBoxSection>
            )}
          </ListBox>
        </Autocomplete>
      </Popover>
    </PopoverTrigger>
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
