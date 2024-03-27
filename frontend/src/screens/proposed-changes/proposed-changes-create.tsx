import { Navigate } from "react-router-dom";
import { usePermission } from "../../hooks/usePermission";
import { constructPath } from "../../utils/fetch";
import Content from "../layout/content";

export const ProposedChangesCreate = () => {
  const permission = usePermission();

  if (!permission.write.allow) {
    return <Navigate to={constructPath("/proposed-changes")} replace />;
  }

  return (
    <Content>
      <Content.Title title="New proposed change" />
      create
    </Content>
  );
};
