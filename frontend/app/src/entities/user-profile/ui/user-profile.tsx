import { gql, useQuery } from "@apollo/client";
import { useAtomValue } from "jotai";
import { useQueryState } from "nuqs";

import { ACCOUNT_GENERIC_OBJECT } from "@/config/constants";
import { QSP } from "@/config/qsp";

import { Avatar } from "@/shared/components/display/avatar";
import ErrorScreen from "@/shared/components/errors/error-screen";
import NoDataFound from "@/shared/components/errors/no-data-found";
import Content from "@/shared/components/layout/content";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { Tabs } from "@/shared/components/tabs";
import { useTitle } from "@/shared/hooks/useTitle";

import { genericSchemasAtom } from "@/entities/schema/stores/schema.atom";
import { getProfileDetails } from "@/entities/user-profile/api/getProfileDetails";

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
  const [qspTab] = useQueryState(QSP.TAB);
  const schemaList = useAtomValue(genericSchemasAtom);
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
    return <LoadingIndicator className="h-full" />;
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

              <p className="text-gray-500 text-sm">{profile?.description?.value ?? "-"}</p>
            </div>
          </div>
        }
      />

      <Tabs tabs={tabs} />

      {renderContent(qspTab)}
    </Content.Card>
  );
}
