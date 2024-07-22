import { useAuth } from "@/hooks/useAuth";
import { UserProfilePage } from "@/screens/user-profile/user-profile";
import { Navigate } from "react-router-dom";

export function Component() {
  const auth = useAuth();

  if (!auth.isAuthenticated) {
    return <Navigate to={"/"} />;
  }

  return <UserProfilePage />;
}
