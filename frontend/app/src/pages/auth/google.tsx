import { useSearchParams } from "react-router-dom";
import { useEffect } from "react";
import { fetchUrl } from "@/utils/fetch";
import { CONFIG } from "@/config/config";

function AuthGoogle() {
  const [searchParams] = useSearchParams();
  const code = searchParams.get("code");
  const state = searchParams.get("state");

  useEffect(() => {
    if (!code) {
      return;
    }
    fetchUrl(CONFIG.GOOGLE_OAUTH2_TOKEN_URL + "?" + searchParams.toString()).then((r) => r.json());
  }, []);

  return null;
}

export const Component = AuthGoogle;
