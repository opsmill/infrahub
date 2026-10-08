import { useAtomValue } from "jotai";
import { useState } from "react";

import { Badge } from "@/shared/components/ui/badge";
import {
  Combobox,
  ComboboxContent,
  ComboboxItem,
  ComboboxList,
  ComboboxTrigger,
} from "@/shared/components/ui/combobox";
import { FormInput } from "@/shared/components/ui/form";

import { ATTRIBUTE_KIND } from "@/entities/schema/domain/model/attribute-kind";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";
import { genericSchemasAtom, nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

type AllocatableSchema = ModelSchema & { kind: string };

function isAllocatable(schema: ModelSchema): schema is AllocatableSchema {
  return (
    !!schema.kind &&
    !!schema.attributes?.some(
      (attribute) => attribute.kind === ATTRIBUTE_KIND.NUMBER && !attribute.read_only
    )
  );
}

export function NodeLabel({ schema }: { schema: ModelSchema }) {
  return (
    <span className="flex w-full justify-between">
      {schema.label} <Badge>{schema.namespace}</Badge>
    </span>
  );
}

interface NodeComboboxProps {
  value?: string;
  onSelect: (kind: string | null) => void;
}

export function NodeCombobox({ value, onSelect }: NodeComboboxProps) {
  const [open, setOpen] = useState(false);
  const nodes = useAtomValue(nodeSchemasAtom);
  const generics = useAtomValue(genericSchemasAtom);
  const { schema: selectedNode } = useSchema(value);
  const options = [...generics, ...nodes].filter(isAllocatable);

  return (
    <Combobox open={open} onOpenChange={setOpen}>
      <FormInput>
        <ComboboxTrigger>{selectedNode && <NodeLabel schema={selectedNode} />}</ComboboxTrigger>
      </FormInput>
      <ComboboxContent>
        <ComboboxList>
          {options.map((node) => (
            <ComboboxItem
              key={node.id}
              selectedValue={selectedNode?.kind}
              value={node.kind}
              keywords={[node.label ?? node.kind]}
              onSelect={() => {
                onSelect(node.kind === selectedNode?.kind ? null : node.kind);
                setOpen(false);
              }}
            >
              <NodeLabel schema={node} />
            </ComboboxItem>
          ))}
        </ComboboxList>
      </ComboboxContent>
    </Combobox>
  );
}
