import { Icon } from "@iconify-icon/react";
import { useState } from "react";

import { queryClient } from "@/shared/api/rest/client";
import { Button } from "@/shared/components/buttons/button-primitive";
import { Col, Row } from "@/shared/components/container";
import SlideOver from "@/shared/components/display/slide-over";
import { TokenInput } from "@/shared/components/display/token-input";
import ModalSuccess from "@/shared/components/modals/modal-success";

import { ObjectHelpButton } from "@/entities/nodes/object/ui/object-help-button";
import { getInfrahubAccountTokenQueryOptions } from "@/entities/user-profile/domain/get-infrahub-account-token.query";
import { AccountTokenCreateForm } from "@/entities/user-profile/ui/account-token-create-form";

export function AccountTokenCreateAction() {
  const [newToken, setNewToken] = useState<string>("");
  const [isFormOpen, setIsFormOpen] = useState(false);

  return (
    <>
      <Button className="ml-auto" onClick={() => setIsFormOpen(true)}>
        <Icon icon="mdi:plus" className="mr-1.5 text-sm" />
        Add account token
      </Button>

      <SlideOver
        title={
          <Col>
            <Row>
              <h3 className="font-semibold text-lg">Create a new token</h3>
              <ObjectHelpButton
                documentationUrl="/guides/managing-api-tokens"
                className="ml-auto"
              />
            </Row>
            <span className="text-gray-500 text-sm">
              These tokens provide full access to your account. Please keep them secure.
            </span>
          </Col>
        }
        open={isFormOpen}
        setOpen={setIsFormOpen}
      >
        <AccountTokenCreateForm
          onSuccess={async ({ token }) => {
            setNewToken(token);
            setIsFormOpen(false);
            await queryClient.invalidateQueries(getInfrahubAccountTokenQueryOptions());
          }}
        />
      </SlideOver>

      {newToken && (
        <ModalSuccess
          open
          title="Token created"
          setOpen={() => setNewToken("")}
          onConfirm={() => setNewToken("")}
          icon="mdi:key"
        >
          <Col className="items-center">
            <Col className="items-center gap-0 text-sm">
              <span>Please copy your token now.</span>
              <b className="font-semibold">For security reasons we cannot show it again.</b>
            </Col>
            <TokenInput value={newToken} />
          </Col>
        </ModalSuccess>
      )}
    </>
  );
}
