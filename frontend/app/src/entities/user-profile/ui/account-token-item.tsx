import { AccountTokenDeleteAction } from "@/entities/user-profile/ui/account-token-delete-action";
import { AccountTokenNode } from "@/shared/api/graphql/generated/graphql";
import { Card } from "@/shared/components/ui/card";
import { classNames } from "@/shared/utils/common";
import { formatFullDate } from "@/shared/utils/date";
import { Icon } from "@iconify-icon/react";

export interface AccountTokenItemProps {
  token: AccountTokenNode;
}

export function AccountTokenItem({ token }: AccountTokenItemProps) {
  return (
    <Card
      className="flex items-center gap-4 p-4 text-sm"
      data-testid={`account-token-${token.name}`}
    >
      <Icon icon="mdi:key-variant" className="text-xl text-gray-600" />
      <div className="grow min-w-0">
        <div className="font-medium truncate">{token.name}</div>
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
      <Icon icon="mdi:alert-circle" className="text-amber-500 text-base shrink-0" />
      <span>This token has no expiration date</span>
    </p>
  );
};
