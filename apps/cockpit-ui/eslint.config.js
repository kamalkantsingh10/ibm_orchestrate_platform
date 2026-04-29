import js from '@eslint/js';
import globals from 'globals';
import reactPlugin from 'eslint-plugin-react';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import jsxA11y from 'eslint-plugin-jsx-a11y';
import tseslint from 'typescript-eslint';
import { defineConfig, globalIgnores } from 'eslint/config';

export default defineConfig([
  globalIgnores(['dist', 'node_modules', 'coverage']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactPlugin.configs.flat.recommended,
      reactPlugin.configs.flat['jsx-runtime'],
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
      jsxA11y.flatConfigs.recommended,
    ],
    languageOptions: {
      globals: { ...globals.browser, ...globals.node },
    },
    settings: {
      // Pin a literal version: eslint-plugin-react@7's `detect` path calls a
      // legacy ESLint context API that ESLint 10 removed. Hardcoding bypasses
      // detection entirely. Bump when react bumps.
      react: { version: '19.2.0' },
    },
  },
  {
    // TanStack Router route files export both a `Route` constant and the
    // component — the canonical pattern. Disable Fast Refresh's "components
    // only" rule here. HMR still works for the component body.
    files: ['src/routes/**/*.{ts,tsx}'],
    rules: {
      'react-refresh/only-export-components': 'off',
    },
  },
]);
