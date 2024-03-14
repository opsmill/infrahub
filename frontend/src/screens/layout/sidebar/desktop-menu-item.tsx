import { Icon } from "@iconify-icon/react";
import { NavLink } from "react-router-dom";
import useFilters from "../../../hooks/useFilters";
import { classNames } from "../../../utils/common";
import { constructPath } from "../../../utils/fetch";

interface DropDownMenuItemProps {
  path: string;
  title?: string;
  icon?: string;
}

export const DropDownMenuItem = ({ path, icon, title }: DropDownMenuItemProps) => {
  const [, setFilters] = useFilters();
  const onClickMenuItem = () => setFilters();

  return (
    <NavLink
      to={constructPath(path)}
      onClick={onClickMenuItem}
      className={({ isActive }) =>
        classNames(
          "p-2 group flex items-center rounded text-sm font-medium text-gray-600",
          isActive ? "bg-gray-300" : "hover:bg-gray-100 hover:text-gray-900"
        )
      }>
      {icon && <Icon icon={icon} className="mr-1 text-custom-blue-500 group-hover:text-gray-500" />}

      <span className="truncate">{title}</span>
    </NavLink>
  );
};
