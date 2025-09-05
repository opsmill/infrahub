import { Navigate } from "react-router";

import { constructPath } from "@/shared/api/rest/fetch";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import { UserProfilePage } from "@/entities/user-profile/ui/user-profile";

export function Component() {
  const auth = useAuth();

  if (!auth.isAuthenticated) {
    return <Navigate to={constructPath("/")} />;
  }

  return <UserProfilePage />;
}
