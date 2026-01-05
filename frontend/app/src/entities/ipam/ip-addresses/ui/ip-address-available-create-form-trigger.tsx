import React from "react";

import { queryClient } from "@/shared/api/rest/client";
import SlideOver, { SlideOverTitle } from "@/shared/components/display/slide-over";
import ObjectForm from "@/shared/components/form/object-form";
import { Tooltip } from "@/shared/components/ui/tooltip";

import {
  type IPAddressAvailableIdentifierProps,
  IpAddressAvailableIdentifier,
} from "@/entities/ipam/ip-addresses/ui/ip-address-available-identifier";
import { objectQueryKeys } from "@/entities/nodes/object/domain/object.query-keys";
import { useObjectTableContext } from "@/entities/nodes/object/ui/object-table/object-table-context";

export function IpAddressAvailableCreateFormTrigger(props: IPAddressAvailableIdentifierProps) {
  const { selectedSchema, permission } = useObjectTableContext();
  const [isCreateFormOpen, setIsCreateFormOpen] = React.useState(false);

  const isCreationAllowed = permission.create.isAllowed;

  return (
    <>
      <Tooltip
        enabled={!isCreationAllowed}
        content={!isCreationAllowed && permission.create.message}
        side="right"
      >
        <IpAddressAvailableIdentifier onClick={() => setIsCreateFormOpen(true)} {...props} />
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
          onSuccess={async () => {
            await queryClient.invalidateQueries({ queryKey: objectQueryKeys.all });
            setIsCreateFormOpen(false);
          }}
          currentObject={{ address: { value: props.ipAddressAvailableNode.address.value } }}
          onCancel={() => setIsCreateFormOpen(false)}
          kind={selectedSchema.kind!}
        />
      </SlideOver>
    </>
  );
}
