import { gql } from "@apollo/client";
import { useId, useState } from "react";

import { PROFILE_KIND, TEMPLATE_GENERIC_KIND } from "@/config/constants";

import useQuery from "@/shared/api/graphql/useQuery";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { Badge } from "@/shared/components/ui/badge";
import {
  Combobox,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxItem,
  ComboboxList,
  ComboboxTrigger,
} from "@/shared/components/ui/combobox";
import Label from "@/shared/components/ui/label";

import { getObjectPermissionsQuery } from "@/entities/permission/queries/getObjectPermissions";
import type { PermissionData } from "@/entities/permission/types";
import { getPermission } from "@/entities/permission/utils";
import { getSchema } from "@/entities/schema/domain/get-schema";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

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
  const { schema } = useSchema(value);
  const [open, setOpen] = useState(false);
  const { data, loading } = useQuery(gql(getObjectPermissionsQuery(currentKind)));

  if (loading) return <LoadingIndicator className="p-4" />;

  const permissionsData: Array<{ node: PermissionData }> = data?.[currentKind]?.permissions?.edges;

  const items = kindInheritingFromGeneric
    .map((usedByKind) => {
      const { schema: relatedSchema } = getSchema(usedByKind);

      if (!relatedSchema) return;

      // When choosing a profile/template, display information about the related node instead
      if (currentKind === PROFILE_KIND || currentKind === TEMPLATE_GENERIC_KIND) {
        const relationship = relatedSchema.relationships?.find(
          (relationship) => relationship.name === "related_nodes"
        );

        const { schema: nodeSchema } = getSchema(relationship?.peer);

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
    <div className="bg-gray-200 p-4">
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
    <div className="flex w-full justify-between">
      <span>{label}</span> <Badge>{badge}</Badge>
    </div>
  );
};
