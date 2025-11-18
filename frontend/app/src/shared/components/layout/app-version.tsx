import { useEffect, useState } from "react";

import { CONFIG } from "@/config/config";

import { fetchUrl } from "@/shared/api/rest/fetch";
import type { components } from "@/shared/api/rest/types.generated";
import { Skeleton } from "@/shared/components/skeleton";

export const AppVersion = () => {
  const [info, setInfo] = useState<components["schemas"]["InfoAPI"] | null>(null);

  useEffect(() => {
    fetchUrl(CONFIG.INFO_URL).then((result) => setInfo(result));
  }, []);

  return (
    <div className="inline-flex w-full items-center justify-end text-gray-400 text-xs">
      Infrahub - v{info ? info.version : <Skeleton className="h-4 w-14" />}
    </div>
  );
};
