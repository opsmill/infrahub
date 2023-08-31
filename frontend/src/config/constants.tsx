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

export const ADMIN_MENU_ITEMS = [
  {
    path: "/schema",
    label: "Schema",
  },
  {
    path: "/groups",
    label: "Groups",
  },
];

export const BRANCHES_MENU_ITEMS = [
  {
    path: "/branches",
    label: "List",
  },
  {
    path: "/proposed-changes",
    label: "Proposed changes",
  },
];

export const DEFAULT_BRANCH_NAME = "main";

export const ACCESS_TOKEN_KEY = "access_token";

export const REFRESH_TOKEN_KEY = "refresh_token";

export const ACCOUNT_OBJECT = "Account";

export const ACCOUNT_TOKEN_OBJECT = "AccountToken";

export const PROPOSED_CHANGES_OBJECT = "ProposedChange";

export const PROPOSED_CHANGES_THREAD = "Thread";
export const PROPOSED_CHANGES_THREAD_OBJECT = "CoreThread";

export const PROPOSED_CHANGES_CHANGE_THREAD = "ChangeThread";
export const PROPOSED_CHANGES_CHANGE_THREAD_OBJECT = "CoreChangeThread";

export const PROPOSED_CHANGES_FILE_THREAD = "FileThread";
export const PROPOSED_CHANGES_FILE_THREAD_OBJECT = "CoreFileThread";

export const PROPOSED_CHANGES_OBJECT_THREAD = "ObjectThread";
export const PROPOSED_CHANGES_OBJECT_THREAD_OBJECT = "CoreObjectThread";

export const ARTIFACT_OBJECT = "Artifact";
export const PROPOSED_CHANGES_ARTIFACT_THREAD = "ArtifactThread";
export const PROPOSED_CHANGES_ARTIFACT_THREAD_OBJECT = "CoreArtifactThread";

export const PROPOSED_CHANGES_COMMENT_OBJECT = "CoreChangeComment";

export const PROPOSED_CHANGES_THREAD_COMMENT_OBJECT = "CoreThreadComment";

export const GROUP_OBJECT = "Group";

export const WRITE_ROLES = ["admin", "read-write"];

export const ADMIN_ROLES = ["admin"];

export const MENU_EXCLUDELIST = [
  "InternalAccountToken",
  "CoreChangeComment",
  "CoreChangeThread",
  "CoreFileThread",
  "CoreArtifactThread",
  "CoreObjectThread",
  "CoreProposedChange",
  "InternalRefreshToken",
  "CoreStandardGroup",
  "CoreThreadComment",
  "CoreArtifactCheck",
  "CoreStandardCheck",
  "CoreDataCheck",
  "CoreFileCheck",
  "CoreSchemaCheck",
  "CoreSchemaValidator",
  "CoreDataValidator",
  "CoreRepositoryValidator",
  "CoreArtifactValidator",
];

export const ATTRIBUTES_EXCLUDELIST = ["HashedPassword"];

export const COLUMNS_BLACKLIST = ["TextArea", "JSON"];

export const NODE_PATH_BLACKLIST = ["property"];
