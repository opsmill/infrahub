import { BrancheItemDetails } from "../screens/branches/branche-item-details";
import { BranchesItems } from "../screens/branches/branches-items";
import ObjectItemDetailsPaginated from "../screens/object-item-details/object-item-details-paginated";
import ObjectItemsPaginated from "../screens/object-items/object-items-paginated";
import OpsObjects from "../screens/ops-objects/ops-objects";
import UserProfile from "../screens/user-profile/user-profile";

export const MAIN_ROUTES = [
  {
    path: "/profile",
    element: <UserProfile />,
  },
  {
    path: "/objects/:objectname/:objectid",
    element: <ObjectItemDetailsPaginated />,
  },
  {
    path: "/objects/:objectname",
    element: <ObjectItemsPaginated />,
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
];

export const ADMIN_MENU_ITEMS = [
  {
    path: "/schema",
    label: "Schema",
  },
  {
    path: "/objects/Group",
    label: "Groups",
  },
];

export const BRANCHES_MENU_ITEMS = [
  {
    path: "/branches",
    label: "List",
  },
];

export const DEFAULT_BRANCH_NAME = "main";

export const ACCESS_TOKEN_KEY = "access_token";

export const REFRESH_TOKEN_KEY = "refresh_token";

export const ACCOUNT_OBJECT = "Account";

export const ACCOUNT_TOKEN_OBJECT = "AccountToken";

export const WRITE_ROLES = ["admin", "read-write"];
