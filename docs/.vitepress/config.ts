import { defineConfig } from 'vitepress'

export default defineConfig({
  title: 'Ember',
  description: 'AI-API-first async HTTP framework for Python',
  base: '/ember/',

  head: [
    ['link', { rel: 'icon', href: '/ember/favicon.ico' }],
  ],

  themeConfig: {
    logo: { src: '/logo.svg', alt: 'Ember' },
    siteTitle: '🔥 Ember',

    nav: [
      { text: 'Guide', link: '/guide/getting-started' },
      { text: 'Tutorial', link: '/tutorial/01-hello-world' },
      { text: 'API Reference', link: '/api/application' },
      { text: 'Roadmap', link: '/roadmap' },
      { text: 'GitHub', link: 'https://github.com/Ember-Foundation/ember' },
    ],

    sidebar: {
      '/guide/': [
        {
          text: 'Setup',
          items: [
            { text: 'Getting Started', link: '/guide/getting-started' },
            { text: 'CLI Reference', link: '/guide/cli' },
          ],
        },
        {
          text: 'Concepts',
          items: [
            { text: 'Core Concepts', link: '/guide/concepts' },
            { text: 'Project Structure', link: '/guide/structure' },
          ],
        },
        {
          text: 'Production',
          items: [
            { text: 'Performance Guide', link: '/guide/performance' },
            { text: 'Deployment', link: '/guide/deployment' },
          ],
        },
      ],

      '/tutorial/': [
        {
          text: 'Tutorial',
          items: [
            { text: '1 — Hello World', link: '/tutorial/01-hello-world' },
            { text: '2 — Routing & Path Params', link: '/tutorial/02-routing' },
            { text: '3 — Request & Response', link: '/tutorial/03-request-response' },
            { text: '4 — Middleware & Hooks', link: '/tutorial/04-middleware' },
            { text: '5 — Blueprints', link: '/tutorial/05-blueprints' },
            { text: '6 — Caching', link: '/tutorial/06-caching' },
            { text: '7 — AI Routes & Streaming', link: '/tutorial/07-ai-routes' },
          ],
        },
      ],

      '/api/': [
        {
          text: 'Core',
          items: [
            { text: 'Application & Blueprint', link: '/api/application' },
            { text: 'Routing', link: '/api/routing' },
            { text: 'Request & Response', link: '/api/request-response' },
          ],
        },
        {
          text: 'Middleware & Security',
          items: [
            { text: 'Middleware', link: '/api/middleware' },
          ],
        },
        {
          text: 'Caching',
          items: [
            { text: 'StaticCache / RedisCache / MemcachedCache', link: '/api/caching' },
          ],
        },
        {
          text: 'AI & Streaming',
          items: [
            { text: 'AI Primitives', link: '/api/ai' },
            { text: 'Server-Sent Events', link: '/api/sse' },
          ],
        },
      ],
    },

    socialLinks: [
      { icon: 'github', link: 'https://github.com/Ember-Foundation/ember' },
    ],

    footer: {
      message: 'Released under the MIT License.',
      copyright: 'Copyright © 2026 Mohammad Ismail',
    },

    search: {
      provider: 'local',
    },
  },
})
