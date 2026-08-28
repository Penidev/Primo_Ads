import nextCoreWebVitals from "eslint-config-next/core-web-vitals";

/**
 * ESLint flat config.
 *
 * `eslint-config-next` 16 ships a native flat config array from
 * `./core-web-vitals`, so it is spread directly. Do not wrap it in
 * `FlatCompat` — the plugin objects are self-referential and the legacy
 * validator throws "Converting circular structure to JSON" on them.
 *
 * Note that `next lint` was removed in Next 16 and `next build` no longer lints,
 * so linting only runs when ESLint is invoked directly. The `lint` script and
 * the CI step are now the only things standing between a lint error and main.
 */
const config = [
  {
    ignores: [
      ".next/**",
      "node_modules/**",
      "next-env.d.ts",
      "coverage/**",
      "public/**",
    ],
  },
  ...nextCoreWebVitals,
];

export default config;
