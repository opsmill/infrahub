import { Autocomplete, Menu, MenuItem, Popover, SubmenuTrigger } from "@infrahub/ui";
import React from "react";
import { useFilter } from "react-aria-components";

import { sortByOrderWeight } from "@/shared/utils/common";

import type { Sort, SortDirection, SortField } from "@/entities/nodes/sort/domain/model/sort";
import { isSortableAttribute } from "@/entities/nodes/sort/domain/rules/is-sortable-attribute";
import { isSortableRelationship } from "@/entities/nodes/sort/domain/rules/is-sortable-relationship";
import {
  buildAttributeSortField,
  buildRelationshipSortField,
} from "@/entities/nodes/sort/domain/rules/sort-field";
import type {
  AttributeSchema,
  ModelSchema,
  RelationshipSchema,
} from "@/entities/schema/domain/model/schema";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

interface SortableField {
  field: SortField;
  label: string;
}

const NODE_METADATA_SORTABLE_FIELDS: SortableField[] = [
  { field: "node_metadata__created_at", label: "Created at" },
  { field: "node_metadata__updated_at", label: "Updated at" },
];

const DIRECTION_OPTIONS: { id: SortDirection; label: string }[] = [
  { id: "ASC", label: "Ascending" },
  { id: "DESC", label: "Descending" },
];

// "Peer › Attribute" separator. En-spaces (U+2002) around the chevron keep it from looking cramped.
const PEER_LABEL_SEPARATOR = " › ";

interface SortDirectionMenuProps {
  fieldLabel: string;
  onSelect: (direction: SortDirection) => void;
}

function SortDirectionMenu({ fieldLabel, onSelect }: SortDirectionMenuProps) {
  return (
    <Menu aria-label={`Sort direction for ${fieldLabel}`} items={DIRECTION_OPTIONS}>
      {(direction) => (
        <MenuItem onAction={() => onSelect(direction.id)}>{direction.label}</MenuItem>
      )}
    </Menu>
  );
}

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
        <SortDirectionMenu
          fieldLabel={children}
          onSelect={(direction) => onSelect({ field, direction })}
        />
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
  onSelect: (sort: Sort) => void;
}

function GroupedSortableRelationshipMenuItem({
  relationship,
  onSelect,
}: SortableRelationshipMenuItemProps) {
  const { schema: peerSchema } = useSchema(relationship.peer);
  if (!peerSchema) return null;

  const sortableAttributes = (peerSchema.attributes ?? []).filter(isSortableAttribute);
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

function FlatSortableRelationshipMenuItems({
  relationship,
  onSelect,
}: SortableRelationshipMenuItemProps) {
  const { schema: peerSchema } = useSchema(relationship.peer);
  if (!peerSchema) return null;

  const sortableAttributes = (peerSchema.attributes ?? []).filter(isSortableAttribute);
  const relationshipLabel = relationship.label ?? relationship.name;

  return (
    <>
      {sortByOrderWeight(sortableAttributes).map((attribute) => {
        const field = buildRelationshipSortField(
          relationship.name,
          buildAttributeSortField(attribute.name)
        );
        const attributeLabel = attribute.label ?? attribute.name;

        return (
          <SortableFieldMenuItem key={field} field={field} onSelect={onSelect}>
            {`${relationshipLabel}${PEER_LABEL_SEPARATOR}${attributeLabel}`}
          </SortableFieldMenuItem>
        );
      })}
    </>
  );
}

interface AddSortPickerProps {
  schema: ModelSchema;
  onSelect: (sort: Sort) => void;
}

export function AddSortPicker({ schema, onSelect }: AddSortPickerProps) {
  const { contains } = useFilter({ sensitivity: "base" });
  const [search, setSearch] = React.useState("");
  const isSearching = search.trim() !== "";

  const SortableRelationshipMenuItems = isSearching
    ? FlatSortableRelationshipMenuItems
    : GroupedSortableRelationshipMenuItem;

  const sortableAttributes = (schema.attributes ?? []).filter(isSortableAttribute);
  const sortableRelationships = (schema.relationships ?? []).filter(isSortableRelationship);

  return (
    <Autocomplete filter={contains} onInputChange={setSearch}>
      <Menu variant="picker" aria-label="Add sort field" className="max-h-72">
        {sortableAttributes.map((attribute) => (
          <SortableAttributeMenuItem
            key={attribute.name}
            attribute={attribute}
            onSelect={onSelect}
          />
        ))}

        {sortableRelationships.map((relationship) => (
          <SortableRelationshipMenuItems
            key={relationship.name}
            relationship={relationship}
            onSelect={onSelect}
          />
        ))}

        {NODE_METADATA_SORTABLE_FIELDS.map((metadata) => (
          <SortableFieldMenuItem key={metadata.field} field={metadata.field} onSelect={onSelect}>
            {metadata.label}
          </SortableFieldMenuItem>
        ))}
      </Menu>
    </Autocomplete>
  );
}
