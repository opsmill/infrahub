import { Button, Modal, Sheet } from "@infrahub/ui";
import { useState } from "react";
import { Heading } from "react-aria-components";

import { queryClient } from "@/shared/api/rest/client";
import { CopyToClipboard } from "@/shared/components/buttons/copy-to-clipboard";
import { Col, Row } from "@/shared/components/container";
import { Icon } from "@/shared/components/display/icon";

import { ObjectHelpButton } from "@/entities/nodes/object/ui/object-help-button";
import { AccountTokenCreateForm } from "@/entities/user-profile/ui/account-token-create-form";
import { getInfrahubAccountTokenQueryOptions } from "@/entities/user-profile/ui/queries/get-infrahub-account-token.query";

export function AccountTokenCreateAction() {
  const [newToken, setNewToken] = useState<string>("");
  const [isFormOpen, setIsFormOpen] = useState(false);

  return (
    <>
      <Button className="ml-auto" onPress={() => setIsFormOpen(true)}>
        <Icon icon="mdi:plus" className="text-sm" />
        Add account token
      </Button>

      <Sheet isOpen={isFormOpen} onOpenChange={setIsFormOpen}>
        <Col className="mb-4">
          <Row>
            <h3 className="font-semibold text-lg">Create a new token</h3>
            <ObjectHelpButton
              documentationUrl="/deploy-manage/user-management/managing-api-tokens"
              className="ml-auto"
            />
          </Row>
          <span className="text-foreground-muted text-sm">
            These tokens provide full access to your account. Please keep them secure.
          </span>
        </Col>

        <AccountTokenCreateForm
          onSuccess={async ({ token }) => {
            setNewToken(token);
            setIsFormOpen(false);
            await queryClient.invalidateQueries(getInfrahubAccountTokenQueryOptions());
          }}
          onCancel={() => setIsFormOpen(false)}
        />
      </Sheet>

      <Modal
        isOpen={!!newToken}
        isDismissable={false}
        onOpenChange={(isOpen) => !isOpen && setNewToken("")}
      >
        <Col className="p-3">
          <Heading slot="title" className="flex items-center gap-2 font-semibold">
            <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-custom-blue-600 dark:bg-custom-blue-500/30">
              <Icon icon="mdi:key-variant" className="text-white dark:text-custom-blue-300" />
            </div>
            Token created
          </Heading>

          <div className="px-8 py-4">
            <p>Please copy your token now.</p>
            <p className="font-semibold">For security reasons we cannot show it again.</p>
          </div>

          <Row>
            <div className="h-9 grow rounded-md bg-content-strong p-2">{newToken}</div>
            <CopyToClipboard text={newToken} shape="square" variant="outline" />
          </Row>
        </Col>

        <Row className="justify-end bg-content-muted p-3">
          <Button variant="primary" onPress={() => setNewToken("")}>
            Confirm
          </Button>
        </Row>
      </Modal>
    </>
  );
}
