import { Navigate, useSearchParams } from "react-router-dom";
import { useEffect } from "react";
import { useAuth } from "@/hooks/useAuth";

function AuthGoogle() {
  const [searchParams] = useSearchParams();
  const { isAuthenticated, signInWithGoogle } = useAuth();

  useEffect(() => {
    const code = searchParams.get("code");
    const state = searchParams.get("state");
    const error = searchParams.get("error");

    if (error) {
      console.error("Google OAuth Error:", error);
      return;
    }

    if (!code) {
      console.error("No authorization code found.");
      return;
    }

    if (!state) {
      console.error("No authorization state found.");
      return;
    }

    signInWithGoogle({ code, state });
  }, []);

  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  return null;
}

export const Component = AuthGoogle;
