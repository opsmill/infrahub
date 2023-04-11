import { NavLink } from "react-router-dom";
import { classNames } from "../../utils/common";

interface Props {
  key: Number,
  path: string,
  label: string | undefined,
  onClick: Function
}

export const DropDownMenuItem = (props: Props) =>  (
  <NavLink
    to={props.path}
    onClick={() => props.onClick()}
  >
    {({ isActive }) => {
      return (
        <div
          className={classNames(
            "group flex w-full items-center rounded-md py-2 pl-11 pr-2 text-sm font-medium text-gray-600",
            isActive
              ? "bg-gray-300"
              : "hover:bg-gray-50 hover:text-gray-900"
          )}
        >
          {props.label}
        </div>
      );}
    }
  </NavLink>
);