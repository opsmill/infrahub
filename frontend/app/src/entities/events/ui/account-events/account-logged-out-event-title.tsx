import type { AccountLoggedOutEventType } from "@/shared/api/graphql/generated/types";

import { AccountEventLayout } from "@/entities/events/ui/account-events/account-event-layout";

export const AccountLoggedOutEventTitle = (props: AccountLoggedOutEventType) => {
  return (
    <AccountEventLayout accountId={props.account_id} branch={props.branch}>
      <span className="whitespace-nowrap text-foreground-muted">logged out</span>
    </AccountEventLayout>
  );
};
