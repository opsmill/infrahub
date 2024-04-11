import Content from "../layout/content";
import IpamTree from "./ipam-tree";

export default function IpamPage() {
  return (
    <>
      <Content.Title
        title={
          <div className="flex items-center">
            <h1 className="mr-2 truncate">IP Address Manager</h1>
          </div>
        }
      />

      <Content>
        <div className="flex items-stretch min-h-full">
          <div className="m-2 p-2 bg-custom-white rounded-md">
            <IpamTree />
          </div>

          <div className="flex-1 m-2 p-2 bg-custom-white rounded-md">Table</div>
        </div>
      </Content>
    </>
  );
}
