import { Card } from "@/components/ui/card";
import Content from "@/screens/layout/content";
import { schemaState } from "@/state/atoms/schema.atom";
import { useAtomValue } from "jotai";
import ObjectItems from "../object-items/object-items-paginated";

export default function TabTokens() {
  const schemaList = useAtomValue(schemaState);

  const schema = schemaList.find((schema) => schema.kind === "CoreAccountToken");

  return (
    <Content className="p-2">
      <Card className="m-auto w-full">
        <h3 className="leading-6 font-semibold mb-4">Tokens</h3>
        {schema && <ObjectItems schema={schema} />}
      </Card>
    </Content>
  );
}
