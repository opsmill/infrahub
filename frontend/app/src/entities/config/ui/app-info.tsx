import { Skeleton } from "@/shared/components/loading/skeleton";
import { capitalizeFirstLetter } from "@/shared/utils/string";

import { useConfig } from "@/entities/config/ui/config-provider";
import { useGetAppInfo } from "@/entities/config/ui/queries/get-app-info.query";

export function AppInfo() {
  return (
    <div className="inline-flex w-full items-center justify-end text-gray-400 text-xs">
      Infrahub - <AppInstallationType /> - <AppVersion />
    </div>
  );
}

export function AppInstallationType() {
  const config = useConfig();

  return `${capitalizeFirstLetter(config.installation_type)} Edition`;
}

export function AppVersion() {
  const { data, isPending, isError } = useGetAppInfo();

  if (isPending) return <Skeleton className="h-4 w-14" />;

  if (isError) return "N/A";

  return `v${data.version}`;
}
