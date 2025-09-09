import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { classNames } from "@/shared/utils/common";

import { useInfrahubAccountToken } from "@/entities/user-profile/domain/get-infrahub-account-token.query";
import { AccountTokenItem } from "@/entities/user-profile/ui/account-token-item";

export interface AccountTokenListProps extends React.HTMLAttributes<HTMLDivElement> {}

export function AccountTokenList({ className, ...props }: AccountTokenListProps) {
  const { data, isPending, error } = useInfrahubAccountToken();

  if (isPending) return <LoadingIndicator />;

  if (error) return <div>Error: {error.message}</div>;

  return (
    <div className={classNames("space-y-2", className)} {...props}>
      {data?.map((token) => (
        <AccountTokenItem key={token.id} token={token} />
      ))}
    </div>
  );
}
