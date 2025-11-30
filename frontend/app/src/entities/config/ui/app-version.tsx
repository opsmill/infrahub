import { Skeleton } from "@/shared/components/skeleton";
import { capitalizeFirstLetter } from "@/shared/utils/string";

import { useGetAppInfo } from "@/entities/config/domain/get-app-info.query";
import { useConfig } from "@/entities/config/ui/config-provider";

export const AppVersion = () => {
  const config = useConfig();
  const { data: info } = useGetAppInfo();

  const installationType = capitalizeFirstLetter(config.installation_type) + " Edition";
  const version = info ? info.version : <Skeleton className="h-4 w-14" />;

  return (
    <div className="inline-flex w-full items-center justify-end text-gray-400 text-xs">
      Infrahub - {installationType} - v{version}
    </div>
  );
};
