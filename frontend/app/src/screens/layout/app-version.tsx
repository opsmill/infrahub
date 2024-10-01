import { CONFIG } from "@/config/config";
import { components } from "@/infraops";
import { fetchUrl } from "@/utils/fetch";
import { useEffect, useState } from "react";

export const AppVersion = () => {
  const [info, setInfo] = useState<components["schemas"]["InfoAPI"] | null>(null);

  useEffect(() => {
    fetchUrl(CONFIG.INFO_URL).then((result) => setInfo(result));
  }, []);

  if (!info) return null;

  return <div className="text-right text-xs text-gray-400">Infrahub - v{info.version}</div>;
};
