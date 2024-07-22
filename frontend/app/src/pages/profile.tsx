import { useAuth } from "@/hooks/useAuth";
import { UserProfilePage } from "@/screens/user-profile/user-profile";
import { useNavigate } from "react-router-dom";

export function Component() {
  const navigate = useNavigate();

  const auth = useAuth();

  if (!auth.isAuthenticated) {
    navigate("/");
    return;
  }

  return <UserProfilePage />;
}
