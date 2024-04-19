import { useMemo } from "react";
import { Outlet } from "react-router-dom";
import { useAtomValue } from "jotai";

import { Card } from "../../components/ui/card";
import Content from "../layout/content";
import IpamTree from "./ipam-tree";
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

        <section className="flex-grow">
          <Outlet />
        </section>
      </Content>
    </>
  );
}
