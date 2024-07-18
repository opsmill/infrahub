import { Card } from "@/components/ui/card";
import Content from "@/screens/layout/content";
import { ACCOUNT_TOKEN_OBJECT } from "@/config/constants";
import { useAtomValue } from "jotai";
import { schemaState } from "@/state/atoms/schema.atom";
import ObjectItems from "../object-items/object-items-paginated";
import LoadingScreen from "../loading-screen/loading-screen";
import ModalConfirm from "@/components/modals/modal-confirm";
import { useState } from "react";
import { TokenInput } from "@/components/ui/token-input";

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
      <Content className="p-2">
        <Card className="m-auto w-full">
          <h3 className="leading-6 font-semibold mb-4">Tokens</h3>
          <ObjectItems schema={schema} onSuccess={handleSuccess} preventLinks />
        </Card>
      </Content>

      <ModalConfirm
        open={open}
        hideCancel
        title="Token created succesfuly"
        setOpen={setOpen}
        onConfirm={() => setOpen(false)}
        onCancel={() => setOpen(false)}
        description={"Token created succesfuly, you can copy it now"}>
        <div className="mt-2">
          <TokenInput value={result?.object?.token?.value} />
        </div>
      </ModalConfirm>
    </>
  );
}
