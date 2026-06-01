// Statyczny sitemap dla publicznych stron portalu.
// Strony prywatne (dashboard, mecze, profil) celowo pominięte.
// /login i /register pominięte — mają noindex, nie powinny być w sitemapie.
export const prerender = true;

const SITE = import.meta.env.PUBLIC_SITE_URL ?? 'https://portal.raketon.pl';

const pages = [
  { path: '/',                        lastmod: '2026-05-31', priority: '1.0', changefreq: 'weekly'  },
  { path: '/dla-klubow',              lastmod: '2026-05-31', priority: '0.9', changefreq: 'monthly' },
  { path: '/rezerwacje-kortow',       lastmod: '2026-05-31', priority: '0.9', changefreq: 'monthly' },
  { path: '/turnieje-ligi-rankingi',  lastmod: '2026-05-31', priority: '0.9', changefreq: 'monthly' },
  { path: '/cennik',                  lastmod: '2026-05-31', priority: '0.8', changefreq: 'monthly' },
  { path: '/kontakt',                 lastmod: '2026-05-31', priority: '0.7', changefreq: 'monthly' },
  { path: '/polityka-prywatnosci',    lastmod: '2026-05-31', priority: '0.3', changefreq: 'yearly'  },
  { path: '/regulamin',               lastmod: '2026-05-31', priority: '0.3', changefreq: 'yearly'  },
];

const xml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${pages
  .map(
    (p) => `  <url>
    <loc>${SITE}${p.path}</loc>
    <lastmod>${p.lastmod}</lastmod>
    <changefreq>${p.changefreq}</changefreq>
    <priority>${p.priority}</priority>
  </url>`,
  )
  .join('\n')}
</urlset>`;

export function GET() {
  return new Response(xml, {
    headers: {
      'Content-Type': 'application/xml; charset=utf-8',
      'Cache-Control': 'public, max-age=86400',
    },
  });
}
