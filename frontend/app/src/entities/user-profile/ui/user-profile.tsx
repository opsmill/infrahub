import { Outlet } from "react-router";

import { Avatar } from "@/shared/components/display/avatar";
import ErrorScreen from "@/shared/components/errors/error-screen";
import Content from "@/shared/components/layout/content";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { useTitle } from "@/shared/hooks/useTitle";

import { ProfileTabs } from "@/entities/user-profile/ui/profile-tabs";
import { useGetAccountProfile } from "@/entities/user-profile/ui/queries/get-account-profile.query";

export function UserProfilePage() {
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

      <ProfileTabs />

      <Outlet />
    </Content.Card>
  );
}
