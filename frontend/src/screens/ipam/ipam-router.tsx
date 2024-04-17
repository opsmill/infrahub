import { Navigate, Route, Routes } from "react-router-dom";
import { Tabs } from "../../components/tabs";
import IpamIPAddress from "./ipam-ip-address";
import { IPAM_QSP, IPAM_TABS } from "./prefixes/constants";
import IpamIPPrefixes from "./prefixes/ipam-prefixes";

const tabs = [
  {
    label: "Summary",
    name: IPAM_TABS.SUMMARY,
  },
  {
    label: "Prefix Details",
    name: IPAM_TABS.PREFIX_DETAILS,
  },
  {
    label: "IP Details",
    name: IPAM_TABS.IP_DETAILS,
  },
];

export default function IpamRouter() {
  return (
    <div>
      <Tabs tabs={tabs} qsp={IPAM_QSP} />

      <div className="m-4">
        <Routes>
          {/* <Route path="/:namespace" element={<IpamNamespaces />} /> */}
          <Route path="/ip-addresses/:ipaddress" element={<IpamIPAddress />} />
          <Route path="/prefixes/:prefix" element={<IpamIPPrefixes />} />
          <Route path="/prefixes" element={<IpamIPPrefixes />} />
          <Route path="/" element={<Navigate to="/ipam/prefixes" />} />
        </Routes>
      </div>
    </div>
  );
}
