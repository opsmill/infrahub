import { useObjects } from "@/entities/nodes/object/domain/get-objects.query";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import { NodeObject } from "@/entities/nodes/types";
import { TemplateSchema } from "@/entities/schema/types";
import {
  ComboboxEmpty,
  ComboboxItem,
  ComboboxList,
  ComboboxListProps,
} from "@/shared/components/ui/combobox";
import { Spinner } from "@/shared/components/ui/spinner";

export interface ObjectTemplateAutocompleteProps extends Omit<ComboboxListProps, "onSelect"> {
  templateSchema: TemplateSchema;
  onSelect: (node: NodeObject) => void;
}

export function ObjectTemplateAutocomplete({
  templateSchema,
  onSelect,
  ...props
}: ObjectTemplateAutocompleteProps) {
  const { data, isPending, error } = useObjects({ schema: templateSchema });

  if (error) {
    return <div>Error: {error.message}</div>;
  }

  return (
    <ComboboxList {...props}>
      {isPending && <Spinner className="flex justify-center m-2" />}

      <ComboboxEmpty>No template found</ComboboxEmpty>

      {data?.pages.flat().map((node) => (
        <ComboboxItem key={node.id} value={node.id} onSelect={() => onSelect(node)}>
          <span className="truncate">{getNodeLabel(node)}</span>
        </ComboboxItem>
      ))}
    </ComboboxList>
  );
}
