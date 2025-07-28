import { reloadIpamTreeAtom } from "@/entities/ipam/ipam-tree/ipam-tree.state";
import { useObjectTableContext } from "@/entities/nodes/object/ui/object-table/object-table-context";
import { NodeCore } from "@/entities/nodes/types";
import { queryClient } from "@/shared/api/rest/client";
import { Button, ButtonProps } from "@/shared/components/buttons/button-primitive";
import { Row } from "@/shared/components/container";
import SlideOver, { SlideOverTitle } from "@/shared/components/display/slide-over";
import ObjectForm from "@/shared/components/form/object-form";
import { Tooltip } from "@/shared/components/ui/tooltip";
import { classNames } from "@/shared/utils/common";
import { useSetAtom } from "jotai/index";
import { PlusIcon } from "lucide-react";
import React from "react";

export interface IpPrefixAvailableIdentifierProps extends ButtonProps {
  prefixNode: NodeCore & { parent?: { node: NodeCore & { ancestors: { count: number } } } };
}

export function IpPrefixAvailableIdentifier({
  className,
  prefixNode,
  ...props
}: IpPrefixAvailableIdentifierProps) {
  const { selectedSchema, permission } = useObjectTableContext();
  const [isCreateFormOpen, setIsCreateFormOpen] = React.useState(false);
  const reloadIpamTree = useSetAtom(reloadIpamTreeAtom);

  const parentNode = prefixNode.parent?.node;
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
            "rounded-full px-2.5 pl-1.5 hover:underline hover:bg-gray-400/10 gap-3.75",
            isCreationAllowed && "hover:bg-gray-50",
            className
          )}
          onClick={() => setIsCreateFormOpen(true)}
          {...props}
        >
          <div className="size-4 mr-px flex items-center justify-center">
            <PlusIcon className="size-4 text-gray-300" />
          </div>

          <Row className="gap-2.5">
            {[...Array(ancestorsCount)].map((_, i) => (
              <div className="bg-gray-300 size-1 rounded-full" key={i} />
            ))}
            {prefixNode.display_label}
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
            queryClient.invalidateQueries({
              predicate: (query) => query.queryKey.includes("objects"),
            });

            if (location.pathname.startsWith("/ipam")) {
              reloadIpamTree(parentNode?.id);
            }
          }}
          currentObject={{ prefix: { value: prefixNode.display_label } }}
          onCancel={() => setIsCreateFormOpen(false)}
          kind={selectedSchema.kind!}
        />
      </SlideOver>
    </>
  );
}
