import { BrancheItemDetails } from "../screens/branches/branche-item-details";
import { BranchesItems } from "../screens/branches/branches-items";
import ObjectItemDetails from "../screens/object-item-details/object-item-details";
import ObjectItemDetailsPaginated from "../screens/object-item-details/object-item-details-paginated";
import ObjectItems from "../screens/object-items/object-items";
import ObjectItemsPaginated from "../screens/object-items/object-items-paginated";
import OpsObjects from "../screens/ops-objects/ops-objects";
import UserProfile from "../screens/user-profile/user-profile";
import { Config } from "../state/atoms/config.atom";

export const MAIN_ROUTES = (config?: Config) => [
  {
    path: "/objects/:objectname/:objectid",
    element: config?.experimental_features?.paginated ? (
      <ObjectItemDetailsPaginated />
    ) : (
      <ObjectItemDetails />
    ),
  },
  {
    path: "/objects/:objectname",
    element: config?.experimental_features?.paginated ? <ObjectItemsPaginated /> : <ObjectItems />,
  },
  {
    path: "/schema",
    element: <OpsObjects />,
  },
  {
    path: "/branches",
    element: <BranchesItems />,
  },
  {
    path: "/branches/:branchname",
    element: <BrancheItemDetails />,
  },
  {
    path: "/profile",
    element: <UserProfile />,
  },
];

export const ADMIN_MENU_ITEMS = [
  {
    path: "/schema",
    label: "Schema",
  },
];

export const BRANCHES_MENU_ITEMS = [
  {
    path: "/branches",
    label: "List",
  },
];

export const DEFAULT_BRANCH_NAME = "main";
