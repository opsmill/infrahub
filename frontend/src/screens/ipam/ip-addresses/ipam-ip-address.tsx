import { useParams } from "react-router-dom";
import IpAddressSummary from "./ip-address-summary";
import IpamIPAddressesList from "./ipam-ip-address-list";

export default function IpamIPAddresses() {
  const { ipaddress } = useParams();

  if (ipaddress) {
    return <IpAddressSummary />;
  }

  return <IpamIPAddressesList />;
}
