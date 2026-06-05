import { Button, type ButtonProps } from "@infrahub/ui";
import { Trash2Icon } from "lucide-react";
import { useState } from "react";

import type { AccountTokenNode } from "@/shared/api/graphql/generated/types";
import { queryClient } from "@/shared/api/rest/client";

import ModalDeleteObject from "@/entities/nodes/object/ui/modal-delete-object";
import { getInfrahubAccountTokenQueryOptions } from "@/entities/user-profile/ui/queries/get-infrahub-account-token.query";

export interface AccountTokenDeleteActionProps extends Omit<ButtonProps, "onPress"> {
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
        shape="square"
        onPress={() => setTokenToDelete(token)}
        aria-label={`Delete token ${token.name}`}
        {...props}
      >
        <Trash2Icon className="text-red-600" />
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
