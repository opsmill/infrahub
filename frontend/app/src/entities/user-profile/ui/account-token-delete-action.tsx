import { Icon } from "@iconify-icon/react";
import { useState } from "react";

import type { AccountTokenNode } from "@/shared/api/graphql/generated/graphql";
import { queryClient } from "@/shared/api/rest/client";
import { Button, type ButtonProps } from "@/shared/components/ui/button";

import ModalDeleteObject from "@/entities/nodes/object/ui/modal-delete-object";
import { getInfrahubAccountTokenQueryOptions } from "@/entities/user-profile/ui/queries/get-infrahub-account-token.query";

export interface AccountTokenDeleteActionProps extends Omit<ButtonProps, "onClick"> {
  token: AccountTokenNode;
}

export function AccountTokenDeleteAction({ token, ...props }: AccountTokenDeleteActionProps) {
  const [tokenToDelete, setTokenToDelete] = useState<AccountTokenNode>();

  const handleClose = () => setTokenToDelete(undefined);

  const handleDelete = async () => {
    await queryClient.invalidateQueries(getInfrahubAccountTokenQueryOptions());
    handleClose();
  };

  return (
    <>
      <Button
        variant="ghost"
        size="icon"
        onClick={() => setTokenToDelete(token)}
        aria-label={`Delete token ${token.name}`}
        {...props}
      >
        <Icon icon="mdi:delete" className="text-lg text-red-500" />
      </Button>

      {tokenToDelete && (
        <ModalDeleteObject
          isOpen
          label={token.name}
          rowToDelete={tokenToDelete}
          onOpenChange={handleClose}
          onDelete={handleDelete}
        />
      )}
    </>
  );
}
