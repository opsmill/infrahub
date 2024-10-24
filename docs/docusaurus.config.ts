import { themes as prismThemes } from "prism-react-renderer";
import type { Config } from "@docusaurus/types";
import type * as Preset from "@docusaurus/preset-classic";

const config: Config = {
  title: "Infrahub Documentation",
  tagline: "Explore our guides and examples to use Infrahub.",
  favicon: "img/favicon.ico",
  scripts: process.env.ANALYTICS ? [
    {
      src: 'https://plausible.io/js/script.js',
      defer: true,
      'data-domain': 'docs.infrahub.app'
    }, {
      src: '/js/custom-reo.js'
    }
  ] : [],

  // Set the production url of your site here
  url: process.env.DOCS_IN_APP ? "http://localhost:8000" : "https://docs.infrahub.app",
  // Set the /<baseUrl>/ pathname under which your site is served
  // For GitHub pages deployment, it is often '/<projectName>/'
  baseUrl: process.env.DOCS_IN_APP ? "/docs/" : "/",

  // GitHub pages deployment config.
  // If you aren't using GitHub pages, you don't need these.
  organizationName: "opsmill", // Usually your GitHub org/user name.
  projectName: "infrahub", // Usually your repo name.

  onBrokenLinks: "throw",
  onBrokenAnchors: "throw",
  onBrokenMarkdownLinks: "throw",
  onDuplicateRoutes: "throw",

  // Even if you don't use internationalization, you can use this field to set
  // useful metadata like html lang. For example, if your site is Chinese, you
  // may want to replace "en" with "zh-Hans".
  i18n: {
    defaultLocale: "en",
    locales: ["en"],
  },

  presets: [
    [
      "classic",
      {
        docs: {
          // Please change this to your repo.
          // Remove this to remove the "edit this page" links.
          editUrl: "https://github.com/opsmill/infrahub/tree/stable/docs",
          routeBasePath: "/",
          sidebarCollapsed: true,
          sidebarPath: "./sidebars.ts",
        },
        blog: false,
        theme: {
          customCss: "./src/css/custom.css",
        },
      } satisfies Preset.Options,
    ],
  ],
  themes: [
    [
      "@easyops-cn/docusaurus-search-local",
      {
        indexBlog: false,
        indexDocs: true,
        docsRouteBasePath: "/", // this needs to be the same as routeBasePath
        hashed: true,
      }
    ],
  ],
  themeConfig: {
    // announcementBar: {
    //   content: 'Welcome to our brand new docs!',
    //   isCloseable: true,
    // },
    navbar: {
      logo: {
        alt: "Infrahub",
        src: "img/infrahub-hori.svg",
        srcDark: "img/infrahub-hori-dark.svg",
      },
      items: [
        {
          type: "docSidebar",
          sidebarId: "docsSidebar",
          position: "left",
          label: "Documentation",
        },
        {
          type: "search",
          position: "right",
        },
        {
          href: "https://github.com/opsmill/infrahub",
          position: "right",
          className: "header-github-link",
          "aria-label": "GitHub repository",
        },
      ],
    },
    footer: {
      copyright: `Copyright © ${new Date().getFullYear()} - <b>Infrahub</b> by OpsMill.`,
    },
    prism: {
      theme: prismThemes.oneDark,
      additionalLanguages: ["bash", "python", "markup-templating", "django", "json", "toml", "yaml"],
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
