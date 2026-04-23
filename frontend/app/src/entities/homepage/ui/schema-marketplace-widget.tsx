import { Icon } from "@iconify-icon/react";

import { Row } from "@/shared/components/container";

import { HomeCard } from "@/entities/homepage/ui/home-card";
import { useHasUserSchemas } from "@/entities/schema-marketplace/hooks/use-has-user-schemas";

interface SchemaMarketplaceWidgetProps {
  className?: string;
}

export function SchemaMarketplaceWidget({ className }: SchemaMarketplaceWidgetProps) {
  const hasUserSchemas = useHasUserSchemas();

  return (
    <HomeCard className={className}>
      <HomeCard.Title>
        <Row>
          <Icon icon="mdi:store" /> Schema Marketplace
        </Row>

        <HomeCard.Link to="/schema-marketplace">
          {hasUserSchemas ? "Browse" : "Get started"} <Icon icon={"mdi:chevron-right"} />
        </HomeCard.Link>
      </HomeCard.Title>

      <HomeCard.Content className="flex flex-col gap-2">
        {hasUserSchemas ? (
          <p className="text-gray-500 text-sm">
            Install additional schemas from the Infrahub Marketplace into a Git repository.
          </p>
        ) : (
          <p className="text-sm">
            <span className="font-medium">Get started — install your first schema.</span>{" "}
            <span className="text-gray-500">
              Browse ready-made schemas from the Infrahub Marketplace and install one into a Git
              repository to populate this instance.
            </span>
          </p>
        )}
      </HomeCard.Content>
    </HomeCard>
  );
}
