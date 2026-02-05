import { Icon } from "@iconify-icon/react";
import { useState } from "react";
import { Heading } from "react-aria-components";

import { queryClient } from "@/shared/api/rest/client";
import { Modal } from "@/shared/components/aria/modal";
import { CopyToClipboard } from "@/shared/components/buttons/copy-to-clipboard";
import { Col, Row } from "@/shared/components/container";
import SlideOver from "@/shared/components/display/slide-over";
import { Button } from "@/shared/components/ui/button";

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

      <Modal
        isOpen={!!newToken}
        isDismissable={false}
        onOpenChange={(isOpen) => !isOpen && setNewToken("")}
        className="p-0"
      >
        <Col className="p-3">
          <Heading slot="title" className="flex items-center gap-2 font-semibold">
            <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-custom-blue-600">
              <Icon icon="mdi:key-variant" className="text-white" />
            </div>
            Token created
          </Heading>

          <div className="px-8 py-4">
            <p>Please copy your token now.</p>
            <p className="font-semibold">For security reasons we cannot show it again.</p>
          </div>

          <Row>
            <div className="h-9 grow rounded-md bg-gray-100 p-2">{newToken}</div>
            <CopyToClipboard text={newToken} size="square" variant="outline" />
          </Row>
        </Col>

        <Row className="justify-end bg-gray-50 p-3">
          <Button variant="primary" onClick={() => setNewToken("")}>
            Confirm
          </Button>
        </Row>
      </Modal>
    </>
  );
}
