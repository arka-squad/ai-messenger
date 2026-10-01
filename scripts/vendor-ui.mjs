import { cpSync, mkdirSync } from "node:fs";

const target = new URL("../src/assets/vendor/", import.meta.url);

mkdirSync(target, { recursive: true });
cpSync(new URL("../node_modules/react/umd/react.production.min.js", import.meta.url), new URL("react.production.min.js", target));
cpSync(new URL("../node_modules/react-dom/umd/react-dom.production.min.js", import.meta.url), new URL("react-dom.production.min.js", target));
