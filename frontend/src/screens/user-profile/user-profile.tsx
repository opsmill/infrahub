import { gql } from "@apollo/client";
import { Cog6ToothIcon } from "@heroicons/react/24/outline";
import { useAtom } from "jotai";
import { StringParam, useQueryParam } from "use-query-params";
import { Avatar } from "../../components/avatar";
import { Tabs } from "../../components/tabs";
import { ACCESS_TOKEN_KEY } from "../../config/constants";
import { QSP } from "../../config/qsp";
import { getProfileDetails } from "../../graphql/queries/profile/getProfileDetails";
import useQuery from "../../hooks/useQuery";
import { configState } from "../../state/atoms/config.atom";
import { schemaState } from "../../state/atoms/schema.atom";
import { parseJwt } from "../../utils/common";
import { getSchemaRelationshipColumns } from "../../utils/getSchemaObjectColumns";
import LoadingScreen from "../loading-screen/loading-screen";
import TabPassword from "./tab-account";
import TabPreferences from "./tab-preferences";
import TabProfile from "./tab-profile";
import TabTokens from "./tab-tokens";

const ACCOUNT_OBJECT = "account";

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
  {
    label: "Preferences",
    name: PROFILE_TABS.PREFERENCES,
  },
  {
    label: "API Tokens",
    name: PROFILE_TABS.TOKENS,
  },
  {
    label: "Account",
    name: PROFILE_TABS.ACCOUNT,
  },
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
  const [config] = useAtom(configState);
  const [schemaList] = useAtom(schemaState);

  const schema = schemaList.find((s) => s.name === ACCOUNT_OBJECT);

  const relationships = getSchemaRelationshipColumns(schema);

  const localToken = sessionStorage.getItem(ACCESS_TOKEN_KEY);

  const tokenData = parseJwt(localToken);

  const queryString = schema
    ? getProfileDetails({
        ...schema,
        relationships,
        objectid: tokenData?.sub,
      })
    : // Empty query to make the gql parsing work
      // TODO: Find another solution for queries while loading schema
      "query { ok }";

  const query = gql`
    ${queryString}
  `;

  // TODO: Find a way to avoid querying object details if we are on a tab
  const { loading, data } = useQuery(query, { skip: !schema });

  if (loading || !schema) {
    return <LoadingScreen />;
  }

  if (config?.main?.allow_anonymous_access) {
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

          <div className="ml-4 mt-4 flex flex-shrink-0">
            <Cog6ToothIcon className="w-6 h-6 text-gray-600 cursor-pointer hover:scale-110" />
          </div>
        </div>
      </div>

      <div className="sticky top-0 z-10 shadow-sm">
        <Tabs tabs={tabs} />
      </div>

      {renderContent(qspTab, objectDetailsData)}
    </div>
  );
}
