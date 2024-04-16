import { useParams } from "react-router-dom";
import { Table } from "../../components/table/table";
import { IPAM_PREFIX_OBJECT } from "../../config/constants";
import { GET_PREFIXES } from "../../graphql/queries/ipam/prefixes";
import useQuery from "../../hooks/useQuery";
import { constructPath } from "../../utils/fetch";
import ErrorScreen from "../error-screen/error-screen";
import LoadingScreen from "../loading-screen/loading-screen";

const constructLink = (data) => {
  switch (data.__typename) {
    case IPAM_PREFIX_OBJECT: {
      return constructPath(`/ipam/prefixes/${encodeURIComponent(data?.prefix?.value)}`);
    }
    default: {
      return constructPath(`/ipam/ip_address/${encodeURIComponent(data?.prefix?.value)}`);
    }
  }
};

export default function IpamIPPrefixes() {
  const { prefix } = useParams();

  const { loading, error, data } = useQuery(GET_PREFIXES, { variables: { prefix: prefix } });

  const rows =
    data &&
    data[IPAM_PREFIX_OBJECT]?.edges.map((edge) => ({
      values: {
        ...edge?.node,
        children_count: edge?.node?.children?.edges?.length,
      },
      link: constructLink(edge?.node),
    }));

  const columns = [
    {
      name: "display_label",
      label: "Name",
    },
    {
      name: "children_count",
      label: "Children",
    },
  ];

  if (error) {
    return <ErrorScreen message="An error occured while retrieving prefixes" />;
  }

  return (
    <div>
      <div>Prefixes</div>

      {loading && <LoadingScreen hideText />}

      {data && <Table rows={rows} columns={columns} />}
    </div>
  );
}
