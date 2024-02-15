import { useSubscription } from "../hooks/useQuery";
import { subscription } from "../graphql/queries/notifications/subscription";
import { gql } from "@apollo/client";

export const Notifications = (props: any) => {
  const { query: queryFromProps } = props;

  const queryString = subscription({ query: queryFromProps });

  const query = gql`
    ${queryString}
  `;

  const { data } = useSubscription(query);
  console.log("data: ", data);

  return <div className="absolute">OK</div>;
};
