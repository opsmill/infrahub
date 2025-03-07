import { useAuth } from "@/entities/authentication/ui/useAuth";
import { UserProfilePage } from "@/entities/user-profile/ui/user-profile";
import { constructPath } from "@/shared/api/rest/fetch";
import { Navigate } from "react-router";

export function Component() {
  const auth = useAuth();

  if (!auth.isAuthenticated) {
    return <Navigate to={constructPath("/")} />;
  }

  return <UserProfilePage />;
}
