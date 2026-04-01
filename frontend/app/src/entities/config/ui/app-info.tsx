import { useEffect, useRef, useState } from "react";

import { Skeleton } from "@/shared/components/loading/skeleton";
import { capitalizeFirstLetter } from "@/shared/utils/string";

import { useConfig } from "@/entities/config/ui/config-provider";
import { useGetAppInfo } from "@/entities/config/ui/queries/get-app-info.query";

export function AppInfo() {
  const [showUuid, setShowUuid] = useState(false);
  const [copied, setCopied] = useState(false);
  const copiedTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const { data, isPending, isError } = useGetAppInfo();

  const isInteractive = !isPending && !isError && !!data;

  useEffect(() => {
    return () => {
      if (copiedTimerRef.current) clearTimeout(copiedTimerRef.current);
    };
  }, []);

  const handleClick = () => {
    if (!isInteractive) return;

    if (!showUuid) {
      setShowUuid(true);
      const uuid = data?.deployment_id;
      if (uuid) {
        navigator.clipboard.writeText(uuid);
        setCopied(true);
        if (copiedTimerRef.current) clearTimeout(copiedTimerRef.current);
        copiedTimerRef.current = setTimeout(() => setCopied(false), 2000);
      }
    } else {
      setShowUuid(false);
      setCopied(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      handleClick();
    }
  };

  const uuidDisplay = data?.deployment_id ? `UUID: ${data.deployment_id}` : "N/A";

  return (
    <div
      className={`inline-flex w-full items-center justify-end text-xs ${isInteractive ? "cursor-pointer text-gray-400 hover:text-gray-300" : "text-gray-400"}`}
      data-testid="app-info-toggle"
      onClick={isInteractive ? handleClick : undefined}
      onKeyDown={isInteractive ? handleKeyDown : undefined}
      role={isInteractive ? "button" : undefined}
      tabIndex={isInteractive ? 0 : undefined}
    >
      {showUuid ? (
        copied ? (
          <span className="text-green-400" data-testid="app-info-copied">
            Copied!
          </span>
        ) : (
          uuidDisplay
        )
      ) : (
        <>
          Infrahub - <AppInstallationType /> -{" "}
          <AppVersion data={data} isPending={isPending} isError={isError} />
        </>
      )}
    </div>
  );
}

export function AppInstallationType() {
  const config = useConfig();

  return `${capitalizeFirstLetter(config.installation_type)} Edition`;
}

interface AppVersionProps {
  data: { version: string; deployment_id: string } | undefined;
  isPending: boolean;
  isError: boolean;
}

export function AppVersion({ data, isPending, isError }: AppVersionProps) {
  if (isPending) return <Skeleton className="h-4 w-14" />;

  if (isError || !data) return "N/A";

  return `v${data.version}`;
}
