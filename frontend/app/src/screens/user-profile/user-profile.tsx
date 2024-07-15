import { Avatar } from "@/components/display/avatar";
import { Tabs } from "@/components/tabs";
import { ACCESS_TOKEN_KEY, ACCOUNT_OBJECT } from "@/config/constants";
import { QSP } from "@/config/qsp";
import { getProfileDetails } from "@/graphql/queries/accounts/getProfileDetails";
import useQuery from "@/hooks/useQuery";
import { useTitle } from "@/hooks/useTitle";
import ErrorScreen from "@/screens/errors/error-screen";
import Content from "@/screens/layout/content";
import LoadingScreen from "@/screens/loading-screen/loading-screen";
import { schemaState } from "@/state/atoms/schema.atom";
import { parseJwt } from "@/utils/common";
import { gql } from "@apollo/client";
import { useAtomValue } from "jotai";
import { StringParam, useQueryParam } from "use-query-params";
import TabPreferences from "./tab-preferences";
import TabProfile from "./tab-profile";
import TabTokens from "./tab-tokens";

const PROFILE_TABS = {
  PROFILE: "profile",
  TOKENS: "tokens",
  PREFERENCES: "preferences",
};

const tabs = [
  {
    label: "Profile",
    name: PROFILE_TABS.PROFILE,
  },
  {
    label: "Tokens",
    name: PROFILE_TABS.TOKENS,
  },
  {
    label: "Preferences",
    name: PROFILE_TABS.PREFERENCES,
  },
];

const renderContent = (tab: string | null | undefined) => {
  switch (tab) {
    case PROFILE_TABS.PREFERENCES:
      return <TabPreferences />;
    case PROFILE_TABS.TOKENS:
      return <TabTokens />;
    default:
      return <TabProfile />;
  }
};

export function UserProfilePage() {
  const [qspTab] = useQueryParam(QSP.TAB, StringParam);
  const schemaList = useAtomValue(schemaState);
  useTitle("Profile");

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
    <Content>
      <Content.Title
        title={
          <div className="flex items-center gap-2">
            <Avatar name={profile?.name?.value} />

            <div className="ml-2">
              <h3>{profile?.display_label}</h3>

              <p className="text-sm text-gray-500">{profile?.description?.value ?? "-"}</p>
            </div>
          </div>
        }
      />

      <div className="sticky top-0 shadow-sm">
        <Tabs tabs={tabs} />
      </div>

      <div>{renderContent(qspTab)}</div>
    </Content>
  );
}
