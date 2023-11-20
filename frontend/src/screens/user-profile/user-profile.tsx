import { gql } from "@apollo/client";
import { useAtom } from "jotai";
import { StringParam, useQueryParam } from "use-query-params";
import { Avatar } from "../../components/avatar";
import { Tabs } from "../../components/tabs";
import { ACCESS_TOKEN_KEY, ACCOUNT_OBJECT } from "../../config/constants";
import { QSP } from "../../config/qsp";
import { getProfileDetails } from "../../graphql/queries/profile/getProfileDetails";
import useQuery from "../../hooks/useQuery";
import { schemaState } from "../../state/atoms/schema.atom";
import { parseJwt } from "../../utils/common";
import ErrorScreen from "../error-screen/error-screen";
import LoadingScreen from "../loading-screen/loading-screen";
import TabPassword from "./tab-account";
import TabPreferences from "./tab-preferences";
import TabProfile from "./tab-profile";
// import TabTokens from "./tab-tokens";

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
  //   label: "Tokens",
  //   name: PROFILE_TABS.TOKENS,
  // },
  {
    label: "Preferences",
    name: PROFILE_TABS.PREFERENCES,
  },
];

const renderContent = (tab: string | null | undefined) => {
  switch (tab) {
    // case PROFILE_TABS.TOKENS:
    //   return <TabTokens />;
    case PROFILE_TABS.ACCOUNT:
      return <TabPassword />;
    case PROFILE_TABS.PREFERENCES:
      return <TabPreferences />;
    default:
      return <TabProfile />;
  }
};

export default function UserProfile() {
  const [qspTab] = useQueryParam(QSP.TAB, StringParam);
  const [schemaList] = useAtom(schemaState);

  const schema = schemaList.find((s) => s.kind === ACCOUNT_OBJECT);

  const localToken = localStorage.getItem(ACCESS_TOKEN_KEY);

  const tokenData = parseJwt(localToken);

  const accountId = tokenData?.sub;

  const queryString = schema
    ? getProfileDetails({
        ...schema,
      })
    : // Empty query to make the gql parsing work
      // TODO: Find another solution for queries while loading schema
      "query { ok }";

  const query = gql`
    ${queryString}
  `;

  // TODO: Find a way to avoid querying object details if we are on a tab
  const { loading, data, error } = useQuery(query, { skip: !schema || !accountId });

  if (error) {
    return <ErrorScreen />;
  }

  if (loading || !schema) {
    return <LoadingScreen />;
  }

  const profile = data?.AccountProfile;

  return (
    <div className="flex flex-col flex-1 overflow-auto">
      <div className="border-b border-gray-200 bg-custom-white px-4 py-5 sm:px-6">
        <div className="-ml-4 -mt-4 flex flex-wrap items-center justify-between sm:flex-nowrap">
          <div className="ml-4 mt-4">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <Avatar name={profile?.name?.value} />
              </div>

              <div className="ml-4">
                <h3 className="text-base font-semibold leading-6 text-gray-900">
                  {profile?.display_label}
                </h3>

                <p className="text-sm text-gray-500">{profile?.description?.value ?? "-"}</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="sticky top-0 z-10 shadow-sm">
        <Tabs tabs={tabs} />
      </div>

      <div data-cy="user-details">{renderContent(qspTab)}</div>
    </div>
  );
}
