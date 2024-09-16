import { CONFIG } from "@/config/config";

export function getLoginUrl(redirect?: string | null) {
  return redirect
    ? `${CONFIG.GOOGLE_OAUTH2_AUTHORIZE_URL}?redirect_uri=${encodeURIComponent(redirect)}`
    : CONFIG.GOOGLE_OAUTH2_AUTHORIZE_URL;
}
