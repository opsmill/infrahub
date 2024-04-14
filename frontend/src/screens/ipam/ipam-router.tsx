import { Route, Routes } from "react-router-dom";
import IpamIPAddress from "./ipam-ip-address";
import IpamNamespaces from "./ipam-namespaces";

export default function IpamRouter() {
  return (
    <div>
      <Routes>
        <Route path="/:namespace" element={<IpamNamespaces />} />
        <Route path="/:namespace/:subnet" element={<IpamNamespaces />} />
        <Route path="/:namespace/:subnet/:ipaddress" element={<IpamIPAddress />} />
        <Route path="*" element={<IpamNamespaces />} />
      </Routes>
    </div>
  );
}
