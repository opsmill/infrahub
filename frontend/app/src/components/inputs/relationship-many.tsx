import React, { useState } from "react";
import {
  Combobox,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxItem,
  ComboboxList,
} from "@/components/ui/combobox";
import { IModelSchema } from "@/state/atoms/schema.atom";
import { Node, RelationshipManyType } from "@/utils/getObjectItemDisplayValue";
import { Badge } from "@/components/ui/badge";
import { useLazyQuery } from "@/hooks/useQuery";
import { generateRelationshipListQuery } from "@/graphql/queries/objects/generateRelationshipListQuery";
import { gql } from "@apollo/client";
import { RelationshipSchema } from "@/screens/schema/types";
import { Spinner } from "@/components/ui/spinner";
import { Button } from "@/components/buttons/button-primitive";
import { PopoverTrigger } from "@/components/ui/popover";
import { Icon } from "@iconify-icon/react";
import { classNames } from "@/utils/common";
import { inputStyle } from "@/components/ui/style";
import { PopoverTriggerProps } from "@radix-ui/react-popover";
import SlideOver, { SlideOverTitle } from "@/components/display/slide-over";
import ObjectForm from "@/components/form/object-form";
import { useSchema } from "@/hooks/useSchema";

export interface RelationshipManyInputProps
  extends Omit<PopoverTriggerProps, "value" | "onChange"> {
  className?: string;
  onChange: (value: Array<Node>) => void;
  relationship: RelationshipSchema;
  schema: IModelSchema;
  value: Array<Node> | null;
}

export const RelationshipManyInput = React.forwardRef<
  React.ElementRef<typeof PopoverTrigger>,
  RelationshipManyInputProps
>(({ id, className, relationship: relationshipSchema, schema, value, onChange, ...props }, ref) => {
  const [open, setOpen] = React.useState(false);
  const [loadComboboxList, { loading, data }] = useLazyQuery(
    gql(generateRelationshipListQuery({ relationshipSchema }))
  );

  const handleSelect = (relationship: Node) => {
    onChange(value ? [...value, relationship] : [relationship]);
  };

  return (
    <Combobox open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <div
          className={classNames(
            inputStyle,
            "has-[>:last-child:focus-visible]:outline-none has-[>:last-child:focus-visible]:ring-2 has-[>:last-child:focus-visible]:ring-custom-blue-500 has-[>:last-child:focus-visible]:ring-offset-2",
            " cursor-pointer",
            className
          )}>
          <div className="flex-grow flex flex-wrap gap-2">
            {value?.map(({ id, display_label }) => (
              <Badge key={id} className="flex items-center gap-1 pr-0.5">
                {display_label}

                <Button
                  size="icon"
                  variant="ghost"
                  onClick={(e) => {
                    e.stopPropagation();
                    onChange(value.filter((item) => item.id !== id));
                  }}
                  className="text-gray-500 hover:text-gray-800 h-4 w-4"
                  aria-label="Remove">
                  &times;
                </Button>
              </Badge>
            ))}
          </div>
          {loading && <Spinner className="ml-auto" />}
          <PopoverTrigger ref={ref} asChild {...props}>
            <button id={id} type="button" className="text-gray-600 outline-none w-3.5 h-3.5">
              <Icon icon="mdi:unfold-more-horizontal" />
            </button>
          </PopoverTrigger>
        </div>
      </PopoverTrigger>

      <ComboboxContent onOpenAutoFocus={() => loadComboboxList()}>
        <ComboboxList>
          <ComboboxEmpty>No results found</ComboboxEmpty>
          {!loading &&
            data &&
            (data[relationshipSchema.peer] as RelationshipManyType).edges
              .map((edge) => edge.node)
              .filter((node): node is Node => !!node && !value?.some((v) => v.id === node.id))
              .map((relationship) => (
                <ComboboxItem
                  key={relationship.id}
                  value={relationship.display_label}
                  onSelect={() => handleSelect(relationship)}>
                  <span className="truncate">{relationship.display_label}</span>
                </ComboboxItem>
              ))}
        </ComboboxList>

        <AddRelationshipAction relationship={relationshipSchema} onSuccess={handleSelect} />
      </ComboboxContent>
    </Combobox>
  );
});

export interface AddRelationshipActionProps {
  relationship: RelationshipSchema;
  onSuccess?: (newObject: Node) => void;
}

const AddRelationshipAction: React.FC<AddRelationshipActionProps> = ({
  relationship,
  onSuccess,
}) => {
  const { schema } = useSchema(relationship.peer);
  const [open, setOpen] = useState(false);

  if (!schema) return null;

  return (
    <div className="p-2 pt-0">
      <Button
        className="w-full bg-custom-blue-700/10 border border-custom-blue-700/20 text-custom-blue-700 enabled:hover:bg-custom-blue-700/20"
        onClick={() => setOpen(!open)}>
        + Add new {schema.label}
      </Button>

      <SlideOver
        title={
          <SlideOverTitle
            schema={schema}
            currentObjectLabel="New"
            title={`Create ${schema.label}`}
            subtitle={schema.description}
          />
        }
        offset={1}
        open={open}
        setOpen={setOpen}>
        <ObjectForm
          kind={relationship.peer}
          onSuccess={({ object }) => {
            setOpen(false);
            if (!onSuccess) return;

            const newNode: Node = {
              id: object.id,
              display_label: object.display_label,
              __typename: relationship.peer,
            };
            onSuccess(newNode);
          }}
          onCancel={() => setOpen(false)}
          data-testid="new-object-form"
        />
      </SlideOver>
    </div>
  );
};
