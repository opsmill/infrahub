import { Badge, type BadgeProps } from "@/shared/components/ui/badge";

import type { ArtifactStatus } from "@/entities/artifacts/types";

export interface ArtifactStatusBadge extends BadgeProps {
  status: ArtifactStatus;
}

export function ArtifactStatusBadge({ status, ...props }: ArtifactStatusBadge) {
  switch (status as ArtifactStatus) {
    case "Error": {
      return (
        <Badge variant="red" {...props}>
          error
        </Badge>
      );
    }
    case "Pending": {
      return (
        <Badge variant="blue" {...props}>
          pending
        </Badge>
      );
    }
    case "Processing": {
      return (
        <Badge variant="yellow" {...props}>
          processing
        </Badge>
      );
    }
    case "Ready": {
      return (
        <Badge variant="green" {...props}>
          ready
        </Badge>
      );
    }
    default: {
      return <Badge {...props}>{status}</Badge>;
    }
  }
}
