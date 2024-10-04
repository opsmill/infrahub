import { CONFIG } from "@/config/config";
import { components } from "@/infraops";
import { fetchUrl } from "@/utils/fetch";
import { useEffect, useState } from "react";
import { Skeleton } from "@/components/skeleton";

export const AppVersion = () => {
  const [info, setInfo] = useState<components["schemas"]["InfoAPI"] | null>(null);

  useEffect(() => {
    fetchUrl(CONFIG.INFO_URL).then((result) => setInfo(result));
  }, []);

  return (
    <div className="text-xs text-gray-400 inline-flex items-center w-full justify-end">
      Infrahub - v{info ? info.version : <Skeleton className="h-4 w-14" />}
    </div>
  );
};
