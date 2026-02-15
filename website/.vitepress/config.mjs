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
        text: 'v0.12.0',
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
        { text: 'Overview', link: '/specs/' },
        {
          text: 'v0.8.0 (F001–F011)',
          collapsed: true,
          items: [
            { text: 'F001 - CSTP Server', link: '/specs/f001-cstp-server' },
            { text: 'F002 - Query Decisions', link: '/specs/f002-query-decisions' },
            { text: 'F003 - Check Guardrails', link: '/specs/f003-check-guardrails' },
            { text: 'F004 - Announce Intent', link: '/specs/f004-announce-intent' },
            { text: 'F005 - CSTP Client', link: '/specs/f005-cstp-client' },
            { text: 'F006 - Docker Deployment', link: '/specs/f006-docker-deployment' },
            { text: 'F007 - Record Decision', link: '/specs/f007-record-decision' },
            { text: 'F008 - Review Decision', link: '/specs/f008-review-decision' },
            { text: 'F009 - Get Calibration', link: '/specs/f009-get-calibration' },
            { text: 'F010 - Project Context', link: '/specs/f010-project-context' },
            { text: 'F011 - Web Dashboard', link: '/specs/f011-web-dashboard' },
          ]
        },
        {
          text: 'v0.9.0 (F019)',
          collapsed: true,
          items: [
            { text: 'F019 - List Guardrails', link: '/specs/f019-list-guardrails' },
          ]
        },
        {
          text: 'v0.10.0 (F022–F027)',
          collapsed: true,
          items: [
            { text: 'F022 - MCP Server', link: '/specs/f022-mcp-server' },
            { text: 'F023 - Deliberation Traces', link: '/specs/f023-deliberation-traces' },
            { text: 'F024 - Bridge-Definitions', link: '/specs/f024-bridge-definitions' },
            { text: 'F027 - Decision Quality', link: '/specs/f027-decision-quality' },
          ]
        },
        {
          text: 'v0.11.0 (F046–F047)',
          items: [
            { text: 'F046 - Pre-Action Hook', link: '/specs/f046-pre-action-hook' },
            { text: 'F047 - Session Context', link: '/specs/f047-session-context' },
          ]
        },
        {
          text: 'Roadmap: Research',
          collapsed: true,
          items: [
            { text: 'F020 - Reasoning Traces', link: '/specs/f020-reasoning-traces' },
            { text: 'F029 - Task Router', link: '/specs/f029-task-router' },
            { text: 'F030 - Circuit Breaker Guardrails', link: '/specs/f030-circuit-breaker-guardrails' },
            { text: 'F031 - Source Trust Scoring', link: '/specs/f031-source-trust-scoring' },
            { text: 'F032 - Error Amplification', link: '/specs/f032-error-amplification-tracking' },
          ]
        },
        {
          text: 'Roadmap: Minsky',
          collapsed: true,
          items: [
            { text: 'F033 - Censor Layer', link: '/specs/f033-censor-layer' },
            { text: 'F034 - Decomposed Confidence', link: '/specs/f034-decomposed-confidence' },
          ]
        },
        {
          text: 'Roadmap: Federation',
          collapsed: true,
          items: [
            { text: 'F035 - Semantic State Transfer', link: '/specs/f035-semantic-state-transfer' },
            { text: 'F036 - Reasoning Continuity', link: '/specs/f036-reasoning-continuity' },
            { text: 'F037 - Collective Innovation', link: '/specs/f037-collective-innovation' },
            { text: 'F038 - Cross-Agent Federation', link: '/specs/f038-cross-agent-federation' },
            { text: 'F039 - Protocol Stack', link: '/specs/f039-protocol-stack' },
          ]
        },
        {
          text: 'Roadmap: Beads-Inspired',
          collapsed: true,
          items: [
            { text: 'F040 - Task-Decision Graph', link: '/specs/f040-task-decision-graph' },
            { text: 'F041 - Memory Compaction', link: '/specs/f041-memory-compaction' },
            { text: 'F042 - Decision Dependencies', link: '/specs/f042-decision-dependencies' },
            { text: 'F043 - Distributed Merge', link: '/specs/f043-distributed-merge' },
            { text: 'F044 - Agent Work Discovery', link: '/specs/f044-agent-work-discovery' },
            { text: 'F045 - Graph Storage Layer', link: '/specs/f045-graph-storage-layer' },
          ]
        },
        {
          text: 'Roadmap: Infrastructure',
          collapsed: true,
          items: [
            { text: 'F048 - Multi-Vector-DB', link: '/specs/f048-multi-vectordb' },
          ]
        },
      ]
    },

    socialLinks: [
      { icon: 'github', link: 'https://github.com/tfatykhov/cognition-agent-decisions' }
    ],

    search: {
      provider: 'local'
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
