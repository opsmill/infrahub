import { PlusIcon } from "lucide-react";
import React from "react";

import { queryClient } from "@/shared/api/rest/client";
import { Row } from "@/shared/components/container";
import SlideOver, { SlideOverTitle } from "@/shared/components/display/slide-over";
import ObjectForm from "@/shared/components/form/object-form";
import { Button, type ButtonProps } from "@/shared/components/ui/button";
import { Tooltip } from "@/shared/components/ui/tooltip";
import { classNames } from "@/shared/utils/common";

import type { IpPrefixNode } from "@/entities/ipam/ip-prefixes/types";
import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";
import { useObjectTableContext } from "@/entities/nodes/object/ui/object-table/object-table-context";
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
      <Tooltip
        enabled={!isCreationAllowed}
        content={!isCreationAllowed && permission.create.message}
        side="right"
      >
        <Button
          variant="ghost"
          size="sm"
          disabled={!isCreationAllowed}
          className={classNames(
            "gap-3.75 rounded-full px-2.5 pl-1.5 hover:bg-gray-400/10 hover:underline disabled:opacity-100",
            className
          )}
          onClick={() => setIsCreateFormOpen(true)}
          {...props}
        >
          <div className="mr-px flex size-4 items-center justify-center">
            <PlusIcon className="size-4 text-gray-300" />
          </div>

          <Row className="gap-2.5">
            {[...Array(ancestorsCount)].map((_, i) => (
              <div className="size-1 rounded-full bg-gray-300" key={i} />
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
