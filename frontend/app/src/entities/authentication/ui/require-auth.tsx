import type React from "react";
import { Navigate, useLocation } from "react-router";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import { useConfig } from "@/entities/config/ui/config-provider";

export function RequireAuth({ children }: { children: React.ReactNode }) {
  const config = useConfig();
  const { isAuthenticated } = useAuth();
  const location = useLocation();

  if (isAuthenticated || config.main.allow_anonymous_access) return children;

  // Redirect them to the /login page, but save the current location they were
  // trying to go to when they were redirected. This allows us to send them
  // along to that page after they log in, which is a nicer user experience
  // than dropping them off on the home page.
  return <Navigate to="/login" state={{ from: location }} replace />;
}
