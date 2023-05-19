const esModules = ["query-string", "decode-uri-component", "split-on-first", "filter-obj"];

const config = {
  verbose: true,
  collectCoverageFrom: ["src/**/*.js", "!**/node_modules/**"],
  coverageReporters: ["text-summary", "lcov", "cobertura"],
  testMatch: ["**/*.test.js"],
  transformIgnorePatterns: esModules.length ? [`/node_modules/(?!${esModules.join("|")})`] : [],
};

export default config;
