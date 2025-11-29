import { useEffect, useState } from "react";

import { fetchUrl } from "@/shared/api/rest/fetch";
import type { components } from "@/shared/api/rest/types.generated";
import { Skeleton } from "@/shared/components/skeleton";
import { CONFIG } from "@/shared/config/config";
import { capitalizeFirstLetter } from "@/shared/utils/string";

import { useConfig } from "@/entities/config/ui/config-provider";

export const AppVersion = () => {
  const [info, setInfo] = useState<components["schemas"]["InfoAPI"] | null>(null);
  const config = useConfig();

  useEffect(() => {
    fetchUrl(CONFIG.INFO_URL)
      .then((result) => setInfo(result))
      .catch((error) => console.error("Failed to load version info:", error.message));
  }, []);

  const installationType = capitalizeFirstLetter(config.installation_type) + " Edition";
  const version = info ? info.version : <Skeleton className="h-4 w-14" />;

  return (
    <div className="inline-flex w-full items-center justify-end text-gray-400 text-xs">
      Infrahub - {installationType} - v{version}
    </div>
  );
};
