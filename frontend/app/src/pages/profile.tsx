import { useAuth } from "@/entities/authentication/useAuth";
import { UserProfilePage } from "@/entities/user-profile/user-profile";
import { constructPath } from "@/shared/api/rest/fetch";
import { Navigate } from "react-router-dom";

export function Component() {
  const auth = useAuth();

  if (!auth.isAuthenticated) {
    return <Navigate to={constructPath("/")} />;
  }

  return <UserProfilePage />;
}
