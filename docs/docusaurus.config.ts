import { themes as prismThemes } from "prism-react-renderer";
import type { Config } from "@docusaurus/types";
import type * as Preset from "@docusaurus/preset-classic";
import globalVars from './globalVars'
import path from 'path';

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
  onDuplicateRoutes: "throw",

  // Structured data so search engines and LLM crawlers associate Infrahub with OpsMill.
  headTags: [
    {
      tagName: "script",
      attributes: { type: "application/ld+json" },
      innerHTML: JSON.stringify({
        "@context": "https://schema.org",
        "@type": "SoftwareApplication",
        name: "Infrahub",
        applicationCategory: "DeveloperApplication",
        operatingSystem: "Linux, Docker",
        url: "https://docs.infrahub.app/",
        description:
          "Infrahub is a graph-based infrastructure data management platform with built-in version control, CI workflows, and API access.",
        publisher: {
          "@type": "Organization",
          name: "OpsMill",
          url: "https://opsmill.com/",
          sameAs: [
            "https://opsmill.com/",
            "https://github.com/opsmill",
            "https://www.linkedin.com/company/opsmill",
            "https://x.com/opsmill",
          ],
        },
      }),
    },
  ],

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
          exclude: ["**/AGENTS.md", "tutorials/getting-started/**"],
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
  plugins: [
    [
      '@docusaurus/theme-mermaid',
      {
        mermaid: {
          theme: { light: 'neutral', dark: 'dark' },
        },
      },
    ],
  ],
  themeConfig: {
    announcementBar: {
      id: 'docs-restructure-2026',
      content: '📚 New docs structure: content is now grouped by capability, not split across Topics and Guides. <a href="/release-notes/infrahub/docs-restructure"><strong>See what changed →</strong></a>',
      isCloseable: true,
    },
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
        {
          href: "https://opsmill.com",
          label: "opsmill.com",
          position: "right",
        },
      ],
    },
    metadata: [
      { property: "og:site_name", content: "OpsMill" },
    ],
    footer: {
      links: [
        {
          title: "Docs",
          items: [
            { label: "Overview", to: "/overview" },
            { label: "Quick Start", to: "/overview/quickstart" },
            { label: "Key Concepts", to: "/overview/concepts" },
          ],
        },
        {
          title: "OpsMill",
          items: [
            { label: "About", href: "https://opsmill.com/about-us" },
            { label: "Solutions", href: "https://opsmill.com/solutions/" },
            { label: "Pricing", href: "https://opsmill.com/pricing/" },
            { label: "Blog", href: "https://opsmill.com/blog/" },
          ],
        },
        {
          title: "Community",
          items: [
            { label: "GitHub", href: "https://github.com/opsmill/infrahub" },
            { label: "Discord", href: "https://discord.gg/opsmill" },
            { label: "Book a meeting", href: "https://cal.com/team/opsmill/meet" },
          ],
        },
      ],
      copyright: `Copyright © ${new Date().getFullYear()} - <b>Infrahub</b> by <a href="https://opsmill.com">OpsMill</a>.`,
    },
    prism: {
      theme: prismThemes.oneDark,
      additionalLanguages: ["bash", "python", "markup-templating", "django", "json", "toml", "yaml", "hcl"],
    },
  } satisfies Preset.ThemeConfig,

  markdown: {
    format: "mdx",
    mermaid: true,
    hooks: {
      onBrokenMarkdownLinks: "throw",
    },
    preprocessor: ({ filePath, fileContent }) => {
      console.log(`Processing ${filePath}`);
      const transformedContent = fileContent.replace(/\$\(\s*(\w+)\s*\)/g, (match, variableName) => {
        if (variableName === 'base_url' && globalVars.base_url === 'RELATIVE') {
          return getDocsRelative(filePath);
        }
        return globalVars[variableName] || match;
      });
      return transformedContent;
    },
  },
};

function getDocsRelative(filePath) {
  const rootDocsDir = path.join(process.cwd(), 'docs');
  const currentDir = path.dirname(filePath);
  const nestedDocsDir = path.join(rootDocsDir, 'docs');
  const relativePath = path.relative(currentDir, nestedDocsDir);
  const segments = relativePath.split(path.sep);
  return '../'.repeat(segments.length - 1);
}

export default config;
