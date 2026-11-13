import { Button, Card, Modal } from "@infrahub/ui";
import { XIcon } from "lucide-react";

import { Separator } from "@/shared/components/aria/separator";
import { Row } from "@/shared/components/container";
import { InfoRow } from "@/shared/components/display/info-row";
import { InfrahubLogo } from "@/shared/components/ui/infrahub-logo";

import { useConfig } from "@/entities/config/ui/config-provider";
import { useGetAppInfo } from "@/entities/config/ui/queries/get-app-info.query";
import { LicenseAboutRows } from "@/entities/license/ui/license-about-rows";

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
    <Modal isOpen={isOpen} onOpenChange={onOpenChange} aria-label="About Infrahub">
      <Row className="mb-1 justify-between p-2">
        <InfrahubLogo className="h-8" role="img" aria-label="Infrahub logo" />
        <Button
          variant="ghost"
          size="xs"
          shape="circle"
          onPress={() => onOpenChange(false)}
          aria-label="Close"
        >
          <XIcon className="size-3.5" />
        </Button>
      </Row>

      <Card variant="panel" className="gap-2 rounded-xl px-3 py-2.5">
        <InfoRow label="Version" value={version} isLoading={isPending} />
        <Separator />
        <InfoRow label="Edition" value={config.installation_type} />
        <Separator />
        <InfoRow label="Deployment ID" value={deploymentId} isLoading={isPending} />
        <LicenseAboutRows license={data?.license} />
      </Card>
    </Modal>
  );
}
