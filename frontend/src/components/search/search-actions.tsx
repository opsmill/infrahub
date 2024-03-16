import { useMemo } from "react";
import { useAtomValue } from "jotai";
import { menuAtom } from "../../state/atoms/schema.atom";
import { SearchGroup, SearchGroupTitle, SearchResultItem } from "./search-modal";
import { MenuItem } from "../../screens/layout/sidebar/desktop-menu";
import { constructPath } from "../../utils/fetch";
import { Icon } from "@iconify-icon/react";

type SearchProps = {
  query: string;
};
export const SearchActions = ({ query }: SearchProps) => {
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

  const results = menuItems.filter(({ title }) =>
    title.toLowerCase().includes(query.toLowerCase())
  );

  if (results.length === 0) return null;

  const firstThreeMatches = results.slice(0, 3);
  return (
    <SearchGroup>
      <SearchGroupTitle>Go to</SearchGroupTitle>

      {firstThreeMatches.map((menuItem) => (
        <ActionOnMenu key={menuItem.path} menuItem={menuItem} />
      ))}
    </SearchGroup>
  );
};

type ActionOnMenuProps = {
  menuItem: MenuItem;
};

const ActionOnMenu = ({ menuItem }: ActionOnMenuProps) => {
  return (
    <SearchResultItem to={constructPath(menuItem.path)}>
      <span className="font-medium">{menuItem.title}</span>
      <Icon icon="mdi:chevron-right" />
      <span className="font-semibold text-custom-blue-700">View</span>
    </SearchResultItem>
  );
};
