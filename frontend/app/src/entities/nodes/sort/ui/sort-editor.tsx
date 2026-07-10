import type { Sort } from "@/entities/nodes/sort/domain/model/sort";
import { getSchemaDefaultSort } from "@/entities/nodes/sort/domain/rules/get-schema-default-sort";
import { AddSortPicker } from "@/entities/nodes/sort/ui/add-sort-picker";
import { useSort } from "@/entities/nodes/sort/ui/hooks/use-sort";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

interface SortEditorProps {
  schema: ModelSchema;
}
export function SortEditor({ schema }: SortEditorProps) {
  const { sort, setSort } = useSort(schema);

  const currentSort: Sort[] = sort ?? getSchemaDefaultSort(schema) ?? [];

  const addSort = (newSort: Sort) => {
    const withoutField = currentSort.filter((existing) => existing.field !== newSort.field);
    setSort([...withoutField, newSort]);
  };

  if (currentSort.length === 0) {
    return <AddSortPicker schema={schema} onSelect={addSort} />;
  }

  // TODO: managing active sorting, it's a placeholder
  return (
    <AddSortPicker
      schema={schema}
      activeFields={new Set(currentSort.map((sort) => sort.field))}
      onSelect={addSort}
    />
  );
}
