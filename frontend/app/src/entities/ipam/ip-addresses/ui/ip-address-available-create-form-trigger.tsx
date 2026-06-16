import { Sheet, Tooltip } from "@infrahub/ui";
import React from "react";

import { queryClient } from "@/shared/api/rest/client";
import { SlideOverTitle } from "@/shared/components/display/slide-over";
import ObjectForm from "@/shared/components/form/object-form";

import {
  type IPAddressAvailableIdentifierProps,
  IpAddressAvailableIdentifier,
} from "@/entities/ipam/ip-addresses/ui/ip-address-available-identifier";
import { useObjectTableContext } from "@/entities/nodes/object/ui/object-table/object-table-context";
import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";
import type { NodeAttributeWithMetadata } from "@/entities/nodes/types";

export function IpAddressAvailableCreateFormTrigger(props: IPAddressAvailableIdentifierProps) {
  const { selectedSchema, permission } = useObjectTableContext();
  const [isCreateFormOpen, setIsCreateFormOpen] = React.useState(false);

  const isCreationAllowed = permission.create.isAllowed;

  return (
    <>
      <Tooltip message={!isCreationAllowed && permission.create.message} placement="right">
        <IpAddressAvailableIdentifier onClick={() => setIsCreateFormOpen(true)} {...props} />
      </Tooltip>

      <Sheet isOpen={isCreateFormOpen} onOpenChange={setIsCreateFormOpen}>
        <SlideOverTitle
          schema={selectedSchema}
          currentObjectLabel="New"
          title={`Create ${selectedSchema.label}`}
          subtitle={selectedSchema.description}
        />
        <ObjectForm
          onSuccess={async () => {
            await queryClient.invalidateQueries({ queryKey: objectQueryKeys.all });
            setIsCreateFormOpen(false);
          }}
          currentObject={{
            address: {
              value: props.ipAddressAvailableNode.address.value,
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
      </Sheet>
    </>
  );
}
