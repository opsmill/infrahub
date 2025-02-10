import { RelationshipNode } from "@/entities/nodes/relationships/domain/types";
import { RelationshipComboboxList } from "@/entities/nodes/relationships/ui/relationship-combobox-list";
import { RelationshipSchema } from "@/entities/schema/types";
import { Button } from "@/shared/components/buttons/button-primitive";
import { Badge } from "@/shared/components/ui/badge";
import { Form, FormField, FormSubmit } from "@/shared/components/ui/form";
import useFilters, { Filter } from "@/shared/hooks/useFilters";
import { pluralize } from "@/shared/utils/string";

export interface RelationshipFilterFormProps {
  relationshipSchema: RelationshipSchema;
}

export function RelationshipFilterForm({ relationshipSchema }: RelationshipFilterFormProps) {
  const [filters, setFilters] = useFilters();

  const currentFilterKey = `${relationshipSchema.name}__ids` as const;
  const currentFilter = filters.find((filter) => filter.name === currentFilterKey);

  const handleSubmit = (data: Record<string, RelationshipNode[] | undefined>) => {
    const relationships = data[relationshipSchema.name];

    if (!relationships?.length) {
      // Remove filter if empty
      setFilters(filters.filter((f) => f.name !== currentFilterKey));
      return;
    }

    const newFilter: Filter = {
      name: currentFilterKey,
      value: relationships,
    };

    if (currentFilter) {
      setFilters(filters.map((f) => (f.name === currentFilterKey ? newFilter : f)));
    } else {
      setFilters([...filters, newFilter]);
    }
  };

  return (
    <Form className="space-y-0" onSubmit={handleSubmit}>
      <FormField
        name={relationshipSchema.name}
        defaultValue={currentFilter?.value}
        render={({ field }) => {
          const value = field.value as RelationshipNode[] | undefined;

          return (
            <RelationshipComboboxList
              peer={relationshipSchema.peer}
              onSelect={(relationship) => {
                field.onChange(value ? [...value, relationship] : [relationship]);
              }}
              filterItem={(node) => !value?.some((v) => v.id === node.id)}
            />
          );
        }}
      />

      <div className="flex justify-between gap-2 p-2 border-t">
        <FormField
          name={relationshipSchema.name}
          defaultValue={currentFilter?.value}
          render={({ field }) => {
            const value = field.value as RelationshipNode[] | undefined;

            if (!value || value.length === 0) {
              return <p className="text-sm text-gray-400 p-1">No relationships selected</p>;
            }

            return (
              <div className="grow">
                <p className="text-sm font-medium text-custom-gray-700 p-1 mb-2">
                  {pluralize(value.length, "relationship")} selected
                </p>

                <div className="flex flex-col items-start gap-2 max-w-xs max-h-[250px] overflow-auto">
                  {value?.map((relationship) => (
                    <Badge key={relationship.id} className="inline-flex items-center gap-1 pr-0.5">
                      {relationship.display_label}

                      <Button
                        size="icon"
                        variant="ghost"
                        onClick={(e) => {
                          e.stopPropagation();
                          field.onChange(value.filter((r) => r.id !== relationship.id));
                        }}
                        className="text-gray-500 hover:text-gray-800 h-4 w-4"
                        aria-label="Remove"
                        data-testid="remove-option"
                      >
                        &times;
                      </Button>
                    </Badge>
                  ))}
                </div>
              </div>
            );
          }}
        />
        <FormSubmit size="sm">Apply</FormSubmit>
      </div>
    </Form>
  );
}
