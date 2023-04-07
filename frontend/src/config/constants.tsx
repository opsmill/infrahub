import { BrancheItemDetails } from "../screens/branches/branche-item-details";
import { BranchesItems } from "../screens/branches/branches-items";
import ObjectItemCreate from "../screens/object-item-create/object-item-create";
import ObjectItemDetails from "../screens/object-item-details/object-item-details";
import ObjectItemEdit from "../screens/object-item-edit/object-item-edit";
import ObjectItems from "../screens/object-items/object-items";
import OpsObjects from "../screens/ops-objects/ops-objects";

export const MAIN_ROUTES = [
  {
    path: "/objects/:objectname/:objectid/edit",
    element: <ObjectItemEdit />,
  },
  {
    path: "/objects/:objectname/new",
    element: <ObjectItemCreate />,
  },
  {
    path: "/objects/:objectname/:objectid",
    element: <ObjectItemDetails />,
  },
  {
    path: "/objects/:objectname",
    element: <ObjectItems />,
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
    path: "/branches/:branchid",
    element: <BrancheItemDetails />,
  },
];

export const ADMIN_MENU_ITEMS = [
  {
    path: "/schema",
    label: "Schema"
  }
];

export const BRANCHES_MENU_ITEMS = [
  {
    path: "/branches",
    label: "List"
  }
];