import { Card } from "../../components/ui/card";
import Content from "../layout/content";
import IpamRouter from "./ipam-router";
import IpamTree from "./ipam-tree";
import { useMemo } from "react";
import { useAtomValue } from "jotai/index";
import { genericsState } from "../../state/atoms/schema.atom";
import LoadingScreen from "../loading-screen/loading-screen";
import { IP_PREFIX_SCHEMA_KIND } from "./constants";

export default function IpamPage() {
  const generics = useAtomValue(genericsState);

  const prefixSchema = useMemo(
    () => generics.find(({ kind }) => kind === IP_PREFIX_SCHEMA_KIND),
    [generics.length]
  );

  // wait for schema to be loaded before displaying IPAM
  if (!prefixSchema) return <LoadingScreen />;

  return (
    <>
      <Content.Title title="IP Address Manager" />
      <Content>
        <div className="p-2 flex flex-wrap gap-2 items-stretch min-h-full">
          <Card>
            <IpamTree />
          </Card>

          <Card className="flex-grow p-0 overflow-hidden">
            <IpamRouter />
          </Card>
        </div>
      </Content>
    </>
  );
}
