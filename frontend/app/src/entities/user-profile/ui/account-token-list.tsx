import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { classNames } from "@/shared/utils/common";

import { AccountTokenItem } from "@/entities/user-profile/ui/account-token-item";
import { useInfrahubAccountToken } from "@/entities/user-profile/ui/queries/get-infrahub-account-token.query";

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
