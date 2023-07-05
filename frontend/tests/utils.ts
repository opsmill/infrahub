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
  username: "Chloe O'Brian",
  password: "Password123",
};

export const READ_ONLY_CREDENTIALS = {
  username: "Jack Bauer",
  password: "Password123",
};
