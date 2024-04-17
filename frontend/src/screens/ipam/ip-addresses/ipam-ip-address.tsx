import { useParams } from "react-router-dom";
import IpamIPAddressDetails from "./ipam-ip-address-details";
import IpamIPAddressesList from "./ipam-ip-address-list";

export default function IpamIPAddresses() {
  const { ipaddress } = useParams();

  if (ipaddress) {
    return <IpamIPAddressDetails />;
  }

  return <IpamIPAddressesList />;
}
