import { Card } from "../../components/ui/card";
import Content from "../layout/content";
import IpamRouter from "./ipam-router";
import IpamTree from "./ipam-tree";

export default function IpamPage() {
  return (
    <>
      <Content.Title title="IP Address Manager" />
      <Content>
        <div className="p-2 flex flex-wrap gap-2 items-stretch min-h-full">
          <Card>
            <IpamTree />
          </Card>

          <Card className="flex-grow">
            <IpamRouter />
          </Card>
        </div>
      </Content>
    </>
  );
}
