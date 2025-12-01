import { Icon } from "@iconify-icon/react";
import { BookOpen, ExternalLink } from "lucide-react";
import type { ReactNode } from "react";

import { Separator } from "@/shared/components/aria/separator";
import { LinkButton, type LinkButtonProps } from "@/shared/components/buttons/button-primitive";
import { HomeCard } from "@/shared/components/ui/home-card";

export const GettingStarted = ({ className }: { className?: string }) => {
  return (
    <HomeCard className={className}>
      <HomeCard.Title>
        <span>Getting Started with Infrahub</span>

        <div className="flex items-center gap-3">
          <LinkButton
            variant={"outline"}
            className="flex items-center gap-2"
            to={"https://docs.infrahub.app/"}
            target="_blank"
            rel="noopener noreferrer"
          >
            <BookOpen className="size-4 text-gray-400" /> Documentation
            <ExternalLink className="size-4 text-gray-400" />
          </LinkButton>
        </div>
      </HomeCard.Title>

      <HomeCard.Content>
        <div className="grid grid-cols-1 lg:grid-cols-2">
          <GettingStartedContentItem>
            <GettingStartedContentItem.Title>
              <Icon icon={"mdi:graduation-cap-outline"} className="size-4" />
              Infrahub Labs
              <GettingStartedContentItem.Link
                to={"https://opsmill.instruqt.com/pages/labs/"}
                target="_blank"
                rel="noopener noreferrer"
              >
                Labs
              </GettingStartedContentItem.Link>
            </GettingStartedContentItem.Title>

            <span className="text-gray-500">
              Explore our hands-on labs for a deep dive into Infrahub's usage and features.
            </span>
          </GettingStartedContentItem>

          <GettingStartedContentItem>
            <GettingStartedContentItem.Title>
              <Icon icon={"mdi:server"} className="size-4" />
              Nornir
              <GettingStartedContentItem.Link
                to={"https://docs.infrahub.app/nornir/nornir/"}
                target="_blank"
                rel="noopener noreferrer"
              >
                Docs
              </GettingStartedContentItem.Link>
            </GettingStartedContentItem.Title>

            <span className="text-gray-500">
              Integrate Infrahub with Nornir for automated network device configuration and
              management.
            </span>
          </GettingStartedContentItem>

          <GettingStartedContentItem>
            <GettingStartedContentItem.Title>
              <Icon icon={"mdi:code-json"} className="size-4" />
              Schema
              <GettingStartedContentItem.Link
                to={"https://docs.infrahub.app/topics/schema/"}
                target="_blank"
                rel="noopener noreferrer"
              >
                Docs
              </GettingStartedContentItem.Link>
              <Separator orientation="vertical" className="h-6" />
              <GettingStartedContentItem.Link to={"/schema"} hideExternal>
                Explore Schema
              </GettingStartedContentItem.Link>
            </GettingStartedContentItem.Title>

            <span className="text-gray-500">
              In Infrahub, the schema is at the center of most things.
            </span>
          </GettingStartedContentItem>

          <GettingStartedContentItem>
            <GettingStartedContentItem.Title>
              <Icon icon={"mdi:subscriber-identification-module-outline"} className="size-4" />
              Infrahub Python SDK
              <GettingStartedContentItem.Link
                to={"https://docs.infrahub.app/python-sdk/"}
                target="_blank"
                rel="noopener noreferrer"
              >
                Docs
              </GettingStartedContentItem.Link>
            </GettingStartedContentItem.Title>

            <span className="text-gray-500">
              The Infrahub Python SDK greatly simplifies how you can interact with Infrahub
              programmatically.
            </span>
          </GettingStartedContentItem>

          <GettingStartedContentItem>
            <GettingStartedContentItem.Title>
              <Icon icon={"mdi:cloud-json"} className="size-4" />
              Schema Library
              <GettingStartedContentItem.Link
                to={"https://github.com/opsmill/schema-library/"}
                target="_blank"
                rel="noopener noreferrer"
              >
                Docs
              </GettingStartedContentItem.Link>
            </GettingStartedContentItem.Title>

            <span className="text-gray-500">
              Offers a collection of schemas designed to streamline and standardize
              infrastructure-related data structures.
            </span>
          </GettingStartedContentItem>

          <GettingStartedContentItem>
            <GettingStartedContentItem.Title>
              <Icon icon={"mdi:ansible"} className="size-4" />
              Infrahub Ansible Collection
              <GettingStartedContentItem.Link
                to={"https://docs.infrahub.app/ansible/ansible/"}
                target="_blank"
                rel="noopener noreferrer"
              >
                Docs
              </GettingStartedContentItem.Link>
            </GettingStartedContentItem.Title>

            <span className="text-gray-500">Infrahub Collection for Ansible Galaxy.</span>
          </GettingStartedContentItem>
        </div>
      </HomeCard.Content>
    </HomeCard>
  );
};

interface GettingStartedContentItemProps {
  children: ReactNode;
}

const GettingStartedContentItemRoot = ({ children }: GettingStartedContentItemProps) => {
  return <div className="p-3">{children}</div>;
};

const GettingStartedContentItemTitle = ({ children }: GettingStartedContentItemProps) => {
  return <div className="flex items-center gap-2 font-semibold">{children}</div>;
};

interface GettingStartedContentItemLinkProps extends LinkButtonProps {
  hideExternal?: boolean;
}

const GettingStartedContentItemLink = ({
  children,
  to,
  hideExternal,
  ...props
}: GettingStartedContentItemLinkProps) => {
  return (
    <LinkButton
      variant={"ghost"}
      className="flex items-center gap-2 px-2 py-1 text-gray-500 underline"
      to={to}
      {...props}
    >
      {children}
      {!hideExternal && <ExternalLink className="size-4 text-gray-400" />}
    </LinkButton>
  );
};

const GettingStartedContentItem = Object.assign(GettingStartedContentItemRoot, {
  Title: GettingStartedContentItemTitle,
  Link: GettingStartedContentItemLink,
});
