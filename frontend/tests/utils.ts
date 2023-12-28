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
  ADMIN: "e2e/.auth/admin.json",
};

export const waitFor = (alias, checkFn, maxRequests = 10, level = 0) => {
  if (level === maxRequests) {
    throw `${maxRequests} requests exceeded`;
  }

  return cy.wait(alias, { timeout: 10000 }).then((interception) => {
    if (!checkFn(interception)) {
      return waitFor(alias, checkFn, maxRequests, level + 1);
    }
  });
};
