import { Card } from "@/components/ui/card";
import { PROPOSED_CHANGES_OBJECT } from "@/config/constants";
import useQuery from "@/hooks/useQuery";
import ErrorScreen from "@/screens/errors/error-screen";
import UnauthorizedScreen from "@/screens/errors/unauthorized-screen";
import Content from "@/screens/layout/content";
import LoadingScreen from "@/screens/loading-screen/loading-screen";
import { getObjectPermissionsQuery } from "@/screens/permission/queries/getObjectPermissions";
import { getPermission } from "@/screens/permission/utils";
import { ProposedChangeCreateForm } from "@/screens/proposed-changes/create-form";
import { gql } from "@apollo/client";

function ProposedChangeCreatePage() {
  const { loading, data, error } = useQuery(
    gql(getObjectPermissionsQuery(PROPOSED_CHANGES_OBJECT))
  );

  const permission = getPermission(data?.[PROPOSED_CHANGES_OBJECT]?.permissions?.edges);

  if (loading) {
    return <LoadingScreen message="Loading permissions..." />;
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
      <Card className="p-4 px-8 max-w-2xl m-auto mt-0 md:mt-4">
        <h1 className="text-xl font-semibold text-gray-700">Create a proposed change</h1>
        <p className="text-xs text-gray-700 mb-6">
          A proposed change lets you compare two branches, run tests, and finally merge one branch
          into another.
        </p>

        <ProposedChangeCreateForm />
      </Card>
    </Content>
  );
}

export const Component = ProposedChangeCreatePage;
