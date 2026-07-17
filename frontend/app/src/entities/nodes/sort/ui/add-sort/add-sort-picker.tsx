import { Autocomplete, Menu, MenuItem, Popover, SubmenuTrigger } from "@infrahub/ui";
import { ArrowDownIcon, ArrowUpIcon, CalendarClockIcon } from "lucide-react";
import React from "react";
import { useFilter } from "react-aria-components";

import { sortByOrderWeight } from "@/shared/utils/common";

import type { Sort, SortField } from "@/entities/nodes/sort/domain/model/sort";
import { isSortableAttribute } from "@/entities/nodes/sort/domain/rules/is-sortable-attribute";
import { isSortableRelationship } from "@/entities/nodes/sort/domain/rules/is-sortable-relationship";
import {
  buildAttributeSortField,
  buildRelationshipSortField,
} from "@/entities/nodes/sort/domain/rules/sort-field";
import { useSortableFields } from "@/entities/nodes/sort/ui/hooks/use-sortable-fields";
import {
  DIRECTION_OPTIONS,
  NODE_METADATA_SORT_OPTIONS,
} from "@/entities/nodes/sort/ui/sort-options";
import type {
  AttributeSchema,
  ModelSchema,
  RelationshipSchema,
} from "@/entities/schema/domain/model/schema";
import { FieldSchemaIcon } from "@/entities/schema/ui/field-schema-icon";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

interface SortableFieldMenuItemProps {
  field: SortField;
  textValue: string;
  children: React.ReactNode;
  onSelect: (sort: Sort) => void;
}

function SortableFieldMenuItem({
  field,
  textValue,
  children,
  onSelect,
}: SortableFieldMenuItemProps) {
  return (
    <SubmenuTrigger>
      <MenuItem textValue={textValue}>{children}</MenuItem>

      <Popover>
        <Menu
          variant="picker"
          aria-label={`Sort direction for ${textValue}`}
          items={DIRECTION_OPTIONS}
        >
          {(option) => (
            <MenuItem
              textValue={option.label}
              onAction={() => onSelect({ field, direction: option.id })}
            >
              {option.id === "DESC" ? <ArrowDownIcon /> : <ArrowUpIcon />}
              <span>{option.label}</span>
            </MenuItem>
          )}
        </Menu>
      </Popover>
    </SubmenuTrigger>
  );
}

interface SortableAttributeMenuItemProps {
  attribute: AttributeSchema;
  onSelect: (sort: Sort) => void;
}

function SortableAttributeMenuItem({ attribute, onSelect }: SortableAttributeMenuItemProps) {
  const label = attribute.label ?? attribute.name;

  return (
    <SortableFieldMenuItem
      field={buildAttributeSortField(attribute.name)}
      textValue={label}
      onSelect={onSelect}
    >
      <FieldSchemaIcon fieldSchema={attribute} />
      <span>{label}</span>
    </SortableFieldMenuItem>
  );
}

interface SortableRelationshipMenuItemProps {
  relationship: RelationshipSchema;
  activeFields: ReadonlySet<SortField>;
  onSelect: (sort: Sort) => void;
}

function getAvailablePeerAttributes(
  peerSchema: ModelSchema,
  relationship: RelationshipSchema,
  activeFields: ReadonlySet<SortField>
): AttributeSchema[] {
  return (peerSchema.attributes ?? []).filter(isSortableAttribute).filter((attribute) => {
    const attributeField = buildAttributeSortField(attribute.name);
    const relationshipField = buildRelationshipSortField(relationship.name, attributeField);
    return !activeFields.has(relationshipField);
  });
}

function GroupedSortableRelationshipMenuItem({
  relationship,
  activeFields,
  onSelect,
}: SortableRelationshipMenuItemProps) {
  const { schema: peerSchema } = useSchema(relationship.peer);
  if (!peerSchema) return null;

  const sortableAttributes = getAvailablePeerAttributes(peerSchema, relationship, activeFields);
  if (sortableAttributes.length === 0) return null;

  const relationshipLabel = relationship.label ?? relationship.name;

  return (
    <SubmenuTrigger>
      <MenuItem textValue={relationshipLabel}>
        <FieldSchemaIcon fieldSchema={relationship} />
        <span>{relationshipLabel}</span>
      </MenuItem>

      <Popover>
        <Menu aria-label={`Sort by ${relationshipLabel}`}>
          {sortByOrderWeight(sortableAttributes).map((attribute) => (
            <SortableAttributeMenuItem
              key={relationship.name + attribute.name}
              attribute={attribute}
              onSelect={(sort) => {
                onSelect({
                  ...sort,
                  field: buildRelationshipSortField(relationship.name, sort.field),
                });
              }}
            />
          ))}
        </Menu>
      </Popover>
    </SubmenuTrigger>
  );
}

interface FieldItemsProps {
  schema: ModelSchema;
  activeFields: ReadonlySet<SortField>;
  onSelect: (sort: Sort) => void;
}

// Flat list of every available field, shown while searching.
function FlatFieldItems({ schema, activeFields, onSelect }: FieldItemsProps) {
  const sortableFields = useSortableFields(schema);
  const availableFields = sortableFields.filter(({ field }) => !activeFields.has(field));

  return availableFields.map(({ field, label }) => (
    <SortableFieldMenuItem key={field} field={field} textValue={label} onSelect={onSelect}>
      {label}
    </SortableFieldMenuItem>
  ));
}

// Attributes, then relationships as submenus, then metadata — shown when not searching.
function GroupedFieldItems({ schema, activeFields, onSelect }: FieldItemsProps) {
  const sortableAttributes = sortByOrderWeight(schema.attributes ?? [])
    .filter(isSortableAttribute)
    .filter((attribute) => !activeFields.has(buildAttributeSortField(attribute.name)));
  const sortableRelationships = sortByOrderWeight(schema.relationships ?? []).filter(
    isSortableRelationship
  );
  const metadataFields = NODE_METADATA_SORT_OPTIONS.filter(({ field }) => !activeFields.has(field));

  return (
    <>
      {sortableAttributes.map((attribute) => (
        <SortableAttributeMenuItem key={attribute.name} attribute={attribute} onSelect={onSelect} />
      ))}

      {sortableRelationships.map((relationship) => (
        <GroupedSortableRelationshipMenuItem
          key={relationship.name}
          relationship={relationship}
          activeFields={activeFields}
          onSelect={onSelect}
        />
      ))}

      {metadataFields.map((metadata) => (
        <SortableFieldMenuItem
          key={metadata.field}
          field={metadata.field}
          textValue={metadata.label}
          onSelect={onSelect}
        >
          <CalendarClockIcon />
          <span>{metadata.label}</span>
        </SortableFieldMenuItem>
      ))}
    </>
  );
}

const NO_ACTIVE_FIELDS: ReadonlySet<SortField> = new Set();

export interface AddSortPickerProps {
  schema: ModelSchema;
  activeFields?: ReadonlySet<SortField>;
  onSelect: (sort: Sort) => void;
}

export function AddSortPicker({
  schema,
  activeFields = NO_ACTIVE_FIELDS,
  onSelect,
}: AddSortPickerProps) {
  const { contains } = useFilter({ sensitivity: "base" });
  const [search, setSearch] = React.useState("");
  const isSearching = search.trim() !== "";

  return (
    <Autocomplete filter={contains} onInputChange={setSearch}>
      <Menu
        variant="picker"
        aria-label="Add sort field"
        className="max-h-72"
        emptyMessage={isSearching ? "No fields match" : "All sortable fields are in use"}
      >
        {isSearching ? (
          <FlatFieldItems schema={schema} activeFields={activeFields} onSelect={onSelect} />
        ) : (
          <GroupedFieldItems schema={schema} activeFields={activeFields} onSelect={onSelect} />
        )}
      </Menu>
    </Autocomplete>
  );
}
