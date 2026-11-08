# ADR 0006: Vanilla front end with no framework and no build step

- Status: Accepted
- Date: 2026-10-31

## Context

Tunza's users include community health workers on low-end Android phones and intermittent
connections. The front end must stay small, fast, auditable and maintainable for a long
handover period. A framework and toolchain add supply-chain and upgrade risk without solving
a measured product problem.

## Decision

- Use HTML, CSS and JavaScript, with no runtime framework and no production build step.
- Use ES modules, `tz-`-prefixed Web Components for the design system, native `<dialog>` and
  popover, CSS custom properties, cascade layers, container queries, `:has()` and View
  Transitions as progressive enhancement.
- Use `Intl` for dates, numbers and plurals. Use JSON message catalogues for English and
  Luganda first, with Kiswahili ready. No hard-coded user-facing strings.
- Check JSDoc types with `tsc --checkJs` as a dev-time step only. No transpilation.
- Self-host every asset. No runtime CDN. The service worker caches static assets only, never
  API responses or personal data.
- Performance budgets: at most 100 KB gzipped JavaScript per page, LCP under 2.5 s on a
  mid-range Android over slow 4G, CLS under 0.1.
- Accessibility: WCAG 2.2 AA, keyboard operable, visible focus, 44 px touch targets, status
  conveyed by icon plus text plus colour, works at 360 px and 200 percent zoom.

## Consequences

- Components are authored by the team and reviewed like any other production code.
- No npm runtime dependency; npm is used only for TypeScript type checking.
- The design system lands in M7, after the design tokens established in M0.
- Playwright journeys, keyboard-only runs, 360 px layouts and accessibility checks are
  release gates.
