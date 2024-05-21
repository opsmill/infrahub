import { addCollection } from "@iconify-icon/react";
import mdiIcons from "@iconify-json/mdi/icons.json";
import loadable from "@loadable/component";
import { Navigate, Route, Routes } from "react-router-dom";

import { ARTIFACT_OBJECT } from "./config/constants";
import { AuthProvider, RequireAuth } from "./hooks/useAuth";

import "react-toastify/dist/ReactToastify.css";
import { IPAM_ROUTE } from "./screens/ipam/constants";

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
const ResourceManager = loadable(() => import("./screens/resource-manager/resource-manager-page"));
const ResourcePool = loadable(() => import("./screens/resource-manager/resource-pool-page"));
const ResourceAllocationDetails = loadable(
  () => import("./screens/resource-manager/resource-allocation-details")
);
const SignIn = loadable(() => import("./screens/sign-in/sign-in"));
const IpamPage = loadable(() => import("./screens/ipam/ipam-page"));
const IpamRouter = loadable(() => import("./screens/ipam/ipam-router"));

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
          <Route path="/resource-manager" element={<ResourceManager />} />
          <Route path="/resource-manager/:resourcePoolId" element={<ResourcePool />}>
            <Route
              path="/resource-manager/:resourcePoolId/resources/:resourceId"
              element={<ResourceAllocationDetails />}
            />
          </Route>
          <Route path="/schema" element={<SchemaPage />} />
          <Route path={IPAM_ROUTE.INDEX} element={<IpamPage />}>
            <Route path={`${IPAM_ROUTE.ADDRESSES}/:ip_address`} element={<IpamRouter />} />
            <Route path={IPAM_ROUTE.ADDRESSES} element={<IpamRouter />} />
            <Route path={`${IPAM_ROUTE.PREFIXES}/:prefix/:ip_address`} element={<IpamRouter />} />
            <Route path={`${IPAM_ROUTE.PREFIXES}/:prefix`} element={<IpamRouter />} />
            <Route path={`${IPAM_ROUTE.INDEX}/*`} index element={<IpamRouter />} />
          </Route>
          <Route path="/" element={<Homepage />} />
          <Route path="*" element={<Navigate to="/" />} />
        </Route>
        <Route path="/signin" element={<SignIn />} />
      </Routes>
    </AuthProvider>
  );
};

export default App;
