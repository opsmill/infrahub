import { Icon } from "@iconify-icon/react";
import { NavLink, useParams } from "react-router-dom";
import useFilters from "../../../hooks/useFilters";
import { classNames } from "../../../utils/common";
import { constructPath } from "../../../utils/fetch";

interface Props {
  path: string;
  title: string | undefined;
  icon?: string;
}

const getActiveStatus = (isActive: boolean, path: string, params?: any) => {
  if (!isActive) {
    return false;
  }

  if (window.location.pathname.includes("/groups")) {
    if (path === "/groups") {
      // Do not be active if it's the /groups menu item,
      // and we are displaying /groups/kind
      return !params.groupname;
    }
  }

  return true;
};

export const DropDownMenuItem = (props: Props) => {
  const { path, icon } = props;

  const params = useParams();
  const [, setFilters] = useFilters();
  const onClickMenuItem = () => setFilters();

  return (
    <NavLink to={constructPath(path)} onClick={onClickMenuItem}>
      {({ isActive }) => {
        const isItemActive = getActiveStatus(isActive, path, params);

        return (
          <div
            className={classNames(
              "p-2 m-1 group flex w-full items-center rounded-md text-sm font-medium text-gray-600",
              isItemActive ? "bg-gray-300" : "hover:bg-gray-100 hover:text-gray-900"
            )}>
            {icon && (
              <Icon icon={icon} className="mr-1 text-custom-blue-500 group-hover:text-gray-500" />
            )}

            {props.title}
          </div>
        );
      }}
    </NavLink>
  );
};
