import { Card } from "@/components/ui/card";
import Content from "@/screens/layout/content";
import { ACCOUNT_TOKEN_OBJECT } from "@/config/constants";
import { useAtomValue } from "jotai";
import { schemaState } from "@/state/atoms/schema.atom";
import ObjectItems from "../object-items/object-items-paginated";
import LoadingScreen from "../loading-screen/loading-screen";

export default function TabTokens() {
  const schemaList = useAtomValue(schemaState);
  const schema = schemaList.find((schema) => schema.kind === ACCOUNT_TOKEN_OBJECT);

  if (!schema) return <LoadingScreen />;

  return (
    <Content className="p-2">
      <Card className="m-auto w-full">
        <h3 className="leading-6 font-semibold mb-4">Tokens</h3>
        <ObjectItems schema={schema} />
      </Card>
    </Content>
  );
}
