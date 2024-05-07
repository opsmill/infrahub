import { forwardRef } from "react";
import { useParams } from "react-router-dom";
import IpAddressSummary from "./ip-address-summary";
import IpamIPAddressesList from "./ipam-ip-address-list";

const IpamIPAddresses = forwardRef((props, ref) => {
  const { ip_address } = useParams();

  if (ip_address) {
    return <IpAddressSummary />;
  }

  return <IpamIPAddressesList ref={ref} />;
});

export default IpamIPAddresses;
