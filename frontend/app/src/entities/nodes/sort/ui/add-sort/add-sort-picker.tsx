import { Autocomplete, Menu, MenuItem, Popover, SubmenuTrigger } from "@infrahub/ui";
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
import { DIRECTION_OPTIONS, METADATA_SORTABLE_FIELDS } from "@/entities/nodes/sort/ui/sort-options";
import type {
  AttributeSchema,
  ModelSchema,
  RelationshipSchema,
} from "@/entities/schema/domain/model/schema";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

interface SortableFieldMenuItemProps {
  field: SortField;
  children: string;
  onSelect: (sort: Sort) => void;
}

function SortableFieldMenuItem({ field, children, onSelect }: SortableFieldMenuItemProps) {
  return (
    <SubmenuTrigger>
      <MenuItem>{children}</MenuItem>

      <Popover>
        <Menu
          variant="picker"
          aria-label={`Sort direction for ${children}`}
          items={DIRECTION_OPTIONS}
        >
          {(option) => (
            <MenuItem onAction={() => onSelect({ field, direction: option.id })}>
              {option.label}
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
  return (
    <SortableFieldMenuItem field={buildAttributeSortField(attribute.name)} onSelect={onSelect}>
      {attribute.label ?? attribute.name}
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
      <MenuItem>{relationshipLabel}</MenuItem>

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

  const sortableFields = useSortableFields(schema);
  const availableFields = sortableFields.filter(({ field }) => !activeFields.has(field));

  const sortableAttributes = (schema.attributes ?? [])
    .filter(isSortableAttribute)
    .filter((attribute) => !activeFields.has(buildAttributeSortField(attribute.name)));
  const sortableRelationships = (schema.relationships ?? []).filter(isSortableRelationship);
  const metadataFields = METADATA_SORTABLE_FIELDS.filter(({ field }) => !activeFields.has(field));

  return (
    <Autocomplete filter={contains} onInputChange={setSearch}>
      <Menu
        variant="picker"
        aria-label="Add sort field"
        className="max-h-72"
        renderEmptyState={() => (
          <div className="px-2 py-1 text-sm text-stone-500">
            {isSearching ? "No fields match" : "All sortable fields are in use"}
          </div>
        )}
      >
        {isSearching ? (
          availableFields.map(({ field, label }) => (
            <SortableFieldMenuItem key={field} field={field} onSelect={onSelect}>
              {label}
            </SortableFieldMenuItem>
          ))
        ) : (
          <>
            {sortableAttributes.map((attribute) => (
              <SortableAttributeMenuItem
                key={attribute.name}
                attribute={attribute}
                onSelect={onSelect}
              />
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
                onSelect={onSelect}
              >
                {metadata.label}
              </SortableFieldMenuItem>
            ))}
          </>
        )}
      </Menu>
    </Autocomplete>
  );
}
