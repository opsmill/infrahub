import { gql } from "@apollo/client";
import { useAtom } from "jotai";
import { StringParam, useQueryParam } from "use-query-params";
import { Avatar } from "../../components/display/avatar";
import { Tabs } from "../../components/tabs";
import { ACCESS_TOKEN_KEY, ACCOUNT_OBJECT } from "../../config/constants";
import { QSP } from "../../config/qsp";
import { getProfileDetails } from "../../graphql/queries/accounts/getProfileDetails";
import useQuery from "../../hooks/useQuery";
import { useTitle } from "../../hooks/useTitle";
import { schemaState } from "../../state/atoms/schema.atom";
import { parseJwt } from "../../utils/common";
import ErrorScreen from "../error-screen/error-screen";
import LoadingScreen from "../loading-screen/loading-screen";
import TabPassword from "./tab-account";
import TabPreferences from "./tab-preferences";
import TabProfile from "./tab-profile";
import Content from "../layout/content";

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
