import { Route, Routes } from "react-router-dom";
import IpamIPAddress from "./ipam-ip-address";
import IpamNamespaces from "./ipam-namespaces";
import IpamIPPrefixes from "./ipam-prefixes";

export default function IpamRouter() {
  return (
    <div>
      <Routes>
        <Route path="/:namespace" element={<IpamNamespaces />} />
        <Route path="/:namespace/:prefix" element={<IpamIPPrefixes />} />
        <Route path="/:namespace/:prefix/:ipaddress" element={<IpamIPAddress />} />
        <Route path="*" element={<IpamNamespaces />} />
      </Routes>
    </div>
  );
}
