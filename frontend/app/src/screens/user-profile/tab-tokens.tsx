import { ACCOUNT_TOKEN_OBJECT } from "@/config/constants";
import { schemaState } from "@/state/atoms/schema.atom";
import { useAtomValue } from "jotai";
import { useState } from "react";
import LoadingScreen from "../loading-screen/loading-screen";
import ObjectItems from "../object-items/object-items-paginated";

import { TokenInput } from "@/components/display/token-input";
import ModalSuccess from "@/components/modals/modal-success";

export default function TabTokens() {
  const [open, setOpen] = useState(false);
  const [result, setResult] = useState();
  const schemaList = useAtomValue(schemaState);
  const schema = schemaList.find((schema) => schema.kind === ACCOUNT_TOKEN_OBJECT);

  if (!schema) return <LoadingScreen />;

  const handleSuccess = (result: any) => {
    setOpen(true);
    setResult(result);
  };

  return (
    <>
      <ObjectItems schema={schema} onSuccess={handleSuccess} preventLinks />

      <ModalSuccess
        open={open}
        title="Your API key"
        setOpen={setOpen}
        onConfirm={() => setOpen(false)}
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
          <TokenInput value={result?.object?.token?.value} />
        </div>
      </ModalSuccess>
    </>
  );
}
