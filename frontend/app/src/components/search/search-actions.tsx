import { SearchAnywhereGroup } from "@/components/search/search-anywhere-group";
import { SearchAnywhereItem } from "@/components/search/search-anywhere-item";
import { Badge } from "@/components/ui/badge";
import { MenuItem } from "@/screens/layout/menu-navigation/types";
import { IModelSchema, genericsState, menuFlatAtom, schemaState } from "@/state/atoms/schema.atom";
import { constructPath } from "@/utils/fetch";
import { Icon } from "@iconify-icon/react";
import { useCommandState } from "cmdk";
import { useAtomValue } from "jotai";

export const SearchActions = () => {
  const query = useCommandState((state) => state.search);
  const nodes = useAtomValue(schemaState);
  const generics = useAtomValue(genericsState);
  const models: IModelSchema[] = [...nodes, ...generics];

  const menuItems = useAtomValue(menuFlatAtom);

  if (query === "") return null;

  const queryLowerCased = query.toLowerCase();
  const resultsMenu = menuItems.filter(({ label }) =>
    label.toLowerCase().includes(queryLowerCased)
  );
  const resultsSchema = models.filter(
    ({ kind, label, description }) =>
      kind?.toLowerCase().includes(queryLowerCased) ||
      label?.toLowerCase().includes(queryLowerCased) ||
      description?.toLowerCase().includes(queryLowerCased)
  );

  const results = [...resultsMenu, ...resultsSchema];
  if (results.length === 0) return null;

  const firstThreeMatches = results.slice(0, 3);
  return (
    <SearchAnywhereGroup heading="Go to">
      {firstThreeMatches.map((result) => {
        return "namespace" in result ? (
          <ActionOnSchema key={result.id} model={result} />
        ) : (
          <ActionOnMenu key={result.identifier} menuItem={result} />
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

  return (
    <SearchAnywhereItem to={url} value={menuItem.identifier}>
      <span className="font-medium">Menu</span>
      <Icon icon="mdi:chevron-right" />
      <span className="font-semibold">{menuItem.label}</span>
    </SearchAnywhereItem>
  );
};

const ActionOnSchema = ({ model }: { model: IModelSchema }) => {
  const { kind, label, name } = model;
  const url = constructPath("/schema", [{ name: "kind", value: kind }]);

  return (
    <SearchAnywhereItem to={url} value={model.id!}>
      <span className="font-medium">Schema</span>
      <Icon icon="mdi:chevron-right" />
      <span className="font-semibold">
        <Badge variant="blue" className="text-xxs mr-1 py-0">
          {model.namespace}
        </Badge>
        {label || name || kind}
      </span>
    </SearchAnywhereItem>
  );
};
