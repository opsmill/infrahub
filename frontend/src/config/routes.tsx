import ArtifactsObjectItemDetailsPaginated from "../screens/artifacts/object-item-details-paginated";
import { BrancheItemDetails } from "../screens/branches/branche-item-details";
import { BranchesItems } from "../screens/branches/branches-items";
import GroupItemDetails from "../screens/groups/group-details";
import GroupItems from "../screens/groups/group-items";
import ObjectItemDetailsPaginated from "../screens/object-item-details/object-item-details-paginated";
import ObjectItemsPaginated from "../screens/object-items/object-items-paginated";
import OpsObjects from "../screens/ops-objects/ops-objects";
import { ProposedChangesDetails } from "../screens/proposed-changes/proposed-changes-details";
import { ProposedChanges } from "../screens/proposed-changes/proposed-changes-items";
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
    path: "/objects/Artifact/:objectid",
    element: <ArtifactsObjectItemDetailsPaginated />,
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
    path: "/proposed-changes",
    element: <ProposedChanges />,
  },
  {
    path: "/proposed-changes/:proposedchange",
    element: <ProposedChangesDetails />,
  },
  {
    path: "/branches/:branchname",
    element: <BrancheItemDetails />,
  },
  {
    path: "/groups",
    element: <GroupItems />,
  },
  {
    path: "/groups/:groupname/:groupid",
    element: <GroupItemDetails />,
  },
];
