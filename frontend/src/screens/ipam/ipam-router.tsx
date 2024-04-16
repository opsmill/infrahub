import { Navigate, Route, Routes } from "react-router-dom";
import IpamIPAddress from "./ipam-ip-address";
import IpamIPPrefix from "./ipam-prefix";
import IpamIPPrefixes from "./ipam-prefixes";

export default function IpamRouter() {
  return (
    <div>
      <Routes>
        {/* <Route path="/:namespace" element={<IpamNamespaces />} /> */}
        <Route path="/ip-addresses/:ipaddress" element={<IpamIPAddress />} />
        <Route path="/prefixes/:prefix" element={<IpamIPPrefix />} />
        <Route path="/prefixes" element={<IpamIPPrefixes />} />
        <Route path="/" element={<Navigate to="/ipam/prefixes" />} />
      </Routes>
    </div>
  );
}
