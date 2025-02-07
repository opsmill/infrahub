import { NODE_OBJECT } from "@/config/constants";
import { getObjectDisplayLabel } from "@/entities/nodes/api/getObjectDisplayLabel";
import useQuery from "@/shared/api/graphql/useQuery";
import { classNames } from "@/shared/utils/common";
import { gql } from "@apollo/client";
import { Spinner } from "./spinner";

type DisplayLabelProps = {
  id: string;
  kind?: string;
  className?: string;
};

export const DisplayLabel = ({ id, kind = NODE_OBJECT, className }: DisplayLabelProps) => {
  const queryString = getObjectDisplayLabel({ kind });

  const query = gql`
    ${queryString}
  `;

  const { loading, error, data } = useQuery(query, { variables: { ids: [id] } });

  const object = data?.[kind]?.edges?.[0]?.node ?? {};

  if (loading) {
    return <Spinner />;
  }

  if (error || !object?.display_label) {
    return <div className="italic">Name not found</div>;
  }

  return <div className={classNames(className)}>{object?.display_label}</div>;
};
