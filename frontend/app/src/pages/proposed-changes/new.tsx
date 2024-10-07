import { Card } from "@/components/ui/card";
import { usePermission } from "@/hooks/usePermission";
import Content from "@/screens/layout/content";
import { ProposedChangeCreateForm } from "@/screens/proposed-changes/create-form";
import { constructPath } from "@/utils/fetch";
import { Navigate } from "react-router-dom";

function ProposedChangeCreatePage() {
  const permission = usePermission();

  if (!permission.write.allow) {
    return <Navigate to={constructPath("/proposed-changes")} replace />;
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
