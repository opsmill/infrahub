import { ACCOUNT_TOKEN_OBJECT } from "@/config/constants";
import { PERMISSION_ALLOW_ALL } from "@/entities/permission/constants";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";
import { getInfrahubAccountTokenQueryOptions } from "@/entities/user-profile/domain/get-infrahub-account-token.query";
import { queryClient } from "@/shared/api/rest/client";
import { TokenInput } from "@/shared/components/display/token-input";
import { ObjectCreateFormTrigger } from "@/shared/components/form/object-create-form-trigger";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import ModalSuccess from "@/shared/components/modals/modal-success";
import { useAtomValue } from "jotai";
import { useState } from "react";

type AccountTokenCreateResponse = {
  object: {
    token: {
      value: string;
    };
  };
};

export function AccountTokenCreateAction() {
  const [result, setResult] = useState<AccountTokenCreateResponse>();
  const schemaList = useAtomValue(nodeSchemasAtom);
  const schema = schemaList.find((schema) => schema.kind === ACCOUNT_TOKEN_OBJECT);

  if (!schema) return <LoadingIndicator className="p-4" />;

  const handleSuccess = async (result: AccountTokenCreateResponse) => {
    await queryClient.invalidateQueries(getInfrahubAccountTokenQueryOptions());
    setResult(result);
  };

  return (
    <>
      <ObjectCreateFormTrigger
        schema={schema}
        permission={PERMISSION_ALLOW_ALL}
        onSuccess={handleSuccess}
        className="ml-auto"
      />

      {result && (
        <ModalSuccess
          open
          title="Your API key"
          setOpen={() => setResult(undefined)}
          onConfirm={() => setResult(undefined)}
          icon="mdi:information-slab-circle-outline"
          description={
            <>
              Make sure to copy your API key now.
              <br />
              <b>You won&apos;t be able to see it again!</b>
            </>
          }
        >
          <div className="mt-2">
            <TokenInput value={result?.object.token.value} />
          </div>
        </ModalSuccess>
      )}
    </>
  );
}
