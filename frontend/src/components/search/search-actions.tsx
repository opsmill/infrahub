import { useMemo } from "react";
import { useAtomValue } from "jotai";
import { genericsState, IModelSchema, menuAtom, schemaState } from "../../state/atoms/schema.atom";
import { SearchGroup, SearchGroupTitle, SearchResultItem } from "./search-anywhere";
import { MenuItem } from "../../screens/layout/sidebar/desktop-menu";
import { constructPath } from "../../utils/fetch";
import { Icon } from "@iconify-icon/react";
import { Badge } from "../ui/badge";

type SearchProps = {
  query: string;
};
export const SearchActions = ({ query }: SearchProps) => {
  const nodes = useAtomValue(schemaState);
  const generics = useAtomValue(genericsState);
  const models: IModelSchema[] = [...nodes, ...generics];

  const menu = useAtomValue(menuAtom);
  const menuItems = useMemo(() => {
    const flattenMenuItems = (menuItems: MenuItem[]): MenuItem[] => {
      return menuItems.reduce<MenuItem[]>((acc, menuItem) => {
        if (menuItem.children.length === 0) {
          return [...acc, menuItem];
        }

        return [...acc, ...flattenMenuItems(menuItem.children)];
      }, []);
    };

    return flattenMenuItems(menu);
  }, [menu.length]);

  const queryLowerCased = query.toLowerCase();
  const resultsMenu = menuItems.filter(({ title }) =>
    title.toLowerCase().includes(queryLowerCased)
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
    <SearchGroup>
      <SearchGroupTitle>Go to</SearchGroupTitle>

      {firstThreeMatches.map((result) => {
        return "namespace" in result ? (
          <ActionOnSchema key={result.kind} model={result} />
        ) : (
          <ActionOnMenu key={result.path} menuItem={result} />
        );
      })}
    </SearchGroup>
  );
};

type ActionOnMenuProps = {
  menuItem: MenuItem;
};

const ActionOnMenu = ({ menuItem }: ActionOnMenuProps) => {
  return (
    <SearchResultItem to={constructPath(menuItem.path)}>
      <span className="font-medium">Menu</span>
      <Icon icon="mdi:chevron-right" />
      <span className="font-semibold">{menuItem.title}</span>
    </SearchResultItem>
  );
};

const ActionOnSchema = ({ model }: { model: IModelSchema }) => {
  console.log(model);
  const { kind, label, name } = model;

  return (
    <SearchResultItem to={constructPath("/schema", [{ name: "kind", value: kind }])}>
      <span className="font-medium">Schema</span>
      <Icon icon="mdi:chevron-right" />
      <span className="font-semibold">
        <Badge variant="blue" className="text-xxs mr-1 py-0">
          {model.namespace}
        </Badge>
        {label || name || kind}
      </span>
    </SearchResultItem>
  );
};
