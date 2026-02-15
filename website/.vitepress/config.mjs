import { defineConfig } from 'vitepress'
import { withMermaid } from 'vitepress-plugin-mermaid'

export default withMermaid(defineConfig({
  title: 'Cognition Engines',
  description: 'Decision Intelligence for AI Agents',
  base: '/',
  appearance: 'dark',

  head: [
    ['meta', { name: 'theme-color', content: '#6366f1' }],
    ['meta', { property: 'og:type', content: 'website' }],
    ['meta', { property: 'og:title', content: 'Cognition Engines' }],
    ['meta', { property: 'og:description', content: 'Decision Intelligence for AI Agents - Query, Check, Record, Learn' }],
  ],

  themeConfig: {
    logo: '/logo.png',
    siteTitle: 'Cognition Engines',

    nav: [
      { text: 'Guide', link: '/guide/what-is-cognition-engines' },
      { text: 'Reference', link: '/reference/product-overview' },
      { text: 'Specs', link: '/specs/' },
      {
        text: 'v0.10.0',
        items: [
          { text: 'Changelog', link: '/changelog' },
          { text: 'GitHub', link: 'https://github.com/tfatykhov/cognition-agent-decisions' }
        ]
      }
    ],

    sidebar: {
      '/guide/': [
        {
          text: 'Introduction',
          items: [
            { text: 'What is Cognition Engines?', link: '/guide/what-is-cognition-engines' },
            { text: 'Why Cognition Engines?', link: '/guide/why-cognition-engines' },
            { text: 'Getting Started', link: '/guide/getting-started' },
            { text: 'Golden Path Walkthrough', link: '/guide/golden-path' },
            { text: 'Agent Quick Start', link: '/guide/agent-quickstart' },
          ]
        },
        {
          text: 'Core Concepts',
          items: [
            { text: 'Decision Protocol', link: '/guide/decision-protocol' },
            { text: 'Deliberation Traces', link: '/guide/deliberation-traces' },
            { text: 'Bridge-Definitions', link: '/guide/bridge-definitions' },
            { text: 'Related Decisions', link: '/guide/related-decisions' },
            { text: 'Guardrails', link: '/guide/guardrails' },
          ]
        },
        {
          text: 'Integration',
          items: [
            { text: 'MCP Integration', link: '/guide/mcp-integration' },
            { text: 'Dashboard', link: '/guide/dashboard' },
          ]
        }
      ],
      '/reference/': [
        {
          text: 'Product Documentation',
          items: [
            { text: 'Product Overview', link: '/reference/product-overview' },
            { text: 'Architecture', link: '/reference/architecture' },
            { text: 'Module Reference', link: '/reference/modules' },
          ]
        },
        {
          text: 'API & CLI',
          items: [
            { text: 'API Reference', link: '/reference/api' },
            { text: 'CLI Reference', link: '/reference/cli' },
            { text: 'MCP Quick Start', link: '/reference/mcp-quickstart' },
          ]
        },
        {
          text: 'Setup',
          items: [
            { text: 'Installation', link: '/reference/installation' },
            { text: 'Configuration', link: '/reference/configuration' },
            { text: 'Dashboard Guide', link: '/reference/dashboard-guide' },
            { text: 'Guardrails Authoring', link: '/reference/guardrails-authoring' },
          ]
        }
      ],
      '/specs/': [
        {
          text: 'Feature Specs',
          items: [
            { text: 'Overview', link: '/specs/' },
            { text: 'F022 - MCP Server', link: '/specs/f022-mcp-server' },
            { text: 'F023 - Deliberation Traces', link: '/specs/f023-deliberation-traces' },
            { text: 'F024 - Bridge-Definitions', link: '/specs/f024-bridge-definitions' },
            { text: 'F027 - Censor Layer', link: '/specs/f027-censor-layer' },
            { text: 'F028 - Decomposed Confidence', link: '/specs/f028-decomposed-confidence' },
          ]
        }
      ]
    },

    socialLinks: [
      { icon: 'github', link: 'https://github.com/tfatykhov/cognition-agent-decisions' }
    ],

    search: {
      provider: 'local'
    },

    editLink: {
      pattern: 'https://github.com/tfatykhov/cognition-agent-decisions/edit/main/website/:path',
      text: 'Edit this page on GitHub'
    },

    footer: {
      message: 'Released under the Apache 2.0 License.',
      copyright: 'Built with Minsky\'s Society of Mind'
    }
  },

  mermaid: {
    theme: 'dark'
  }
}))
