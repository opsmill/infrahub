import { XIcon } from "lucide-react";

import InfrahubLogo from "@/assets/Infrahub-SVG-hori.svg?react";

import { CopyToClipboardButton } from "@/shared/components/aria/copy-to-clipboard-button";
import { Modal } from "@/shared/components/aria/modal";
import { Separator } from "@/shared/components/aria/separator";
import { Col, Row } from "@/shared/components/container";
import { Skeleton } from "@/shared/components/loading/skeleton";
import { Button } from "@/shared/components/ui/button";

import { useConfig } from "@/entities/config/ui/config-provider";
import { useGetAppInfo } from "@/entities/config/ui/queries/get-app-info.query";

interface AboutModalProps {
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
}

export function AboutModal({ isOpen, onOpenChange }: AboutModalProps) {
  const config = useConfig();
  const { data, isPending, isError } = useGetAppInfo();

  const version = isPending ? null : isError || !data ? "N/A" : `v${data.version}`;
  const deploymentId = isPending ? null : isError || !data ? "N/A" : data.deployment_id;

  return (
    <Modal
      isOpen={isOpen}
      onOpenChange={onOpenChange}
      aria-label="About Infrahub"
      className="w-full max-w-lg"
    >
      <Row className="mb-1 justify-between p-2">
        <InfrahubLogo className="h-8" role="img" aria-label="Infrahub logo" />
        <Button variant="ghost" size="icon" onClick={() => onOpenChange(false)} aria-label="Close">
          <XIcon className="size-3.5" />
        </Button>
      </Row>

      <Col className="rounded-xl bg-stone-100 px-3 py-2.5">
        <InfoRow label="Version" value={version} isLoading={isPending} />
        <Separator />
        <InfoRow label="Edition" value={config.installation_type} />
        <Separator />
        <InfoRow label="Deployment ID" value={deploymentId} isLoading={isPending} />
      </Col>
    </Modal>
  );
}

function InfoRow({
  label,
  value,
  isLoading,
}: {
  label: string;
  value: string | null;
  isLoading?: boolean;
}) {
  return (
    <Row className="justify-between">
      <span className="text-sm text-stone-600">{label}</span>
      <Row>
        {isLoading ? (
          <Skeleton className="h-7 w-20" />
        ) : (
          <>
            <span className="text-sm text-stone-800">{value}</span>
            {value && value !== "N/A" && (
              <CopyToClipboardButton data={value} aria-label={`Copy ${label}`} />
            )}
          </>
        )}
      </Row>
    </Row>
  );
}
