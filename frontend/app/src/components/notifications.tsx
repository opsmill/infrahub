import { subscription } from "@/shared/api/graphql/queries/notifications/subscription";
import { useSubscription } from "@/hooks/useQuery";
import { gql } from "@apollo/client";

export const Notifications = (props: any) => {
  const { query: queryFromProps } = props;

  const queryString = subscription({ query: queryFromProps });

  const query = gql`
    ${queryString}
  `;

  // biome-ignore lint/correctness/noUnusedVariables: to have an example component using subscriptions
  const { data } = useSubscription(query);

  return <div className="absolute">OK</div>;
};
