import { Card, CardContent } from "@infrahub/ui";

import ErrorScreen from "@/shared/components/errors/error-screen";
import UnauthorizedScreen from "@/shared/components/errors/unauthorized-screen";
import Content from "@/shared/components/layout/content";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";

import { useGetObjectPermissions } from "@/entities/permission/ui/queries/get-object-permissions.query";
import { PROPOSED_CHANGE_OBJECT } from "@/entities/proposed-changes/domain/model/proposed-change";
import { ProposedChangeCreateForm } from "@/entities/proposed-changes/ui/create-form";

function ProposedChangeCreatePage() {
  const { isPending, data: permission, error } = useGetObjectPermissions(PROPOSED_CHANGE_OBJECT);

  if (isPending) {
    return <LoadingIndicator className="h-full" message="checking permissions..." />;
  }

  if (error) {
    return <ErrorScreen message="Something went wrong when fetching the permissions." />;
  }

  if (!permission?.create?.isAllowed) {
    return <UnauthorizedScreen message={permission?.create.message} />;
  }

  return (
    <Content>
      <Card className="m-auto mt-0 max-w-2xl md:mt-4">
        <CardContent className="px-8 py-4">
          <h1 className="font-semibold text-foreground text-xl">Create a proposed change</h1>
          <p className="mb-6 text-foreground-muted text-xs">
            A proposed change lets you compare two branches, run tests, and finally merge one branch
            into another.
          </p>

          <ProposedChangeCreateForm />
        </CardContent>
      </Card>
    </Content>
  );
}

export const Component = ProposedChangeCreatePage;
