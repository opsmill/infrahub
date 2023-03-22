import { useAtom } from "jotai";
import { ADMIN_MENU_ITEMS, BRANCHES_MENU_ITEMS } from "../../config/constants";
import { comboxBoxFilterState } from "../../state/atoms/filters.atom";
import { schemaState } from "../../state/atoms/schema.atom";
import DropDownMenuHeader from "./desktop-menu-header";
import { DropDownMenuItem } from "./desktop-menu-item";

import logo from "./logo.png";

export default function DesktopMenu() {
  const [schema] = useAtom(schemaState);
  const [, setCurrentFilters] = useAtom(comboxBoxFilterState);

  const onClinkMenuItem = () => setCurrentFilters([]);

  const schemaItems = schema.map(
    (item, index) => (
      <DropDownMenuItem
        key={index}
        path={`/objects/${item.name}`}
        label={item.label}
        onClick={onClinkMenuItem}
      />
    )
  );

  const adminItems = ADMIN_MENU_ITEMS.map(
    (item, index) => (
      <DropDownMenuItem
        key={index}
        path={item.path}
        label={item.label}
        onClick={onClinkMenuItem}
      />
    )
  );

  const branchesItems = BRANCHES_MENU_ITEMS.map(
    (item, index) => (
      <DropDownMenuItem
        key={index}
        path={item.path}
        label={item.label}
        onClick={onClinkMenuItem}
      />
    )
  );

  return (
    <div className="hidden md:fixed md:inset-y-0 md:flex md:w-64 md:flex-col z-20">
      <div className="flex flex-grow flex-col overflow-y-auto border-r border-gray-200 bg-white pt-5">
        <div className="flex flex-shrink-0 items-center px-4">
          <img className="h-10 w-auto" src={logo} alt="Your Company" />
        </div>
        <div className="mt-5 flex flex-grow flex-col flex-1 overflow-auto py-2">
          <nav className="flex-1 space-y-2 bg-white px-2" aria-label="Sidebar">
            <DropDownMenuHeader title={"Objects"} items={schemaItems} />
            <DropDownMenuHeader title={"Admin"} items={adminItems} />
            <DropDownMenuHeader title={"Branches"} items={branchesItems} />
          </nav>
        </div>
      </div>
    </div>
  );
}
