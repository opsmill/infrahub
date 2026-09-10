import { useAtomValue } from "jotai";
import { useId, useRef, useState } from "react";
import { useFormContext } from "react-hook-form";

import { Col } from "@/shared/components/container";
import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import {
  FieldTabs,
  FieldTabsContent,
  FieldTabsList,
  FieldTabsTrigger,
} from "@/shared/components/form/field-tabs";
import { LabelFormField } from "@/shared/components/form/fields/common";
import { PoolAllocationPanel } from "@/shared/components/form/pool-allocation-panel";
import type {
  DynamicRelationshipFieldProps,
  FormRelationshipValue,
  PoolValue,
} from "@/shared/components/form/type";
import { getParentRelationship } from "@/shared/components/form/utils/getParentRelationship";
import { updateRelationshipFieldValue } from "@/shared/components/form/utils/updateFormFieldValue";
import { RelationshipInput } from "@/shared/components/inputs/relationship-one";
import { Badge } from "@/shared/components/ui/badge";
import {
  Combobox,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxItem,
  ComboboxList,
  ComboboxTrigger,
} from "@/shared/components/ui/combobox";
import { FormField, FormInput, FormMessage } from "@/shared/components/ui/form";
import { Input } from "@/shared/components/ui/input";

import type { Node } from "@/entities/nodes/getObjectItemDisplayValue";
import { useDefaultParent } from "@/entities/nodes/relationships/ui/queries/get-default-parent.query";
import { resolveSchema } from "@/entities/schema/domain/rules/resolve-schema";
import {
  genericSchemasAtom,
  nodeSchemasAtom,
  profileSchemasAtom,
  templateSchemasAtom,
} from "@/entities/schema/stores/schema.atom";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

import { useCommonParentFilter } from "./useCommonParentFilter";

interface GenericOption extends Node {
  id: string;
  display_label: string;
  badge: string;
}

const OBJECT_TAB = "object";
const POOL_TAB = "from-pool";
type FieldTab = typeof OBJECT_TAB | typeof POOL_TAB;

/**
 * Maps the stored field value onto what `RelationshipInput` renders. The two shapes genuinely
 * differ, so this narrows at the boundary instead of asserting:
 * - `FormRelationshipValue["value"]` may be an array (cardinality-many); this field only ever
 *   renders a single peer, so an array has nothing to display.
 * - `NodeCore.display_label` is optional, `Node.display_label` is not. Keeping a nullish label
 *   as `""` leaves `getNodeLabel` on its hfid/id fallback, exactly as before.
 * - the stored from-pool value is a bare marker; the pool's own name and kind live on the
 *   field's `source`, so recombine them rather than inventing values.
 */
const toRelationshipInputValue = (
  fieldData: FormRelationshipValue | undefined
): Node | PoolValue | null => {
  const value = fieldData?.value;
  if (!value || Array.isArray(value)) return null;

  if ("from_pool" in value) {
    const poolSource = fieldData?.source?.type === "pool" ? fieldData.source : null;
    if (!poolSource) return null;

    return {
      from_pool: { ...value.from_pool, name: poolSource.label ?? "", kind: poolSource.kind },
    };
  }

  return { ...value, display_label: value.display_label ?? "" };
};

export interface GenericRelationshipFieldProps extends DynamicRelationshipFieldProps {
  parentDisabled?: boolean;
}

export const GenericRelationshipField = ({
  defaultValue,
  description,
  label,
  name,
  rules,
  unique,
  type,
  options,
  parent,
  pool,
  relationship,
  shouldUnregister,
  ...props
}: GenericRelationshipFieldProps) => {
  const { schema: peerSchema, isGeneric } = useSchema(relationship?.peer);

  const defaultSelectedGeneric = parent ? options?.find((option) => option.id === parent) : null;

  const [selectedGeneric, setSelectedGeneric] = useState<GenericOption | null>(
    defaultSelectedGeneric as GenericOption | null
  );

  const parentRelationship = selectedGeneric?.id && getParentRelationship(selectedGeneric.id);
  const commonParent = useCommonParentFilter(relationship, name);
  // When common_parent drives the filter from a sibling field, the manual "Parent" picker
  // is redundant — hide it and source the peer filter from the sibling value instead.
  const showManualParent = !commonParent.isActive && !!parentRelationship;

  const { data: defaultParent } = useDefaultParent({
    defaultValue,
    parentRelationship: parentRelationship
      ? {
          peer: parentRelationship.peer,
          direction: parentRelationship.direction,
          identifier: parentRelationship.identifier ?? undefined,
        }
      : undefined,
  });

  const [selectedParent, setSelectedParent] = useState<Node | null>(defaultParent || null);
  const hasDerivedKindFromDefault = useRef(false);

  // One subscription per schema collection, resolved with the same pure lookup `useSchema`
  // uses. Calling `useSchema` per `used_by` entry would put a hook inside the loop, making
  // the hook count vary with the number of implementations.
  const schemas = {
    nodeSchemas: useAtomValue(nodeSchemasAtom),
    genericSchemas: useAtomValue(genericSchemasAtom),
    profileSchemas: useAtomValue(profileSchemasAtom),
    templateSchemas: useAtomValue(templateSchemasAtom),
  };

  const genericOptions = (isGeneric ? (peerSchema?.used_by ?? []) : [])
    .map((usedByKind: string) => {
      const { schema: relatedSchema } = resolveSchema(usedByKind, schemas);

      if (relatedSchema) {
        return {
          id: usedByKind,
          display_label: relatedSchema.label || relatedSchema.name,
          badge: relatedSchema.namespace,
        };
      }

      return null;
    })
    .filter((n): n is GenericOption => n !== null);

  // Select the first option if the only available
  if (genericOptions?.length === 1 && !selectedGeneric) {
    setSelectedGeneric(genericOptions[0] ?? null);
  }

  // Select the kind after building the options from generics
  if (parent && !selectedGeneric && genericOptions?.length) {
    const foundOption: GenericOption | undefined = genericOptions.find(
      (option: GenericOption) => option.id === parent
    );
    if (foundOption) {
      setSelectedGeneric(foundOption);
    }
  }

  // A default value (e.g. a parent pre-filled from the object being viewed) carries
  // its concrete node kind. Derive the selected kind from it once, so the value is shown
  // even when the generic is implemented by more than one node and cannot auto-select —
  // without re-selecting after the user has explicitly cleared the kind.
  const defaultValueKind =
    defaultValue?.value && !Array.isArray(defaultValue.value)
      ? (defaultValue.value as Node).__typename
      : undefined;
  if (
    defaultValueKind &&
    !selectedGeneric &&
    !hasDerivedKindFromDefault.current &&
    genericOptions?.length
  ) {
    const foundOption = genericOptions.find((option) => option.id === defaultValueKind);
    if (foundOption) {
      hasDerivedKindFromDefault.current = true;
      setSelectedGeneric(foundOption);
    }
  }

  if (!selectedParent && defaultParent) {
    setSelectedParent(defaultParent);
  }

  const form = useFormContext();

  // A user switching the kind invalidates any node picked under the previous kind, along with
  // the parent used to filter it, so clear both. Only wired to the picker, not the automatic
  // derivation above, so a pre-filled value is preserved on mount. Validation is not forced
  // here — flagging the field required before the user can pick a node under the new kind
  // would be premature.
  const handleKindChange = (value: GenericOption | null) => {
    setSelectedGeneric(value);
    setSelectedParent(null);
    form.setValue(name, DEFAULT_FORM_FIELD_VALUE, { shouldDirty: true });
  };

  // A field satisfied from a pool offers the two ways of satisfying it as tabs. The kind picker
  // belongs to the object tab alone: the pool list is deliberately filtered over the generic's
  // whole `used_by` (see `allocatableKinds`), so a kind chosen for the object picker would
  // contradict the pool the user then picks. From the pool tab the pool's own default kind
  // applies, overridable per allocation.
  const [activeTab, setActiveTab] = useState<FieldTab>(OBJECT_TAB);

  // Switching tabs abandons whatever was staged under the old one, so the field goes back to
  // the value it had on open — not to empty. Restoring the default is what makes merely looking
  // at the other tab a no-op: `getUpdateMutationFromFormData` skips a field that deep-equals its
  // default, so nothing is submitted, and on an edit form the existing value is not silently
  // cleared. It also stops the nested `${name}.value.from_pool.*` fields surviving a switch.
  const handleTabChange = (tab: string) => {
    setActiveTab(tab === POOL_TAB ? POOL_TAB : OBJECT_TAB);
    setSelectedParent(null);
    form.setValue(name, defaultValue ?? DEFAULT_FORM_FIELD_VALUE, { shouldDirty: true });
  };

  return (
    <div className="space-y-2">
      <FormField
        key={name}
        name={name}
        rules={rules}
        shouldUnregister={shouldUnregister}
        render={({ field }) => {
          // RHF hands back `undefined` until this field's default lands, so normalise to the
          // empty value the pool controls expect rather than letting it reach them raw.
          const fieldData: FormRelationshipValue = field.value ?? DEFAULT_FORM_FIELD_VALUE;
          const selectedPoolId = fieldData?.source?.type === "pool" ? fieldData.source.id : null;

          const onChange = (newValue: Node | PoolValue | null) => {
            field.onChange(updateRelationshipFieldValue(newValue, defaultValue));
          };

          const renderObjectValue = () => {
            if (!selectedGeneric?.id) {
              return (
                <div className="relative flex flex-col space-y-2">
                  <LabelFormField
                    label={selectedGeneric?.display_label ?? "Select a kind first"}
                    unique={unique}
                    required={!!rules?.required}
                    description={description}
                    variant="small"
                    className="italic"
                  />
                  <FormInput>
                    <Input disabled name="node-placholder" />
                  </FormInput>
                </div>
              );
            }

            return (
              <div className="relative flex flex-col space-y-2">
                <LabelFormField
                  label={selectedGeneric?.display_label ?? "Node"}
                  unique={unique}
                  required={!!rules?.required}
                  description={description}
                  variant="small"
                />
                <Col className="gap-2">
                  <FormInput>
                    <RelationshipInput
                      {...field}
                      {...props}
                      options={undefined}
                      value={toRelationshipInputValue(fieldData)}
                      onChange={onChange}
                      peer={selectedGeneric.id}
                      parent={
                        commonParent.isActive
                          ? commonParent.parent
                          : { name: parentRelationship?.name, value: selectedParent?.id }
                      }
                      addNewInitialObject={commonParent.addNewInitialObject}
                      disabled={props.disabled}
                    />
                  </FormInput>

                  <FormMessage />
                </Col>
              </div>
            );
          };

          const objectPanel = (
            <>
              <GenericSchemaPicker
                genericOptions={genericOptions}
                selectedGeneric={selectedGeneric}
                setSelectedGeneric={handleKindChange}
              />

              {showManualParent && parentRelationship && (
                <Col>
                  <LabelFormField
                    label={parentRelationship?.label ?? "Parent"}
                    description={parentRelationship?.description}
                    unique={unique}
                    variant="small"
                  />
                  <RelationshipInput
                    name={name + "_parent"}
                    value={selectedParent ?? null}
                    peer={parentRelationship.peer}
                    placeholder="Select a parent"
                    disabled={props.disabled || !selectedGeneric?.id}
                    onChange={(value) => setSelectedParent(value as Node | null)}
                  />
                </Col>
              )}

              {renderObjectValue()}
            </>
          );

          // Rendered inside the field so it can carry `fieldData`: that is what puts the
          // provenance badge (pool / profile / template) beside the label, as the untabbed
          // relationship field does. Without it a pool-allocated field looks unsourced.
          const fieldLabel = (
            <LabelFormField
              label={label}
              unique={unique}
              required={!!rules?.required}
              description={description}
              fieldData={fieldData}
            />
          );

          if (!pool) {
            return (
              <>
                {fieldLabel}
                <Col className="rounded-md border border-border p-3">{objectPanel}</Col>
              </>
            );
          }

          return (
            <FieldTabs
              value={activeTab}
              onValueChange={handleTabChange}
              // Switching discards the staged value, so it must take a deliberate press rather
              // than merely arrowing across the strip.
              activationMode="manual"
            >
              {fieldLabel}

              <FieldTabsList>
                <FieldTabsTrigger value={OBJECT_TAB} disabled={props.disabled}>
                  Object
                </FieldTabsTrigger>
                <FieldTabsTrigger value={POOL_TAB} disabled={props.disabled}>
                  From pool
                </FieldTabsTrigger>
              </FieldTabsList>

              <FieldTabsContent value={OBJECT_TAB}>{objectPanel}</FieldTabsContent>

              <FieldTabsContent value={POOL_TAB}>
                <PoolAllocationPanel
                  name={name}
                  poolKind={pool.kind}
                  poolDefaultAllocatedObjectKind={pool.defaultAllocatedObjectKind}
                  // Straight from the peer generic's `used_by`: the pool filter and the type
                  // override share it, and neither depends on the object tab's selection.
                  allocatableKinds={genericOptions.map((option) => ({
                    kind: option.id,
                    label: option.display_label,
                    namespace: option.badge,
                  }))}
                  options={pool.options}
                  selectedPoolId={selectedPoolId}
                  value={fieldData}
                  disabled={props.disabled}
                  onChange={onChange}
                />
              </FieldTabsContent>
            </FieldTabs>
          );
        }}
      />
    </div>
  );
};

const GenericSchemaPicker = ({
  genericOptions,
  selectedGeneric,
  setSelectedGeneric,
}: {
  genericOptions: GenericOption[];
  selectedGeneric: GenericOption | null;
  setSelectedGeneric: (value: GenericOption | null) => void;
}) => {
  const id = useId();
  const [open, setOpen] = useState(false);

  return (
    <Col>
      <LabelFormField
        label="Kind"
        description="Kind of node to use as relationship"
        variant="small"
        htmlFor={id}
      />

      <Combobox open={open} onOpenChange={setOpen}>
        <ComboboxTrigger id={id}>
          {selectedGeneric ? (
            <div className="flex w-full justify-between" data-testid="select-value">
              {selectedGeneric.display_label} <Badge>{selectedGeneric.badge}</Badge>
            </div>
          ) : (
            <span className="text-subtle-muted">Select a kind</span>
          )}
        </ComboboxTrigger>

        <ComboboxContent>
          <ComboboxList>
            <ComboboxEmpty>No schema found.</ComboboxEmpty>
            {genericOptions.map((item: GenericOption) => {
              return (
                <ComboboxItem
                  key={item.id}
                  value={item.id}
                  selectedValue={selectedGeneric?.id}
                  onSelect={() => {
                    setSelectedGeneric(item.id === selectedGeneric?.id ? null : item);
                    setOpen(false);
                  }}
                >
                  {item.display_label}
                  <Badge className="ml-auto">{item.badge}</Badge>
                </ComboboxItem>
              );
            })}
          </ComboboxList>
        </ComboboxContent>
      </Combobox>
    </Col>
  );
};
