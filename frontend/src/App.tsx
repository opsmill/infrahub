import { addCollection } from "@iconify-icon/react";
import mdiIcons from "@iconify-json/mdi/icons.json";
import loadable from "@loadable/component";
import { Navigate, Route, Routes } from "react-router-dom";

import { ARTIFACT_OBJECT } from "./config/constants";
import { AuthProvider, RequireAuth } from "./hooks/useAuth";

import "react-toastify/dist/ReactToastify.css";

addCollection(mdiIcons);

const Layout = loadable(() => import("./screens/layout/layout"));
const SchemaPage = loadable(() => import("./screens/schema/schema-page"));
const GraphiQLPage = loadable(() => import("./screens/graphql/graphiql"));
const RedirectToGraphiQLPage = loadable(() => import("./screens/graphql/RedirectToGraphiQLPage"));
const ArtifactsObjectItemDetailsPaginated = loadable(
  () => import("./screens/artifacts/object-item-details-paginated")
);
const BranchItemDetails = loadable(() => import("./screens/branches/branch-item-details"));
const BranchesItems = loadable(() => import("./screens/branches/branches-items"));
const TaskItemsScreen = loadable(() => import("./screens/tasks/task-items-screen"));
const TaskItemDetailsScreen = loadable(() => import("./screens/tasks/task-item-details-screen"));
const ProposedChanges = loadable(() => import("./screens/proposed-changes/proposed-changes-items"));
const ProposedChangesDetails = loadable(
  () => import("./screens/proposed-changes/proposed-changes-details")
);
const ProposedChangesCreatePage = loadable(
  () => import("./screens/proposed-changes/proposed-changes-create-page")
);
const UserProfile = loadable(() => import("./screens/user-profile/user-profile"));
const ObjectItemsPaginated = loadable(
  () => import("./screens/object-items/object-items-paginated")
);
const ObjectItemDetailsPaginated = loadable(
  () => import("./screens/object-item-details/object-item-details-paginated")
);
const Homepage = loadable(() => import("./screens/homepage"));
const SignIn = loadable(() => import("./screens/sign-in/sign-in"));
const IpamPage = loadable(() => import("./screens/ipam/ipam-page"));

const App = () => {
  return (
    <AuthProvider>
      <Routes>
        <Route
          path="/"
          element={
            <RequireAuth>
              <Layout />
            </RequireAuth>
          }>
          <Route path="/branches/:branchname" element={<BranchItemDetails />} />
          <Route path="/branches" element={<BranchesItems />} />
          <Route
            path={`/objects/${ARTIFACT_OBJECT}/:objectid`}
            element={<ArtifactsObjectItemDetailsPaginated />}
          />
          <Route path="/objects/:objectname/:objectid" element={<ObjectItemDetailsPaginated />} />
          <Route path="/objects/:objectname" element={<ObjectItemsPaginated />} />
          <Route path="/profile" element={<UserProfile />} />
          <Route path="/proposed-changes/new" element={<ProposedChangesCreatePage />} />
          <Route path="/proposed-changes/:proposedchange" element={<ProposedChangesDetails />} />
          <Route path="/proposed-changes" element={<ProposedChanges />} />
          <Route path="/tasks/:task" element={<TaskItemDetailsScreen />} />
          <Route path="/tasks" element={<TaskItemsScreen />} />
          <Route path="/graphql/:branch" element={<RedirectToGraphiQLPage />} />
          <Route path="/graphql" element={<GraphiQLPage />} />
          <Route path="/schema" element={<SchemaPage />} />
          <Route path="/ipam/*" element={<IpamPage />} />
          <Route path="/" element={<Homepage />} />
          <Route path="*" element={<Navigate to="/" />} />
        </Route>
        <Route path="/signin" element={<SignIn />} />
      </Routes>
    </AuthProvider>
  );
};

export default App;
