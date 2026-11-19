import { Outlet } from "react-router";

import Content from "@/shared/components/layout/content";
import { useTitle } from "@/shared/hooks/useTitle";

import { RackElevationStoreProvider } from "@/entities/rack-elevation/ui/rack-elevation-store";

export function Component() {
  useTitle("Rack elevation");

  return (
    <RackElevationStoreProvider>
      <Content.Card className="grow overflow-hidden">
        <Outlet />
      </Content.Card>
    </RackElevationStoreProvider>
  );
}
