import { ClockAlertIcon, ClockFadingIcon, KeySquareIcon } from "lucide-react";

import type { AccountTokenNode } from "@/shared/api/graphql/generated/types";
import { Row } from "@/shared/components/container";
import { formatFullDate } from "@/shared/utils/date";

import { AccountTokenDeleteAction } from "@/entities/user-profile/ui/account-token-delete-action";

export interface AccountTokenItemProps {
  token: AccountTokenNode;
}

export function AccountTokenItem({ token }: AccountTokenItemProps) {
  return (
    <Row className="gap-3 p-3 text-sm" data-testid={`account-token-${token.name}`}>
      <KeySquareIcon className="size-5 text-stone-600" />

      <div className="min-w-0">
        <div className="truncate font-medium">{token.name}</div>
        <ExpirationDate date={token.expiration} />
      </div>

      <AccountTokenDeleteAction token={token} className="ml-auto" />
    </Row>
  );
}

export const ExpirationDate = ({ date }: { date?: string | null }) => {
  if (!date) {
    return (
      <Row className="text-amber-600">
        <ClockAlertIcon className="size-4" /> This token has no expiration date
      </Row>
    );
  }

  const isExpired = new Date(date) < new Date();

  if (isExpired) {
    return (
      <Row className="text-red-600">
        <ClockAlertIcon className="size-4" /> Expired on {formatFullDate(date)}
      </Row>
    );
  }

  return (
    <Row className="text-gray-500">
      <ClockFadingIcon className="size-4" /> Expires {formatFullDate(date)}
    </Row>
  );
};
