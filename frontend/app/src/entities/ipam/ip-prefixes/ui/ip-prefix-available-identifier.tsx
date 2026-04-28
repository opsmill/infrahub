import { Button, type ButtonProps } from "@infrahub/ui";
import { PlusIcon } from "lucide-react";
import React from "react";

import { queryClient } from "@/shared/api/rest/client";
import { Tooltip } from "@/shared/components/aria/tooltip";
import { Row } from "@/shared/components/container";
import SlideOver, { SlideOverTitle } from "@/shared/components/display/slide-over";
import ObjectForm from "@/shared/components/form/object-form";
import { classNames } from "@/shared/utils/common";

import type { IpPrefixNode } from "@/entities/ipam/ip-prefixes/types";
import { useObjectTableContext } from "@/entities/nodes/object/ui/object-table/object-table-context";
import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";
import type { NodeAttributeWithMetadata } from "@/entities/nodes/types";

export interface IpPrefixAvailableIdentifierProps extends ButtonProps {
  ipPrefixNode: IpPrefixNode;
}

export function IpPrefixAvailableIdentifier({
  className,
  ipPrefixNode,
  ...props
}: IpPrefixAvailableIdentifierProps) {
  const { selectedSchema, permission } = useObjectTableContext();
  const [isCreateFormOpen, setIsCreateFormOpen] = React.useState(false);

  const parentNode = ipPrefixNode.parent?.node;
  const ancestorsCount: number = (parentNode?.ancestors?.count ?? 0) + 1;
  const isCreationAllowed = permission.create.isAllowed;

  return (
    <>
      <Tooltip message={permission.create.message} placement="right">
        <Button
          variant="ghost"
          size="sm"
          isDisabledAndFocusable={!isCreationAllowed}
          className={classNames(
            "gap-2.5 rounded-full px-2.5 pl-1.5 text-neutral-400 hover:underline",
            className
          )}
          onPress={() => setIsCreateFormOpen(true)}
          {...props}
        >
          <PlusIcon className="size-4 text-neutral-300" />

          <Row className="gap-2.5">
            {[...Array(ancestorsCount)].map((_, i) => (
              <div className="size-1 rounded-full bg-neutral-300" key={i} />
            ))}
            {ipPrefixNode.display_label}
          </Row>
        </Button>
      </Tooltip>

      <SlideOver
        title={
          <SlideOverTitle
            schema={selectedSchema}
            currentObjectLabel="New"
            title={`Create ${selectedSchema.label}`}
            subtitle={selectedSchema.description}
          />
        }
        open={isCreateFormOpen}
        setOpen={setIsCreateFormOpen}
      >
        <ObjectForm
          onSuccess={() => {
            setIsCreateFormOpen(false);
            queryClient.invalidateQueries({ queryKey: objectQueryKeys.all });
          }}
          currentObject={{
            prefix: {
              value: ipPrefixNode.display_label ?? null,
              is_default: false,
              is_from_profile: false,
              is_protected: false,
              is_visible: true,
              owner: null,
              source: null,
              updated_at: new Date().toISOString(),
            } satisfies NodeAttributeWithMetadata,
          }}
          onCancel={() => setIsCreateFormOpen(false)}
          kind={selectedSchema.kind!}
        />
      </SlideOver>
    </>
  );
}
