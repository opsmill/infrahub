import { Icon } from "@iconify-icon/react";
import { useParams } from "react-router-dom";
import { StringParam, useQueryParam } from "use-query-params";
import { Link } from "../../../components/utils/link";
import { GET_IP_ADDRESSES } from "../../../graphql/queries/ipam/ip-address";
import useQuery from "../../../hooks/useQuery";
import { constructPath } from "../../../utils/fetch";
import ErrorScreen from "../../error-screen/error-screen";
import LoadingScreen from "../../loading-screen/loading-screen";
import { IPAM_QSP } from "../constants";

export default function IpamIPAddressDetails() {
  const { prefix, ipaddress } = useParams();
  const [qspTab] = useQueryParam(IPAM_QSP, StringParam);

  const parentLink = prefix
    ? constructPath(`/ipam/prefixes/${encodeURIComponent(prefix)}`, [
        { name: IPAM_QSP, value: qspTab },
      ])
    : constructPath("/ipam/ip-addresses", [{ name: IPAM_QSP, value: qspTab }]);

  const { loading, error, data } = useQuery(GET_IP_ADDRESSES, { variables: { ipaddress } });

  if (error) {
    return <ErrorScreen message="An error occured while retrieving prefixes" />;
  }

  return (
    <div>
      <div className="flex items-center mb-2">
        <Link to={parentLink}>All IP Addresses</Link>
        <Icon icon={"mdi:chevron-right"} />
        <span>{ipaddress}</span>
      </div>

      {loading && <LoadingScreen hideText />}

      <pre>{JSON.stringify(data, null, 2)}</pre>
    </div>
  );
}
