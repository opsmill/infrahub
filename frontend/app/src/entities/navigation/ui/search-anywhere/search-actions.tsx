import { Icon } from "@iconify-icon/react";
import { useCommandState } from "cmdk";
import { useAtomValue } from "jotai";
import { useId, useMemo } from "react";

import { constructPath } from "@/shared/api/rest/fetch";
import { Badge } from "@/shared/components/ui/badge";

import type { MenuItem } from "@/entities/navigation/types";
import { useMenu } from "@/entities/navigation/ui/queries/get-menu.query";
import { SearchAnywhereGroup } from "@/entities/navigation/ui/search-anywhere/search-anywhere-group";
import { SearchAnywhereItem } from "@/entities/navigation/ui/search-anywhere/search-anywhere-item";
import { genericSchemasAtom, nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";
import type { ModelSchema } from "@/entities/schema/types";

export const SearchActions = () => {
  const query = useCommandState((state) => state.search);
  const nodes = useAtomValue(nodeSchemasAtom);
  const generics = useAtomValue(genericSchemasAtom);
  const models: ModelSchema[] = [...nodes, ...generics];

  const { data: menuData, isPending, isError } = useMenu({ enabled: false }); // prevent fetching menu, data should be already cached

  const menuItems = useMemo(() => {
    if (!menuData) return [];

    const menuItems: MenuItem[] = [];

    const flattenMenuItems = (menuItem: MenuItem) => {
      if (menuItem.path !== "") menuItems.push(menuItem);

      if (menuItem.children && menuItem.children.length > 0) {
        menuItem.children.forEach(flattenMenuItems);
      }
    };

    menuData.sections.object.forEach(flattenMenuItems);
    menuData.sections.internal.forEach(flattenMenuItems);

    return menuItems;
  }, [menuData]);

  if (query === "") return null;

  if (isPending) {
    return (
      <SearchAnywhereGroup heading="Go to">
        <SearchAnywhereItem to="" disabled>
          Loading...
        </SearchAnywhereItem>
      </SearchAnywhereGroup>
    );
  }

  if (isError || menuItems.length === 0) return null;

  const queryLowerCased = query.toLowerCase();
  const resultsMenu = menuItems.filter(({ label }) =>
    label.toLowerCase().includes(queryLowerCased)
  );
  const resultsSchema = models.filter(({ kind, label, description }) => {
    return (
      kind?.toLowerCase().includes(queryLowerCased) ||
      label?.toLowerCase().includes(queryLowerCased) ||
      description?.toLowerCase().includes(queryLowerCased)
    );
  });

  const results = [...resultsMenu, ...resultsSchema];

  if (results.length === 0) return null;

  const firstThreeMatches = results.slice(0, 3);

  return (
    <SearchAnywhereGroup heading="Go to">
      {firstThreeMatches.map((result) => {
        return "section" in result ? (
          <ActionOnMenu key={result.identifier} menuItem={result} />
        ) : (
          <ActionOnSchema key={result.id} model={result} />
        );
      })}
    </SearchAnywhereGroup>
  );
};

type ActionOnMenuProps = {
  menuItem: MenuItem;
};

const ActionOnMenu = ({ menuItem }: ActionOnMenuProps) => {
  const url = constructPath(menuItem.path);
  const uniqueId = useId();

  return (
    <SearchAnywhereItem to={url} value={uniqueId}>
      <span className="font-medium">Menu</span>
      <Icon icon="mdi:chevron-right" />
      <span className="font-semibold">{menuItem.label}</span>
    </SearchAnywhereItem>
  );
};

const ActionOnSchema = ({ model }: { model: ModelSchema }) => {
  const { kind, label, name } = model;
  const url = constructPath("/schema", [{ name: "kind", value: kind }]);
  const uniqueId = useId();

  return (
    <SearchAnywhereItem to={url} value={uniqueId}>
      <span className="font-medium">Schema</span>
      <Icon icon="mdi:chevron-right" />
      <span className="font-semibold">
        <Badge variant="blue" className="mr-1 py-0 text-xxs">
          {model.namespace}
        </Badge>
        {label || name || kind}
      </span>
    </SearchAnywhereItem>
  );
};
