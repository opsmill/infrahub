import { Avatar } from "@/components/display/avatar";
import { Tabs } from "@/components/tabs";
import { ACCOUNT_GENERIC_OBJECT } from "@/config/constants";
import { QSP } from "@/config/qsp";
import { getProfileDetails } from "@/graphql/queries/accounts/getProfileDetails";
import { useTitle } from "@/hooks/useTitle";
import ErrorScreen from "@/screens/errors/error-screen";
import Content from "@/screens/layout/content";
import LoadingScreen from "@/screens/loading-screen/loading-screen";
import { genericsState } from "@/state/atoms/schema.atom";
import { gql, useQuery } from "@apollo/client";
import { useAtomValue } from "jotai";
import { StringParam, useQueryParam } from "use-query-params";
import NoDataFound from "../errors/no-data-found";
import TabProfile from "./tab-profile";
import TabTokens from "./tab-tokens";
import TabUpdatePassword from "./tab-update-password";

const PROFILE_TABS = {
  PROFILE: "profile",
  TOKENS: "tokens",
  PASSWORD: "password",
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
    label: "Password",
    name: PROFILE_TABS.PASSWORD,
  },
];

const renderContent = (tab: string | null | undefined) => {
  switch (tab) {
    case PROFILE_TABS.PASSWORD:
      return <TabUpdatePassword />;
    case PROFILE_TABS.TOKENS:
      return <TabTokens />;
    default:
      return <TabProfile />;
  }
};

export function UserProfilePage() {
  const [qspTab] = useQueryParam(QSP.TAB, StringParam);
  const schemaList = useAtomValue(genericsState);
  useTitle("Profile");

  const schema = schemaList.find((s) => s.kind === ACCOUNT_GENERIC_OBJECT);

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
  const { loading, data, error } = useQuery(query, {
    skip: !schema,
  });

  const profile = data?.AccountProfile;

  if (error) {
    return <ErrorScreen />;
  }

  if (loading || !schema) {
    return <LoadingScreen />;
  }

  if (!profile) {
    return <NoDataFound message="No profile found" />;
  }

  return (
    <Content.Card>
      <Content.CardTitle
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

      <Tabs tabs={tabs} />

      {renderContent(qspTab)}
    </Content.Card>
  );
}
