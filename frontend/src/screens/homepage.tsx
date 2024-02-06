import { Link } from "react-router-dom";
import { Icon } from "@iconify-icon/react";

export const Homepage = () => {
  return (
    <main className="bg-custom-white h-full p-8">
      <div className="bg-white flex flex-col">
        <h1 className="text-2xl font-semibold">Welcome to Infrahub!</h1>
        <h2 className="text-2xl">
          Browse our{" "}
          <Link
            to="https://docs.infrahub.app/"
            target="_blank"
            className="text-custom-blue-700 font-semibold">
            developer docs
          </Link>{" "}
          or{" "}
          <Link
            to="https://docs.infrahub.app/guides"
            target="_blank"
            className="text-custom-blue-700 font-semibold">
            explore all the ways
          </Link>{" "}
          to start using <strong className="font-semibold">Infrahub</strong>.
        </h2>
      </div>

      <div className="bg-custom-white py-4 flex flex-wrap gap-4">
        <HelperCard
          icon="mdi:learn-outline"
          title="Getting Started with Infrahub"
          description="Discover the main components and concepts behind Infrahub."
          docLabel="Get started"
          docTo="https://docs.infrahub.app/tutorials/getting-started/"
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
          icon="mdi:file-code-outline"
          title="Integration with Git"
          description="Connect your Git repository for unified version control for data and files."
          docLabel="About integration"
          docTo="https://docs.infrahub.app/tutorials/getting-started/git-integration/"
          gotoLabel="Your Repository"
          goto="/objects/CoreRepository"
        />
      </div>

      <div className="bg-white flex flex-col pt-8">
        <h1 className="text-xl font-semibold">Infrahub Integrations</h1>
        <h2 className="text-l">
          Integrate Infrahub with other tools and solutions. Below is a list of OpsMill-maintained packages.
        </h2>
      </div>

      <div className="bg-custom-white py-4 flex flex-wrap gap-4">
        <HelperCard
          icon="mdi:toy-brick-marker-outline"
          title="Nornir"
          description="Infrahub can be used as an inventory source for Nornir."
          docLabel="About Nornir"
          docTo="https://nornir.readthedocs.io/en/latest/"
        />

        <HelperCard
          icon="mdi:developer-board"
          title="Infrahub Python SDK"
          description="The Infrahub Python SDK greatly simplifies how you can interact with Infrahub programmatically."
          docLabel="About SDK"
          docTo="https://docs.infrahub.app/python-sdk/"
        />

        <HelperCard
          icon="mdi:ansible"
          title="Infrahub Ansible Collection"
          description="Infrahub Collection for Ansible Galaxy"
          docLabel="About Ansible"
          docTo="https://infrahub-ansible.readthedocs.io/en/latest/"
        />
      </div>
    </main>
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
    <div className="max-w-xs rounded p-4 border flex flex-col">
      <h3 className="font-semibold flex items-center gap-1">
        <Icon icon={icon} /> {title}
      </h3>
      <p className="mb-6 text-gray-500 text-sm flex-grow">{description}</p>

      <div className="flex gap-2">
        {docTo && (
          <Link to={docTo} target="_blank">
            <button className="text-xs font-semibold bg-custom-white border p-2 rounded flex items-center gap-1 border-custom-blue-700 text-custom-blue-700">
              {docLabel} <Icon icon="mdi:open-in-new" />
            </button>
          </Link>
        )}

        {goto && (
          <Link to={goto}>
            <button className="text-xs font-semibold bg-custom-white border p-2 rounded">
              {gotoLabel}
            </button>
          </Link>
        )}
      </div>
    </div>
  );
};
