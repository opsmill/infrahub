import { LinkIcon, Square3Stack3DIcon, UserIcon } from "@heroicons/react/24/outline";
import { useAtom } from "jotai";
import { useNavigate } from "react-router-dom";
import { ADMIN_MENU_ITEMS, BRANCHES_MENU_ITEMS } from "../../config/constants";
import useFilters from "../../hooks/useFilters";
import logo from "../../images/Infrahub-SVG-hori.svg";
import { schemaState } from "../../state/atoms/schema.atom";
import { constructPath } from "../../utils/fetch";
import DropDownMenuHeader from "./desktop-menu-header";
import { DropDownMenuItem } from "./desktop-menu-item";

export default function DesktopMenu() {
  const [schema] = useAtom(schemaState);
  const [, setFilters] = useFilters();
  const onClickMenuItem = () => setFilters();
  const navigate = useNavigate();

  const schemaItems = schema.map((item, index) => (
    <DropDownMenuItem
      key={index}
      path={constructPath(`/objects/${item.name}`)}
      label={item.label}
      onClick={onClickMenuItem}
    />
  ));

  const adminItems = ADMIN_MENU_ITEMS.map((item, index) => (
    <DropDownMenuItem
      key={index}
      path={constructPath(item.path)}
      label={item.label}
      onClick={onClickMenuItem}
    />
  ));

  const branchesItems = BRANCHES_MENU_ITEMS.map((item, index) => (
    <DropDownMenuItem
      key={index}
      path={constructPath(item.path)}
      label={item.label}
      onClick={onClickMenuItem}
    />
  ));

  return (
    <div className="hidden md:fixed md:inset-y-0 md:flex md:w-64 md:flex-col">
      <div className="flex flex-grow flex-col overflow-y-auto border-r border-gray-200 bg-custom-white pt-5">
        <div
          className="flex flex-shrink-0 items-center px-4 cursor-pointer"
          onClick={() => navigate("/")}>
          <img src={logo} />
        </div>
        <div className="mt-5 flex flex-grow flex-col flex-1 overflow-auto py-2">
          <nav className="flex-1 space-y-2 bg-custom-white px-2" aria-label="Sidebar">
            <DropDownMenuHeader title={"Objects"} items={schemaItems} Icon={LinkIcon} />
            <DropDownMenuHeader title={"Admin"} items={adminItems} Icon={UserIcon} />
            <DropDownMenuHeader
              title={"Branches"}
              items={branchesItems}
              Icon={Square3Stack3DIcon}
            />
          </nav>
        </div>
      </div>
    </div>
  );
}
