import ArtifactsObjectItemDetailsPaginated from "../screens/artifacts/object-item-details-paginated";
import { BrancheItemDetails } from "../screens/branches/branche-item-details";
import { BranchesItems } from "../screens/branches/branches-items";
import ObjectItemDetailsPaginated from "../screens/object-item-details/object-item-details-paginated";
import ObjectItemsPaginated from "../screens/object-items/object-items-paginated";
import OpsObjects from "../screens/ops-objects/ops-objects";
import { ProposedChangesDetails } from "../screens/proposed-changes/proposed-changes-details";
import { ProposedChanges } from "../screens/proposed-changes/proposed-changes-items";
import UserProfile from "../screens/user-profile/user-profile";
import { ARTIFACT_OBJECT } from "./constants";

export const MAIN_ROUTES = [
  {
    path: "/branches/:branchname",
    element: <BrancheItemDetails />,
  },
  {
    path: "/branches",
    element: <BranchesItems />,
  },
  // {
  //   path: "/groups/:groupname/:groupid",
  //   element: <GroupItemDetails />,
  // },
  // {
  //   path: "/groups/:groupname",
  //   element: <GroupItems />,
  // },
  // {
  //   path: "/groups",
  //   element: <GroupItems />,
  // },
  {
    path: `/objects/${ARTIFACT_OBJECT}/:objectid`,
    element: <ArtifactsObjectItemDetailsPaginated />,
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
    path: "/profile",
    element: <UserProfile />,
  },
  {
    path: "/proposed-changes/:proposedchange",
    element: <ProposedChangesDetails />,
  },
  {
    path: "/proposed-changes",
    element: <ProposedChanges />,
  },
  {
    path: "/schema",
    element: <OpsObjects />,
  },
];
