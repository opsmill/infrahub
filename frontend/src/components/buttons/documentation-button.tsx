import { Link } from "react-router-dom";
import { Icon } from "@iconify-icon/react";
import { classNames } from "../../utils/common";
import { INFRAHUB_DOC_URL } from "../../config/config";

export const DOC_URLS = {
  CoreGroup: `${INFRAHUB_DOC_URL}/release-notes/release-0_6_0#groups`,
  CoreGraphQLQueryGroup: `${INFRAHUB_DOC_URL}/release-notes/release-0_6_0#groups`,
  CoreStandardGroup: `${INFRAHUB_DOC_URL}/release-notes/release-0_6_0#groups`,
  schema: `${INFRAHUB_DOC_URL}/topics/schema`,
  CoreProposedChange: `${INFRAHUB_DOC_URL}/topics/proposed-change`,
  CoreRepository: `${INFRAHUB_DOC_URL}/tutorials/getting-started/git-integration`,
  CoreReadOnlyRepository: `${INFRAHUB_DOC_URL}/guides/repository#read-only-repository`,
  CoreGraphQLQuery: `${INFRAHUB_DOC_URL}/topics/graphql`,
  branches: `${INFRAHUB_DOC_URL}/tutorials/getting-started/branches`,
  CoreCheckDefinition: `${INFRAHUB_DOC_URL}/topics/check`,
  CoreArtifact: `${INFRAHUB_DOC_URL}/topics/artifact`,
  CoreArtifactDefinition: `${INFRAHUB_DOC_URL}/topics/artifact`,
  CoreTransformation: `${INFRAHUB_DOC_URL}/topics/transformation`,
} as const;

const LABELS: Record<keyof typeof DOC_URLS, string> = {
  CoreGroup: "Group",
  CoreGraphQLQueryGroup: "Group",
  CoreStandardGroup: "Group",
  schema: "Schema",
  CoreProposedChange: "Proposed change",
  CoreRepository: "Git Repository",
  CoreReadOnlyRepository: "Read-Only Repository",
  CoreGraphQLQuery: "GraphQL",
  branches: "Branches",
  CoreCheckDefinition: "Checks",
  CoreArtifact: "Artifact",
  CoreArtifactDefinition: "Artifact",
  CoreTransformation: "Transformation",
};

type DocumentationButtonProps = {
  topic: keyof typeof DOC_URLS;
  className?: string;
};

export const DocumentationButton = ({ topic, className = "" }: DocumentationButtonProps) => {
  const docUrl = DOC_URLS[topic];

  if (!docUrl) return null;

  return (
    <Link
      to={docUrl}
      target="_blank"
      className={classNames(
        "flex items-center gap-2 text-gray-600 text-xs rounded hover:bg-gray-100 px-2 py-1",
        className
      )}>
      <Icon icon="mdi:book-open-blank-variant-outline" className="text-base" />
      {LABELS[topic]} documentation
    </Link>
  );
};
