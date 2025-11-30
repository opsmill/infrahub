import { matchPath, useLocation } from "react-router";

import { BreadcrumbAccountProfile } from "@/entities/navigation/ui/breadcrumbs/breadcrumb-account-profile";
import { BreadcrumbActivities } from "@/entities/navigation/ui/breadcrumbs/breadcrumb-activities";
import { BreadcrumbBranches } from "@/entities/navigation/ui/breadcrumbs/breadcrumb-branches";
import { BreadcrumbGraphql } from "@/entities/navigation/ui/breadcrumbs/breadcrumb-graphql";
import { BreadcrumbIpNamespaces } from "@/entities/navigation/ui/breadcrumbs/breadcrumb-ip-namespaces";
import { BreadcrumbIpam } from "@/entities/navigation/ui/breadcrumbs/breadcrumb-ipam";
import { BreadcrumbObjects } from "@/entities/navigation/ui/breadcrumbs/breadcrumb-objects";
import { BreadcrumbProposedChanges } from "@/entities/navigation/ui/breadcrumbs/breadcrumb-proposed-changes";
import { BreadcrumbResourceManager } from "@/entities/navigation/ui/breadcrumbs/breadcrumb-resource-manager";
import { BreadcrumbRoleManagement } from "@/entities/navigation/ui/breadcrumbs/breadcrumb-role-management";
import { BreadcrumbSchemaViewer } from "@/entities/navigation/ui/breadcrumbs/breadcrumb-schema-viewer";
import { BreadcrumbTasks } from "@/entities/navigation/ui/breadcrumbs/breadcrumb-tasks";

export function BreadcrumbNavigation() {
  const { pathname } = useLocation();

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
    return <BreadcrumbAccountProfile />;
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
    return <BreadcrumbSchemaViewer />;
  }

  if (matchPath({ path: "/role-management", end: false }, pathname)) {
    return <BreadcrumbRoleManagement />;
  }

  return <BreadcrumbObjects />;
}
