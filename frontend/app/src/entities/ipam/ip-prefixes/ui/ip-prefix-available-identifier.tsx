import { Button, type ButtonProps, Tooltip } from "@infrahub/ui";
import { PlusIcon } from "lucide-react";
import React from "react";

import { queryClient } from "@/shared/api/rest/client";
import { Row } from "@/shared/components/container";
import { classNames } from "@/shared/utils/common";

import type { IpPrefixNode } from "@/entities/ipam/ip-prefixes/domain/model/ip-prefix";
import { IpPrefixCreateSheet } from "@/entities/ipam/ip-prefixes/ui/ip-prefix-create-sheet";
import { useObjectTableContext } from "@/entities/nodes/object/ui/object-table/object-table-context";
import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";

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
            "gap-2.5 rounded-full px-2.5 pl-1.5 text-subtle-muted hover:underline",
            className
          )}
          onPress={() => setIsCreateFormOpen(true)}
          {...props}
        >
          <PlusIcon className="size-4 text-subtle-muted" />

          <Row className="gap-2.5">
            {[...Array(ancestorsCount)].map((_, i) => (
              <div className="size-1 rounded-full bg-border-strong" key={i} />
            ))}
            {ipPrefixNode.display_label}
          </Row>
        </Button>
      </Tooltip>

      <IpPrefixCreateSheet
        schema={selectedSchema}
        prefix={ipPrefixNode.display_label}
        isOpen={isCreateFormOpen}
        onOpenChange={setIsCreateFormOpen}
        onSuccess={() => {
          setIsCreateFormOpen(false);
          queryClient.invalidateQueries({ queryKey: objectQueryKeys.all });
        }}
      />
    </>
  );
}
