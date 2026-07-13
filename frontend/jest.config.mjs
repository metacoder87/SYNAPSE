import nextJest from "next/jest.js";

const createJestConfig = nextJest({ dir: "./" });

/** @type {import('jest').Config} */
const config = {
  testEnvironment: "jsdom",
  setupFilesAfterEnv: ["<rootDir>/jest.setup.ts"],
  moduleNameMapper: { "^@/(.*)$": "<rootDir>/src/$1" },
};

// react-markdown v9 and the unified/remark ecosystem are ESM-only; next/jest
// excludes node_modules from transformation by default, so carve them back in.
const ESM_PACKAGES = [
  "react-markdown",
  "remark-.*",
  "rehype-.*",
  "micromark.*",
  "mdast-.*",
  "unist-.*",
  "unified",
  "bail",
  "is-plain-obj",
  "trough",
  "vfile.*",
  "hast-.*",
  "property-information",
  "html-url-attributes",
  "space-separated-tokens",
  "comma-separated-tokens",
  "ccount",
  "escape-string-regexp",
  "markdown-table",
  "zwitch",
  "longest-streak",
  "decode-named-character-reference",
  "character-entities.*",
  "character-reference-invalid",
  "is-alphanumerical",
  "is-alphabetical",
  "is-decimal",
  "is-hexadecimal",
  "trim-lines",
  "devlop",
  "estree-util-is-identifier-name",
  "html-void-elements",
  "web-namespaces",
  "stringify-entities",
];

export default async () => {
  const jestConfig = await createJestConfig(config)();
  jestConfig.transformIgnorePatterns = [
    `/node_modules/(?!(${ESM_PACKAGES.join("|")})/)`,
    "^.+\\.module\\.(css|sass|scss)$",
  ];
  return jestConfig;
};
