import { NavLink } from "react-router-dom";
import useFilters from "../../hooks/useFilters";
import { classNames } from "../../utils/common";

interface Props {
  path: string;
  title: string | undefined;
}

export const DropDownMenuItem = (props: Props) => {
  const [, setFilters] = useFilters();
  const onClickMenuItem = () => setFilters();

  return (
    <NavLink to={props.path} onClick={onClickMenuItem}>
      {({ isActive }) => {
        return (
          <div
            className={classNames(
              "p-1 mb-1 group flex w-full items-center rounded-md text-sm font-medium text-gray-600",
              isActive ? "bg-gray-300" : "hover:bg-gray-50 hover:text-gray-900"
            )}>
            {props.title}
          </div>
        );
      }}
    </NavLink>
  );
};
