// Statyczny sitemap dla publicznych stron portalu.
// Strony prywatne (dashboard, mecze, profil) celowo pominięte.
export const prerender = true;

const SITE = import.meta.env.PUBLIC_SITE_URL ?? 'https://portal.raketon.pl';

const pages = [
  { path: '/',                        priority: '1.0', changefreq: 'weekly'  },
  { path: '/dla-klubow',              priority: '0.9', changefreq: 'monthly' },
  { path: '/rezerwacje-kortow',       priority: '0.9', changefreq: 'monthly' },
  { path: '/turnieje-ligi-rankingi',  priority: '0.9', changefreq: 'monthly' },
  { path: '/cennik',                  priority: '0.8', changefreq: 'monthly' },
  { path: '/kontakt',                 priority: '0.7', changefreq: 'monthly' },
  { path: '/login',                   priority: '0.5', changefreq: 'yearly'  },
  { path: '/register',                priority: '0.6', changefreq: 'yearly'  },
];

const today = new Date().toISOString().split('T')[0];

const xml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${pages
  .map(
    (p) => `  <url>
    <loc>${SITE}${p.path}</loc>
    <lastmod>${today}</lastmod>
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
