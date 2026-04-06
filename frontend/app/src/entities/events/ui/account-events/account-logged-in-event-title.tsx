import type { AccountLoggedInEventType } from "@/shared/api/graphql/generated/types";

import { AccountEventLayout } from "@/entities/events/ui/account-events/account-event-layout";

const AUTH_METHOD_LABELS: Record<string, string> = {
  PASSWORD: "password",
  OAUTH2: "OAuth2",
  OIDC: "OIDC",
};

export const AccountLoggedInEventTitle = (props: AccountLoggedInEventType) => {
  return (
    <AccountEventLayout accountId={props.account_id} branch={props.branch}>
      <span className="whitespace-nowrap text-gray-600">
        logged in via {AUTH_METHOD_LABELS[props.auth_method] ?? props.auth_method}
      </span>
    </AccountEventLayout>
  );
};
