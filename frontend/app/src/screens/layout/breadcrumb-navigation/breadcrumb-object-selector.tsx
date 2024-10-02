import { useSchema } from "@/hooks/useSchema";
import { useObjectItems } from "@/hooks/useObjectItems";
import { Combobox, ComboboxContent, ComboboxList, ComboboxTrigger } from "@/components/ui/combobox";
import React, { useState } from "react";
import { IModelSchema } from "@/state/atoms/schema.atom";
import { Spinner } from "@/components/ui/spinner";
import { CommandEmpty, CommandItem } from "@/components/ui/command";
import { Link, useNavigate } from "react-router-dom";
import { getObjectDetailsUrl2 } from "@/utils/objects";

export default function BreadcrumbObjectSelector({ kind, id }: { kind: string; id: string }) {
  const { schema } = useSchema(kind);

  if (!schema) return <Spinner className="mx-2" />;

  return <ObjectSelector schema={schema} id={id} />;
}

const ObjectSelector = ({ schema, id }: { schema: IModelSchema; id: string }) => {
  const { data, loading } = useObjectItems(schema ?? undefined);
  const navigate = useNavigate();
  const [isOpen, setIsOpen] = useState(false);

  if (loading) return <Spinner className="mx-2" />;

  const objectData = data?.[schema.kind!];
  const currentObject = objectData.edges.find((edge: any) => edge.node.id === id)?.node;
  const objectList = objectData.edges.map((edge: any) => edge.node);

  return (
    <Combobox open={isOpen} onOpenChange={setIsOpen}>
      <ComboboxTrigger className="w-auto h-auto border-none hover:bg-gray-100 py-1 px-2">
        {currentObject?.display_label}
      </ComboboxTrigger>

      <ComboboxContent align="start">
        <ComboboxList fitTriggerWidth={false}>
          <CommandEmpty>No {schema.label} found.</CommandEmpty>
          {objectList.map((node: any) => {
            const objectUrl = getObjectDetailsUrl2(node.__typename, node.id);
            return (
              <CommandItem
                key={node.id}
                value={node.id}
                keywords={[node.display_label]}
                onSelect={() => {
                  setIsOpen(false);
                  navigate(objectUrl);
                }}>
                <Link to={objectUrl}>{node.display_label}</Link>
              </CommandItem>
            );
          })}
        </ComboboxList>
      </ComboboxContent>
    </Combobox>
  );
};
