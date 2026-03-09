import { useQueryState } from "nuqs";

import { Avatar } from "@/shared/components/display/avatar";
import ErrorScreen from "@/shared/components/errors/error-screen";
import Content from "@/shared/components/layout/content";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { Tabs } from "@/shared/components/tabs";
import { QSP } from "@/shared/config/qsp";
import { useTitle } from "@/shared/hooks/useTitle";

import { useGetAccountProfile } from "@/entities/user-profile/ui/queries/get-account-profile.query";

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
  const { data: account, isPending, error } = useGetAccountProfile();
  useTitle(account?.display_label ?? "Profile");

  if (error) {
    return <ErrorScreen />;
  }

  if (isPending) {
    return <LoadingIndicator className="h-full" />;
  }

  return (
    <Content.Card>
      <Content.CardTitle
        title={
          <div className="flex items-center gap-2">
            <Avatar name={account.name?.value} />

            <div className="ml-2">
              <h3>{account.display_label}</h3>

              <p className="text-gray-500 text-sm">{account.description?.value ?? "-"}</p>
            </div>
          </div>
        }
      />

      <Tabs tabs={tabs} />

      {renderContent(qspTab)}
    </Content.Card>
  );
}
