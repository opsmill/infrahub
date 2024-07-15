type ScreenshotConfig = {
  overwrite: boolean;
  scale: boolean;
};

export const screenshotConfig: ScreenshotConfig = {
  overwrite: true,
  scale: true,
};

export const SCREENSHOT_ENV_VARIABLE = "SCREENSHOTS";

export const ADMIN_CREDENTIALS = {
  username: "admin",
  password: "infrahub",
};

export const READ_WRITE_CREDENTIALS = {
  username: "Chloe O'Brian",
  password: "Password123",
};

export const READ_ONLY_CREDENTIALS = {
  username: "Jack Bauer",
  password: "Password123",
};

export const ENG_TEAM_ONLY_CREDENTIALS = {
  username: "Engineering Team",
  password: "Password123",
};

export const ACCOUNT_STATE_PATH = {
  ADMIN: "tests/e2e/.auth/admin.json",
  READ_WRITE: "tests/e2e/.auth/read-write.json",
  READ_ONLY: "tests/e2e/.auth/read-only.json",
};
