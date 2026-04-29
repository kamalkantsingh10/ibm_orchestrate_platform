// Tailwind 4 canonical install path: @tailwindcss/postcss replaces the legacy
// `tailwindcss` PostCSS plugin. ADR pointer to be added in Story 1.4.
export default {
  plugins: {
    '@tailwindcss/postcss': {},
    autoprefixer: {},
  },
};
