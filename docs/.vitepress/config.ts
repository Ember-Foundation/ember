import { defineConfig } from 'vitepress'

const SITE_URL = 'https://ember-foundation.github.io/ember/'
// OG image. SVG is supported by Google, Facebook, LinkedIn, Discord. Twitter/X
// still requires PNG for large summary cards — render docs/public/og-image.svg
// to docs/public/og-image.png and replace this URL if Twitter cards matter.
const OG_IMAGE = `${SITE_URL}og-image.svg`

export default defineConfig({
  title: 'Ember',
  titleTemplate: ':title — 112k RPS Python web framework',
  description: 'Ember is a fast, AI-first async HTTP framework for Python. 112,000 RPS single-thread at 25 MB RSS. Built on Cython, llhttp, and io_uring.',
  base: '/ember/',
  lang: 'en-US',
  cleanUrls: true,
  lastUpdated: true,

  sitemap: {
    hostname: SITE_URL,
  },

  head: [
    // Favicon
    ['link', { rel: 'icon', href: '/ember/favicon.ico' }],
    ['link', { rel: 'icon', type: 'image/svg+xml', href: '/ember/logo.svg' }],
    ['link', { rel: 'apple-touch-icon', href: '/ember/apple-touch-icon.png' }],

    // SEO
    ['meta', { name: 'theme-color', content: '#ff6b35' }],
    ['meta', { name: 'author', content: 'Ember Foundation' }],
    ['meta', { name: 'keywords', content: 'Python web framework, fast Python framework, async Python framework, Python LLM framework, Python AI API, FastAPI alternative, Cython HTTP, Python io_uring, Python SSE streaming, ember python, AI gateway python, high-performance python, llhttp python' }],
    ['meta', { name: 'robots', content: 'index, follow, max-image-preview:large' }],
    ['link', { rel: 'canonical', href: SITE_URL }],

    // Open Graph
    ['meta', { property: 'og:type',        content: 'website' }],
    ['meta', { property: 'og:locale',      content: 'en_US' }],
    ['meta', { property: 'og:site_name',   content: 'Ember' }],
    ['meta', { property: 'og:title',       content: 'Ember — 112k RPS Python web framework' }],
    ['meta', { property: 'og:description', content: 'AI-first async HTTP framework for Python. 6× faster than FastAPI, 4× faster than Express, in 25 MB RSS.' }],
    ['meta', { property: 'og:url',         content: SITE_URL }],
    ['meta', { property: 'og:image',       content: OG_IMAGE }],
    ['meta', { property: 'og:image:width', content: '1200' }],
    ['meta', { property: 'og:image:height', content: '630' }],
    ['meta', { property: 'og:image:alt',   content: 'Ember — 112k RPS Python web framework' }],

    // Twitter / X
    ['meta', { name: 'twitter:card',        content: 'summary_large_image' }],
    ['meta', { name: 'twitter:title',       content: 'Ember — 112k RPS Python web framework' }],
    ['meta', { name: 'twitter:description', content: 'AI-first async HTTP framework for Python. 112k RPS single-thread, 25 MB RSS, llhttp + Cython + io_uring.' }],
    ['meta', { name: 'twitter:image',       content: OG_IMAGE }],
    ['meta', { name: 'twitter:image:alt',   content: 'Ember — Python framework benchmarks' }],

    // JSON-LD: SoftwareApplication
    ['script', { type: 'application/ld+json' }, JSON.stringify({
      '@context': 'https://schema.org',
      '@type': 'SoftwareApplication',
      'name': 'Ember',
      'alternateName': 'ember-api',
      'applicationCategory': 'DeveloperApplication',
      'applicationSubCategory': 'Web Framework',
      'operatingSystem': 'Linux, macOS, Windows',
      'description': 'AI-first async HTTP framework for Python. 112k RPS single-thread at 25 MB RSS. Built on Cython, llhttp, and io_uring.',
      'url': SITE_URL,
      'downloadUrl': 'https://pypi.org/project/ember-api/',
      'softwareVersion': '0.2.1',
      'license': 'https://opensource.org/licenses/MIT',
      'programmingLanguage': 'Python',
      'offers': { '@type': 'Offer', 'price': '0', 'priceCurrency': 'USD' },
      'codeRepository': 'https://github.com/Ember-Foundation/ember',
      'author': { '@type': 'Organization', 'name': 'Ember Foundation' },
    })],
  ],

  themeConfig: {
    logo: { src: '/logo.svg', alt: 'Ember' },
    siteTitle: 'Ember',

    nav: [
      { text: 'Guide', link: '/guide/getting-started', activeMatch: '/guide/' },
      { text: 'Tutorial', link: '/tutorial/01-hello-world', activeMatch: '/tutorial/' },
      { text: 'API Reference', link: '/api/application', activeMatch: '/api/' },
      { text: 'Benchmarks', link: '/guide/performance#cross-framework-comparison' },
      { text: 'Roadmap', link: '/roadmap' },
      {
        text: 'Resources',
        items: [
          { text: 'GitHub', link: 'https://github.com/Ember-Foundation/ember' },
          { text: 'PyPI', link: 'https://pypi.org/project/ember-api/' },
          { text: 'Issues', link: 'https://github.com/Ember-Foundation/ember/issues' },
          { text: 'Releases', link: 'https://github.com/Ember-Foundation/ember/releases' },
        ],
      },
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

    editLink: {
      pattern: 'https://github.com/Ember-Foundation/ember/edit/master/docs/:path',
      text: 'Edit this page on GitHub',
    },

    footer: {
      message: 'Released under the MIT License.',
      copyright: `Copyright © 2026 Ember Foundation. <a href="https://github.com/Ember-Foundation/ember">Star on GitHub</a>`,
    },

    search: {
      provider: 'local',
      options: {
        detailedView: true,
        miniSearch: {
          searchOptions: {
            fuzzy: 0.2,
            prefix: true,
            boost: { title: 4, text: 2, titles: 1 },
          },
        },
      },
    },
  },
})
