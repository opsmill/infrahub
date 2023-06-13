type ScreenshotConfig = {
  overwrite: boolean;
  scale: boolean;
};

export const screenshotConfig: ScreenshotConfig = {
  overwrite: true,
  scale: true,
};

export const SCREENSHOT_ENV_VARIABLE = "SCREENSHOTS";
