/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{astro,html,js,ts,jsx,tsx}'],
  darkMode: ['attribute', '[data-theme="dark"]'],
  theme: {
    extend: {
      // Mapowanie tokenów z tokens.css do Tailwind
      // Używamy CSS custom properties — Tailwind odczytuje je przez var()
      colors: {
        // Tło
        bg: 'var(--bg)',
        'bg-secondary': 'var(--bg-secondary)',
        surface: 'var(--surface)',
        'surface-2': 'var(--surface-2)',
        'surface-hover': 'var(--surface-hover)',

        // Ramki
        border: 'var(--border)',
        'border-light': 'var(--border-light)',

        // Tekst
        text: 'var(--text)',
        'text-muted': 'var(--text-muted)',
        'text-dim': 'var(--text-dim)',

        // Akcenty
        primary: 'var(--primary)',
        'primary-dark': 'var(--primary-dark)',
        'primary-subtle': 'var(--primary-subtle)',

        // Statusy
        success: 'var(--success)',
        warning: 'var(--warning)',
        danger: 'var(--danger)',
        info: 'var(--info)',
      },
      spacing: {
        sidebar: 'var(--sidebar-width)',   // 260px
        topbar: 'var(--topbar-height)',    // 64px
      },
      borderRadius: {
        xs: 'var(--radius-xs)',   // 6px
        sm: 'var(--radius-sm)',   // 10px
        md: 'var(--radius-md)',   // 14px
        lg: 'var(--radius-lg)',   // 20px
        xl: 'var(--radius-xl)',   // 28px
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      boxShadow: {
        sm: 'var(--shadow-sm)',
        md: 'var(--shadow-md)',
        lg: 'var(--shadow-lg)',
      },
      maxWidth: {
        content: 'var(--content-max)', // 1400px
      },
    },
  },
  plugins: [],
};
