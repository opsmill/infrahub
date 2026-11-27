import { LinkButton } from "@infrahub/ui";
import { SearchXIcon } from "lucide-react";

import { Col } from "@/shared/components/container";

export interface PoolItemNotFoundProps {
  title: string;
  description: string;
  href: string;
  linkLabel: string;
}

export function PoolItemNotFound({ title, description, href, linkLabel }: PoolItemNotFoundProps) {
  return (
    <Col className="items-center gap-4 px-6 py-16 text-center">
      <span className="flex size-10 items-center justify-center rounded-xl bg-content-muted text-foreground-muted">
        <SearchXIcon className="size-5" aria-hidden />
      </span>
      <Col className="max-w-sm items-center gap-1.5">
        <p className="font-medium">{title}</p>
        <p className="text-pretty text-foreground-muted text-sm">{description}</p>
      </Col>
      <LinkButton variant="outline" size="sm" href={href}>
        {linkLabel}
      </LinkButton>
    </Col>
  );
}
