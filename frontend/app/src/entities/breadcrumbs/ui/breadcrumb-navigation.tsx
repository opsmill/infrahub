import { matchPath, useLocation } from "react-router";

import { BreadcrumbAccountProfile } from "@/entities/breadcrumbs/ui/breadcrumb-account-profile";
import { BreadcrumbActivities } from "@/entities/breadcrumbs/ui/breadcrumb-activities";
import { BreadcrumbBranches } from "@/entities/breadcrumbs/ui/breadcrumb-branches";
import { BreadcrumbGraphql } from "@/entities/breadcrumbs/ui/breadcrumb-graphql";
import { BreadcrumbIpNamespaces } from "@/entities/breadcrumbs/ui/breadcrumb-ip-namespaces";
import { BreadcrumbIpam } from "@/entities/breadcrumbs/ui/breadcrumb-ipam";
import { BreadcrumbObjects } from "@/entities/breadcrumbs/ui/breadcrumb-objects";
import { BreadcrumbProposedChanges } from "@/entities/breadcrumbs/ui/breadcrumb-proposed-changes";
import { BreadcrumbResourceManager } from "@/entities/breadcrumbs/ui/breadcrumb-resource-manager";
import { BreadcrumbRoleManagement } from "@/entities/breadcrumbs/ui/breadcrumb-role-management";
import { BreadcrumbSchemaViewer } from "@/entities/breadcrumbs/ui/breadcrumb-schema-viewer";
import { BreadcrumbTasks } from "@/entities/breadcrumbs/ui/breadcrumb-tasks";

export default function BreadcrumbNavigation() {
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
