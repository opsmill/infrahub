import { Card } from "../../components/ui/card";
import Content from "../layout/content";
import IpamRouter from "./ipam-router";
import IpamTree from "./ipam-tree";
import { useMemo } from "react";
import { useAtomValue } from "jotai/index";
import { currentSchemaHashAtom, genericsState } from "../../state/atoms/schema.atom";
import { IP_PREFIX_DEFAULT_SCHEMA_KIND } from "./constants";

export default function IpamPage() {
  const generics = useAtomValue(genericsState);
  const currentSchemaHash = useAtomValue(currentSchemaHashAtom);

  const prefixSchema = useMemo(
    () => generics.find(({ kind }) => kind === IP_PREFIX_DEFAULT_SCHEMA_KIND),
    [currentSchemaHash]
  );

  return (
    <>
      <Content.Title title="IP Address Manager" />

      <Content className="flex p-2 gap-2">
        <Card className="overflow-auto">
          <IpamTree prefixSchema={prefixSchema} />
        </Card>

        <Card className="flex-grow p-0 overflow-hidden">
          <IpamRouter />
        </Card>
      </Content>
    </>
  );
}
