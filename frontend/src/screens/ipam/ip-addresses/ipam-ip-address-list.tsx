import { useParams } from "react-router-dom";
import { StringParam, useQueryParam } from "use-query-params";
import { Table } from "../../../components/table/table";
import { IPAM_IP_ADDRESS_OBJECT } from "../../../config/constants";
import { GET_IP_ADDRESSES } from "../../../graphql/queries/ipam/ip-address";
import useQuery from "../../../hooks/useQuery";
import { constructPath } from "../../../utils/fetch";
import ErrorScreen from "../../error-screen/error-screen";
import LoadingScreen from "../../loading-screen/loading-screen";
import { IPAM_QSP } from "../constants";

export default function IpamIPAddressesList() {
  const { prefix } = useParams();
  const [qspTab] = useQueryParam(IPAM_QSP, StringParam);

  const constructLink = (data) => {
    if (prefix) {
      return constructPath(
        `/ipam/prefixes/${encodeURIComponent(prefix)}/${encodeURIComponent(data?.address?.value)}`,
        [{ name: IPAM_QSP, value: qspTab }]
      );
    }

    return constructPath(`/ipam/ip-addresses/${encodeURIComponent(data?.address?.value)}`, [
      { name: IPAM_QSP, value: qspTab },
    ]);
  };

  const { loading, error, data } = useQuery(GET_IP_ADDRESSES, { variables: { prefix: prefix } });

  const rows =
    data &&
    data[IPAM_IP_ADDRESS_OBJECT]?.edges.map((edge) => ({
      values: {
        ...edge?.node,
      },
      link: constructLink(edge?.node),
    }));

  const columns = [
    {
      name: "display_label",
      label: "Name",
    },
  ];

  if (error) {
    return <ErrorScreen message="An error occured while retrieving prefixes" />;
  }

  return (
    <div>
      <div>IP Addresses</div>

      {loading && <LoadingScreen hideText />}

      {data && <Table rows={rows} columns={columns} />}
    </div>
  );
}
