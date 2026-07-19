# Website playbook

Use this playbook when the primary contract is a public informational, documentation, editorial, portfolio, commerce-catalog, or marketing experience. Add the web-app/SaaS playbook when authenticated stateful workflows are in scope.

## Capture evidence

- Freeze the reference date, browser/version, viewport width and height, device scale, color scheme, locale, reduced-motion setting, consent state, and authentication state.
- Inventory every in-scope route, redirect, canonical URL, navigation edge, external link, form, download, and error route.
- Capture full-page and component-level screenshots for default, hover, focus, active, expanded, validation, submitted, loading, empty, and error states that exist.
- Record semantic structure: landmarks, heading hierarchy, link/control names, tab order, form labels, live regions, image alternatives, and keyboard behavior.
- Record content hierarchy and field meaning. Reuse text, images, fonts, icons, logos, and trade dress only when rights are documented; otherwise specify replacements with matching structural role.
- Record responsive changes at actual transition widths. Do not infer standard breakpoints.
- Record metadata and delivery behavior when in scope: title, description, canonical, robots, social cards, structured data, status codes, caching, redirects, and asset failures.

## Specify the clone

- Map each route to its layout, sections, components, content source, interactions, metadata, and failure behavior.
- Define design tokens with exact units: typeface fallback chain, sizes, weights, line heights, colors, spacing, borders, radii, shadows, container widths, and motion durations/easing.
- Define layout behavior at named viewport intervals, including overflow, truncation, wrapping, stacking, crop/focal behavior, and navigation changes.
- Define every form's input schema, validation timing, messages, submission transport, duplicate behavior, success state, failure state, privacy behavior, and persistence.
- Define browser support, accessibility level, performance budget, asset policy, rendering strategy, analytics/consent boundary, and hosting path.
- State the visual oracle and tolerance. Name screenshot states, viewports, ignored dynamic regions, diff method, and numeric threshold.

## Minimum MVP

Include every route and interaction required for one complete primary visitor journey. Supply working navigation and forms within that journey. Do not call a set of disconnected screenshots or dead controls an MVP.

## Verify

| Contract | Required proof |
| --- | --- |
| Routes and links | Automated route/link crawl plus explicit redirect and 404 assertions |
| Responsive behavior | Screenshots and interaction checks at every named viewport and transition boundary |
| Visual fidelity | Independent reference-versus-clone image comparison using the frozen states and tolerance |
| Interaction | Keyboard and pointer tests for controls, menus, dialogs, forms, and focus restoration |
| Accessibility | Automated checks plus named manual keyboard/assistive-technology scenarios |
| Content/metadata | Assertions for required headings, labels, title, canonical, structured data, and status |
| Failure behavior | Missing assets, invalid form input, submission failure, slow load, and offline behavior when applicable |
| Performance | Recorded tool, environment, run count, percentile/statistic, and fixed budget |

Never generate expected screenshots from the clone itself. Preserve reference captures as the independent oracle.

