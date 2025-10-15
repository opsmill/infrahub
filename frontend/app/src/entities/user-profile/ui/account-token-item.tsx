import { Icon } from "@iconify-icon/react";

import type { AccountTokenNode } from "@/shared/api/graphql/generated/graphql";
import { Card } from "@/shared/components/ui/card";
import { classNames } from "@/shared/utils/common";
import { formatFullDate } from "@/shared/utils/date";

import { AccountTokenDeleteAction } from "@/entities/user-profile/ui/account-token-delete-action";

export interface AccountTokenItemProps {
  token: AccountTokenNode;
}

export function AccountTokenItem({ token }: AccountTokenItemProps) {
  return (
    <Card
      className="flex items-center gap-4 p-4 text-sm"
      data-testid={`account-token-${token.name}`}
    >
      <Icon icon="mdi:key-variant" className="text-gray-600 text-xl" />
      <div className="min-w-0 grow">
        <div className="truncate font-medium">{token.name}</div>
        {token.expiration ? (
          <ExpirationDate date={token.expiration} />
        ) : (
          <NoExpirationDataWarning />
        )}
      </div>
      <AccountTokenDeleteAction token={token} />
    </Card>
  );
}

export const ExpirationDate = ({ date }: { date: string }) => {
  const isExpired = new Date(date) < new Date();

  return (
    <p className={classNames("flex items-center gap-1 text-gray-500", isExpired && "text-red-600")}>
      {isExpired && <Icon icon="mdi:clock-alert" className="text-base" />}
      {isExpired ? "Expired on" : "Expires"} {formatFullDate(date)}
    </p>
  );
};

export const NoExpirationDataWarning = () => {
  return (
    <p className="flex items-center gap-1 text-yellow-800">
      <Icon icon="mdi:alert-circle" className="shrink-0 text-amber-500 text-base" />
      <span>This token has no expiration date</span>
    </p>
  );
};
