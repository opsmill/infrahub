import { gql, useQuery } from "@apollo/client";

import ErrorScreen from "@/shared/components/errors/error-screen";
import UnauthorizedScreen from "@/shared/components/errors/unauthorized-screen";
import Content from "@/shared/components/layout/content";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { Card } from "@/shared/components/ui/card";
import { PROPOSED_CHANGES_OBJECT } from "@/shared/config/constants";

import { getObjectPermissionsQuery } from "@/entities/permission/queries/getObjectPermissions";
import { getPermission } from "@/entities/permission/utils";
import { ProposedChangeCreateForm } from "@/entities/proposed-changes/ui/create-form";

function ProposedChangeCreatePage() {
  const { loading, data, error } = useQuery(
    gql(getObjectPermissionsQuery(PROPOSED_CHANGES_OBJECT))
  );

  const permission = getPermission(data?.[PROPOSED_CHANGES_OBJECT]?.permissions?.edges);

  if (loading) {
    return <LoadingIndicator className="h-full" message="checking permissions..." />;
  }

  if (error) {
    if (error.networkError?.statusCode === 403) {
      const { message } = error.networkError?.result?.errors?.[0] ?? {};

      return <UnauthorizedScreen message={message} />;
    }

    return <ErrorScreen message="Something went wrong when fetching the permissions." />;
  }

  if (!permission?.create?.isAllowed) {
    return <UnauthorizedScreen message={permission.create.message} />;
  }

  return (
    <Content>
      <Card className="m-auto mt-0 max-w-2xl p-4 px-8 md:mt-4">
        <h1 className="font-semibold text-gray-700 text-xl">Create a proposed change</h1>
        <p className="mb-6 text-gray-700 text-xs">
          A proposed change lets you compare two branches, run tests, and finally merge one branch
          into another.
        </p>

        <ProposedChangeCreateForm />
      </Card>
    </Content>
  );
}

export const Component = ProposedChangeCreatePage;
