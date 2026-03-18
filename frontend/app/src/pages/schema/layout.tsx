import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { Outlet } from "react-router";

import { genericSchemasAtom, nodeSchemasAtom, profileSchemasAtom } from "@/entities/schema/stores/schema.atom";
import { LinkToggleButton, LinkToggleButtonGroup } from "@/shared/components/buttons/link-toggle-button";
import Content from "@/shared/components/layout/content";
import { useTitle } from "@/shared/hooks/useTitle";

function SchemaLayout() {
  useTitle("Schema");
  const nodes = useAtomValue(nodeSchemasAtom);
  const generics = useAtomValue(genericSchemasAtom);
  const profiles = useAtomValue(profileSchemasAtom);

  return (
    <Content.Card className="flex h-[calc(100%-1rem)] flex-col">
      <Content.CardTitle
        title="Schema"
        badgeContent={nodes.length + generics.length + profiles.length}
        className="w-full"
        end={
          <LinkToggleButtonGroup>
            <LinkToggleButton to="/schema">
              <Icon icon="mdi:format-list-bulleted" />
              List
            </LinkToggleButton>
            <LinkToggleButton to="/schema/graph">
              <Icon icon="mdi:graph" />
              Graph
            </LinkToggleButton>
          </LinkToggleButtonGroup>
        }
      />

      <Outlet />
    </Content.Card>
  );
}

export function Component() {
  return <SchemaLayout />;
}
