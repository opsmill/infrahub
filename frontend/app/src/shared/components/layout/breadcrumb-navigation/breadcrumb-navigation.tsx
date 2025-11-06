import { matchPath, useLocation, useParams } from "react-router";

import { BreadcrumbActivities } from "@/shared/components/layout/breadcrumb-navigation/breadcrumb-activities";
import { BreadcrumbBranches } from "@/shared/components/layout/breadcrumb-navigation/breadcrumb-branches";
import { BreadcrumbGraphql } from "@/shared/components/layout/breadcrumb-navigation/breadcrumb-graphql";
import { BreadcrumbIpNamespaces } from "@/shared/components/layout/breadcrumb-navigation/breadcrumb-ip-namespaces";
import { BreadcrumbIpam } from "@/shared/components/layout/breadcrumb-navigation/breadcrumb-ipam";
import { BreadcrumbObjects } from "@/shared/components/layout/breadcrumb-navigation/breadcrumb-objects";
import { BreadcrumbProfile } from "@/shared/components/layout/breadcrumb-navigation/breadcrumb-profile";
import { BreadcrumbProposedChanges } from "@/shared/components/layout/breadcrumb-navigation/breadcrumb-proposed-changes";
import { BreadcrumbResourceManager } from "@/shared/components/layout/breadcrumb-navigation/breadcrumb-resource-manager";
import { BreadcrumbRoleManagement } from "@/shared/components/layout/breadcrumb-navigation/breadcrumb-role-management";
import { BreadcrumbSchema } from "@/shared/components/layout/breadcrumb-navigation/breadcrumb-schema";
import { BreadcrumbTasks } from "@/shared/components/layout/breadcrumb-navigation/breadcrumb-tasks";

export default function BreadcrumbNavigation() {
  const { pathname } = useLocation();
  const { objectKind } = useParams();

  if (matchPath({ path: "/branches", end: false }, pathname)) {
    return <BreadcrumbBranches />;
  }

  if (matchPath({ path: "/ipam/namespaces", end: false }, pathname)) {
    return <BreadcrumbIpNamespaces />;
  }

  if (matchPath({ path: "/ipam", end: false }, pathname)) {
    return <BreadcrumbIpam />;
  }

  if (matchPath({ path: "/activities", end: false }, pathname)) {
    return <BreadcrumbActivities />;
  }

  if (matchPath({ path: "/profile" }, pathname)) {
    return <BreadcrumbProfile />;
  }

  if (matchPath({ path: "/proposed-changes", end: false }, pathname)) {
    return <BreadcrumbProposedChanges />;
  }

  if (matchPath({ path: "/tasks", end: false }, pathname)) {
    return <BreadcrumbTasks />;
  }

  if (matchPath({ path: "/graphql", end: false }, pathname)) {
    return <BreadcrumbGraphql />;
  }

  if (matchPath({ path: "/resource-manager", end: false }, pathname)) {
    return <BreadcrumbResourceManager />;
  }

  if (matchPath({ path: "/schema" }, pathname)) {
    return <BreadcrumbSchema />;
  }

  if (matchPath({ path: "/role-management", end: false }, pathname)) {
    return <BreadcrumbRoleManagement />;
  }

  if (matchPath({ path: "/objects/CoreArtifact", end: false }, pathname)) {
    return <BreadcrumbObjects />;
  }

  if (objectKind) {
    return <BreadcrumbObjects />;
  }

  return null;
}
