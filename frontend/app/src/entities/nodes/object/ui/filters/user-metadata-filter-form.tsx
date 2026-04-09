import { FormField } from "@/shared/components/ui/form";
import useFilters, { type Filter } from "@/shared/hooks/useFilters";

import type { MetadataUserFilterDefinition } from "@/entities/nodes/object/domain/filter-definition";
import { FILTER_CONDITION } from "@/entities/nodes/object/ui/filters/filter-condition-select";
import { FilterFormLayout } from "@/entities/nodes/object/ui/filters/filter-form-layout";
import { RelationshipFilterCombobox } from "@/entities/nodes/object/ui/filters/relationship-filter-combobox";
import type { RelationshipNode } from "@/entities/nodes/relationships/domain/types";

export interface UserMetadataFilterFormProps {
  definition: MetadataUserFilterDefinition;
  onSuccess?: () => void;
}

type UserFormData = {
  relationships: RelationshipNode[];
};

export function UserMetadataFilterForm({ definition, onSuccess }: UserMetadataFilterFormProps) {
  const [filters, setFilters] = useFilters();
  const currentFilter = filters.find((filter) => filter.name.startsWith(definition.name));

  const handleSubmit = (data: UserFormData) => {
    const { relationships } = data;

    if (!relationships?.length) {
      return setFilters(filters.filter((f) => !f.name.startsWith(definition.name)));
    }

    const newFilter: Filter = {
      name: `${definition.name}__ids`,
      value: relationships,
    };

    if (currentFilter) {
      return setFilters(filters.map((f) => (f.name.startsWith(definition.name) ? newFilter : f)));
    }
    return setFilters([...filters, newFilter]);
  };

  return (
    <FilterFormLayout
      filterType="metadata-user"
      condition={FILTER_CONDITION.IS_ANY_OF}
      onConditionChange={() => {}}
      testId="metadata-user-filter-form"
      onSubmit={(formData) => {
        handleSubmit(formData as UserFormData);
        onSuccess?.();
      }}
    >
      <FormField
        name="relationships"
        defaultValue={currentFilter?.value ?? undefined}
        render={({ field }) => (
          <RelationshipFilterCombobox
            peer={definition.peer}
            value={field.value as RelationshipNode[] | undefined}
            onChange={field.onChange}
          />
        )}
      />
    </FilterFormLayout>
  );
}
