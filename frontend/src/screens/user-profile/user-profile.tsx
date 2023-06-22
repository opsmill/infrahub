import { gql, useReactiveVar } from "@apollo/client";
import { PencilIcon, Square3Stack3DIcon } from "@heroicons/react/24/outline";
import { useAtom } from "jotai";
import { useContext, useState } from "react";
import { StringParam, useQueryParam } from "use-query-params";
import { Avatar } from "../../components/avatar";
import { Button } from "../../components/button";
import SlideOver from "../../components/slide-over";
import { Tabs } from "../../components/tabs";
import { ACCESS_TOKEN_KEY, ACCOUNT_OBJECT, DEFAULT_BRANCH_NAME } from "../../config/constants";
import { QSP } from "../../config/qsp";
import { AuthContext } from "../../decorators/withAuth";
import { getProfileDetails } from "../../graphql/queries/profile/getProfileDetails";
import { branchVar } from "../../graphql/variables/branchVar";
import useQuery from "../../hooks/useQuery";
import { schemaState } from "../../state/atoms/schema.atom";
import { parseJwt } from "../../utils/common";
import { getSchemaRelationshipColumns } from "../../utils/getSchemaObjectColumns";
import LoadingScreen from "../loading-screen/loading-screen";
import ObjectItemEditComponent from "../object-item-edit/object-item-edit-paginated";
import TabPassword from "./tab-account";
import TabPreferences from "./tab-preferences";
import TabProfile from "./tab-profile";
import TabTokens from "./tab-tokens";

const PROFILE_TABS = {
  PREFERENCES: "preferences",
  PROFILE: "profile",
  TOKENS: "tokens",
  ACCOUNT: "account",
};

const tabs = [
  {
    label: "Profile",
    name: PROFILE_TABS.PROFILE,
  },
  // {
  //   label: "Preferences",
  //   name: PROFILE_TABS.PREFERENCES,
  // },
  {
    label: "API Tokens",
    name: PROFILE_TABS.TOKENS,
  },
  // {
  //   label: "Account",
  //   name: PROFILE_TABS.ACCOUNT,
  // },
];

const renderContent = (tab: string | null | undefined, user?: any) => {
  switch (tab) {
    case PROFILE_TABS.TOKENS:
      return <TabTokens />;
    case PROFILE_TABS.ACCOUNT:
      return <TabPassword />;
    case PROFILE_TABS.PREFERENCES:
      return <TabPreferences />;
    default:
      return <TabProfile user={user} />;
  }
};

export default function UserProfile() {
  const [qspTab] = useQueryParam(QSP.TAB, StringParam);
  const auth = useContext(AuthContext);

  const [schemaList] = useAtom(schemaState);
  const [showEditDrawer, setShowEditDrawer] = useState(false);
  const branch = useReactiveVar(branchVar);

  const schema = schemaList.find((s) => s.name === ACCOUNT_OBJECT);

  const relationships = getSchemaRelationshipColumns(schema);

  const localToken = sessionStorage.getItem(ACCESS_TOKEN_KEY);

  const tokenData = parseJwt(localToken);

  const accountId = tokenData?.sub;

  const queryString = schema
    ? getProfileDetails({
        ...schema,
        relationships,
        objectid: accountId,
      })
    : // Empty query to make the gql parsing work
      // TODO: Find another solution for queries while loading schema
      "query { ok }";

  const query = gql`
    ${queryString}
  `;

  // TODO: Find a way to avoid querying object details if we are on a tab
  const { loading, data, refetch } = useQuery(query, { skip: !schema || !accountId });

  if (loading || !schema) {
    return <LoadingScreen />;
  }

  if (!auth?.permissions?.write) {
    return <div>Anonymous access</div>;
  }

  const objectDetailsData = data[schema.name]?.edges[0]?.node;

  return (
    <div className="flex flex-col flex-1 overflow-auto">
      <div className="border-b border-gray-200 bg-white px-4 py-5 sm:px-6">
        <div className="-ml-4 -mt-4 flex flex-wrap items-center justify-between sm:flex-nowrap">
          <div className="ml-4 mt-4">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <Avatar
                  name={objectDetailsData?.name?.value}
                  // image="https://shotkit.com/wp-content/uploads/2020/07/headshots_image002.jpg"
                />
              </div>

              <div className="ml-4">
                <h3 className="text-base font-semibold leading-6 text-gray-900">
                  {objectDetailsData?.display_label}
                </h3>

                <p className="text-sm text-gray-500">
                  {objectDetailsData?.description?.value ?? "-"}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="sticky top-0 z-10 shadow-sm">
        <Tabs
          tabs={tabs}
          rightItems={
            <Button
              disabled={!auth?.permissions?.write}
              onClick={() => setShowEditDrawer(true)}
              className="mr-4">
              Edit
              <PencilIcon className="-mr-0.5 h-4 w-4" aria-hidden="true" />
            </Button>
          }
        />
      </div>

      {renderContent(qspTab, objectDetailsData)}

      <SlideOver
        title={
          <div className="space-y-2">
            <div className="flex items-center w-full">
              <span className="text-lg font-semibold mr-3">{objectDetailsData.display_label}</span>
              <div className="flex-1"></div>
              <div className="flex items-center">
                <Square3Stack3DIcon className="w-5 h-5" />
                <div className="ml-1.5 pb-1">{branch?.name ?? DEFAULT_BRANCH_NAME}</div>
              </div>
            </div>
            <span className="inline-flex items-center rounded-md bg-yellow-50 px-2 py-1 text-xs font-medium text-yellow-800 ring-1 ring-inset ring-yellow-600/20">
              <svg
                className="h-1.5 w-1.5 mr-1 fill-yellow-500"
                viewBox="0 0 6 6"
                aria-hidden="true">
                <circle cx={3} cy={3} r={3} />
              </svg>
              {schema.kind}
            </span>
            <div className="inline-flex items-center rounded-md bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700 ring-1 ring-inset ring-blue-700/10 ml-3">
              <svg className="h-1.5 w-1.5 mr-1 fill-blue-500" viewBox="0 0 6 6" aria-hidden="true">
                <circle cx={3} cy={3} r={3} />
              </svg>
              ID: {objectDetailsData.id}
            </div>
          </div>
        }
        open={showEditDrawer}
        setOpen={setShowEditDrawer}>
        <ObjectItemEditComponent
          closeDrawer={() => setShowEditDrawer(false)}
          onUpdateComplete={() => refetch()}
          objectid={accountId}
          objectname={ACCOUNT_OBJECT!}
        />
      </SlideOver>
    </div>
  );
}
