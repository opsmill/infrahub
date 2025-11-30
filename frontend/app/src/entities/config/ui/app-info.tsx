import { Skeleton } from "@/shared/components/skeleton";
import { capitalizeFirstLetter } from "@/shared/utils/string";

import { useGetAppInfo } from "@/entities/config/domain/get-app-info.query";
import { useConfig } from "@/entities/config/ui/config-provider";

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
