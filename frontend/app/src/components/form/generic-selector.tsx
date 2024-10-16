import { Badge } from "@/components/ui/badge";
import {
  Combobox,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxItem,
  ComboboxList,
  ComboboxTrigger,
} from "@/components/ui/combobox";
import Label from "@/components/ui/label";
import { PROFILE_KIND } from "@/config/constants";
import useQuery from "@/hooks/useQuery";
import { useSchema } from "@/hooks/useSchema";
import LoadingScreen from "@/screens/loading-screen/loading-screen";
import { getObjectPermissionsQuery } from "@/screens/permission/queries/getObjectPermissions";
import { PermissionData } from "@/screens/permission/types";
import { genericsState, profilesAtom, schemaState } from "@/state/atoms/schema.atom";
import { getPermission } from "@/utils/permissions";
import { gql } from "@apollo/client";
import { useAtomValue } from "jotai/index";
import React, { useId, useState } from "react";

type GenericSelectorProps = {
  currentKind: string;
  kindInheritingFromGeneric: string[];
  value?: string | null;
  onChange: (item: string | null) => void;
};

export const GenericSelector = ({
  currentKind,
  kindInheritingFromGeneric,
  value,
  onChange,
}: GenericSelectorProps) => {
  const id = useId();
  const nodeSchemas = useAtomValue(schemaState);
  const nodeGenerics = useAtomValue(genericsState);
  const profileSchemas = useAtomValue(profilesAtom);
  const { schema } = useSchema(value);
  const [open, setOpen] = useState(false);
  const { data, loading } = useQuery(gql(getObjectPermissionsQuery(currentKind)));

  if (loading) return <LoadingScreen />;
  const permissionsData: Array<{ node: PermissionData }> = data?.[currentKind]?.permissions?.edges;

  const items = kindInheritingFromGeneric
    .map((usedByKind) => {
      const relatedSchema = [...nodeSchemas, ...profileSchemas].find(
        (schema) => schema.kind === usedByKind
      );

      if (!relatedSchema) return;

      // When choosing a profile, display informations about the related node
      if (currentKind === PROFILE_KIND) {
        const relationship = relatedSchema.relationships?.find(
          (relationship) => relationship.name === "related_nodes"
        );

        const nodeSchema =
          relationship?.peer &&
          [...nodeSchemas, ...nodeGenerics, ...profileSchemas].find(
            (schema) => schema.kind === relationship.peer
          );

        if (!nodeSchema) return;

        return {
          value: relatedSchema.kind,
          label: nodeSchema.label ?? nodeSchema.name,
          badge: nodeSchema.namespace,
        };
      }

      return {
        value: relatedSchema.kind,
        label: relatedSchema.label ?? relatedSchema.name,
        badge: relatedSchema.namespace,
      };
    })
    .filter((item) => !!item);

  return (
    <div className="p-4 bg-gray-200">
      <Label htmlFor={id}>Select an object type</Label>
      <Combobox open={open} onOpenChange={setOpen}>
        <ComboboxTrigger id={id}>
          {schema && <SchemaItem label={schema.label as string} badge={schema.namespace} />}
        </ComboboxTrigger>

        <ComboboxContent>
          <ComboboxList>
            <ComboboxEmpty>No schema found.</ComboboxEmpty>
            {items.map((item) => {
              const itemValue = item?.value as string;
              const permissionToCreate = getPermission(
                permissionsData.filter(({ node }) => node.kind === itemValue)
              ).create;

              return (
                <ComboboxItem
                  key={itemValue}
                  value={itemValue}
                  selectedValue={value}
                  onSelect={() => {
                    onChange(value === itemValue ? null : itemValue);
                    setOpen(false);
                  }}
                  disabled={!permissionToCreate.isAllowed}
                >
                  <SchemaItem label={item.label} badge={item.badge} />
                </ComboboxItem>
              );
            })}
          </ComboboxList>
        </ComboboxContent>
      </Combobox>
    </div>
  );
};

const SchemaItem = ({ label, badge }: { label: string; badge: string }) => {
  return (
    <div className="flex justify-between w-full">
      <span>{label}</span> <Badge>{badge}</Badge>
    </div>
  );
};
