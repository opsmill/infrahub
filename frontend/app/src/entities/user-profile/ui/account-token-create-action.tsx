import { ACCOUNT_TOKEN_OBJECT } from "@/config/constants";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";
import { getInfrahubAccountTokenQueryOptions } from "@/entities/user-profile/domain/get-infrahub-account-token.query";
import { AccountTokenCreateForm } from "@/entities/user-profile/ui/account-token-create-form";
import { queryClient } from "@/shared/api/rest/client";
import { Button } from "@/shared/components/buttons/button-primitive";
import { Col } from "@/shared/components/container";
import SlideOver, { SlideOverTitle } from "@/shared/components/display/slide-over";
import { TokenInput } from "@/shared/components/display/token-input";
import ModalSuccess from "@/shared/components/modals/modal-success";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { useState } from "react";

export function AccountTokenCreateAction() {
  const [newToken, setNewToken] = useState<string>("");
  const [isFormOpen, setIsFormOpen] = useState(false);
  const schemaList = useAtomValue(nodeSchemasAtom);
  const schema = schemaList.find((schema) => schema.kind === ACCOUNT_TOKEN_OBJECT);

  return (
    <>
      <Button className="ml-auto" onClick={() => setIsFormOpen(true)}>
        <Icon icon="mdi:plus" className="text-sm mr-1.5" />
        Add account token
      </Button>

      <SlideOver
        title={
          <SlideOverTitle
            schema={schema}
            currentObjectLabel="New"
            title="Create new account token"
            subtitle={schema.description}
          />
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
            <Col className="text-sm gap-0 items-center">
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
