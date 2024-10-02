import { useAtomValue } from "jotai/index";
import { genericsState, profilesAtom, schemaState } from "@/state/atoms/schema.atom";
import {
  Combobox,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxList,
  ComboboxTrigger,
} from "@/components/ui/combobox";
import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { getObjectDetailsUrl2 } from "@/utils/objects";
import { CommandItem } from "@/components/ui/command";
import { MENU_EXCLUDELIST } from "@/config/constants";
import { Badge } from "@/components/ui/badge";

export default function BreadcrumbSchemaSelector({ kind }: { kind: string }) {
  const generics = useAtomValue(genericsState);
  const nodes = useAtomValue(schemaState);
  const profiles = useAtomValue(profilesAtom);
  const navigate = useNavigate();
  const [isOpen, setIsOpen] = useState(false);

  const models = [...generics, ...nodes, ...profiles]
    .filter((schema) => !MENU_EXCLUDELIST.includes(schema.kind as string) && schema.include_in_menu)
    .sort((a, b) => (a.label as string).localeCompare(b.label as string));
  const currentSchema = models.find((schema) => schema.kind === kind);

  return (
    <Combobox open={isOpen} onOpenChange={setIsOpen}>
      <ComboboxTrigger className="w-auto h-auto border-none hover:bg-gray-100 py-1 px-2">
        {currentSchema?.label}
      </ComboboxTrigger>

      <ComboboxContent align="start">
        <ComboboxList fitTriggerWidth={false}>
          <ComboboxEmpty>No schema found.</ComboboxEmpty>
          {models.map((node) => (
            <CommandItem
              key={node.name}
              value={node.kind!}
              onClick={() => setIsOpen(false)}
              keywords={[node.label!, node.name]}
              onSelect={(kind) => {
                setIsOpen(false);
                navigate(getObjectDetailsUrl2(kind));
              }}
              asChild>
              <Link to={getObjectDetailsUrl2(node.kind!)}>
                {node.label} <Badge className="ml-auto">{node.namespace}</Badge>
              </Link>
            </CommandItem>
          ))}
        </ComboboxList>
      </ComboboxContent>
    </Combobox>
  );
}
