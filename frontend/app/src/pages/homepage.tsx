import { Icon } from "@iconify-icon/react";
import { Link } from "react-router";

import { LinkButton } from "@/shared/components/buttons/button-primitive";
import Content from "@/shared/components/layout/content";
import { Card } from "@/shared/components/ui/card";

const Homepage = () => {
  return (
    <Content className="p-8">
      <div className="flex flex-col">
        <h1 className="text-3xl font-semibold">Welcome to Infrahub!</h1>
        <h2 className="text-2xl">
          Browse our{" "}
          <Link
            to="https://docs.infrahub.app/"
            target="_blank"
            className="text-custom-blue-700 font-semibold"
          >
            documentation
          </Link>{" "}
          or{" "}
          <Link
            to="https://docs.infrahub.app/tutorials/getting-started/"
            target="_blank"
            className="text-custom-blue-700 font-semibold"
          >
            tutorials
          </Link>{" "}
          to start using <strong className="font-semibold">Infrahub</strong>.
        </h2>
      </div>

      <div className="py-4 flex flex-wrap gap-4">
        <HelperCard
          icon="mdi:learn-outline"
          title="Infrahub Labs"
          description="Explore our hands-on labs for a deep dive into Infrahub's usage and features."
          docLabel="Labs"
          docTo="https://opsmill.instruqt.com/pages/labs"
        />

        <HelperCard
          icon="mdi:file-code-outline"
          title="Schema"
          description="In Infrahub, the schema is at the center of most things."
          docLabel="About Schema"
          docTo="https://docs.infrahub.app/topics/schema/"
          gotoLabel="Explore Schema"
          goto="/schema"
        />

        <HelperCard
          icon="mdi:bookshelf"
          title="Schema Library"
          description="Offers a collection of schemas designed to streamline and standardize infrastructure-related data structures."
          docLabel="Schema Library"
          docTo="https://github.com/opsmill/schema-library/"
        />

        <HelperCard
          icon="mdi:file-code-outline"
          title="Integration with Git"
          description="Connect your Git repository for unified version control for data and files."
          docLabel="About integration"
          docTo="https://docs.infrahub.app/tutorials/getting-started/git-integration/"
          gotoLabel="Your Repository"
          goto="/objects/CoreRepository"
        />
      </div>

      <div className="flex flex-col pt-8">
        <h1 className="text-xl font-semibold">Infrahub Integrations</h1>
        <h2 className="text-l">
          Integrate Infrahub with other tools and solutions. Below is a list of OpsMill-maintained
          packages.
        </h2>
      </div>

      <div className="py-4 flex flex-wrap gap-4">
        <HelperCard
          icon="mdi:toy-brick-marker-outline"
          title="Nornir"
          description="Nornir plugin for Infrahub"
          docLabel="About Nornir plugin"
          docTo="https://docs.infrahub.app/nornir/nornir/"
        />

        <HelperCard
          icon="mdi:developer-board"
          title="Infrahub Python SDK"
          description="The Infrahub Python SDK greatly simplifies how you can interact with Infrahub programmatically."
          docLabel="About Infrahub SDK"
          docTo="https://docs.infrahub.app/python-sdk/"
        />

        <HelperCard
          icon="mdi:ansible"
          title="Infrahub Ansible Collection"
          description="Infrahub Collection for Ansible Galaxy"
          docLabel="About Infrahub Ansible collection"
          docTo="https://docs.infrahub.app/ansible/ansible/"
        />
      </div>
    </Content>
  );
};

type HelperCardProps = {
  icon: string;
  title: string;
  description: string;
  goto?: string;
  gotoLabel?: string;
  docTo?: string;
  docLabel?: string;
};
const HelperCard = ({
  title,
  description,
  icon,
  goto,
  gotoLabel,
  docTo,
  docLabel,
}: HelperCardProps) => {
  return (
    <Card className="border border-gray-200 flex flex-col hover:shadow-md transition-shadow duration-300 w-80">
      <h3 className="font-semibold flex items-center gap-1 mb-1">
        <Icon icon={icon} /> {title}
      </h3>
      <p className="mb-6 text-gray-500 text-sm grow">{description}</p>

      <div className="flex justify-end gap-2">
        {docTo && (
          <LinkButton
            size="sm"
            variant="outline"
            to={docTo}
            target="_blank"
            className="text-xs font-semibold gap-1 border-custom-blue-700 text-custom-blue-700"
          >
            {docLabel} <Icon icon="mdi:open-in-new" />
          </LinkButton>
        )}

        {goto && (
          <LinkButton
            size="sm"
            variant="outline"
            to={goto}
            className="text-xs font-semibold shadow-none"
          >
            {gotoLabel}
          </LinkButton>
        )}
      </div>
    </Card>
  );
};

export function Component() {
  return <Homepage />;
}
