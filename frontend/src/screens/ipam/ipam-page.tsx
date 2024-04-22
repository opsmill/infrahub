import { useAtomValue } from "jotai";
import { useMemo } from "react";
import { Outlet } from "react-router-dom";

import { Card } from "../../components/ui/card";
import { currentSchemaHashAtom, genericsState } from "../../state/atoms/schema.atom";
import Content from "../layout/content";
import { IP_PREFIX_DEFAULT_SCHEMA_KIND } from "./constants";
import IpamTree from "./ipam-tree/ipam-tree";

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

        <section className="flex-grow">
          <Outlet />
        </section>
      </Content>
    </>
  );
}
