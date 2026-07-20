# {{PRODUCT_NAME}}

Neutral static-web scaffold for the authorized `{{PRODUCT_TYPE}}` reimplementation described by {{SOURCE_DESCRIPTION}}.

Requirements: a current Node.js/npm toolchain for the smoke test and Python 3 for the local allowlisted static server.

```text
npm test
npm start
```

The development server binds to `127.0.0.1:8000` and serves only the exact routes and regular non-symlink files declared by `serve_manifest.json`. It provides no directory listing, redirect, implicit index fallback, query handling, or undeclared-file access.
