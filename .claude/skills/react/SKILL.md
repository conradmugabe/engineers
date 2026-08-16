---
name: react
description: How this team writes React — layered architecture, code-level rules, and open debates. Loaded by the frontend engineer whenever the project's frontend is React. Grows as articles are digested and debates get settled.
---

# React

**How to read this document.** Three tiers:

- **Do / Don't** — settled. Follow them; a deviation needs a stated reason in your
  report.
- **Debated** — genuinely open. Pick a side consciously per situation and say which
  and why in your report. The owner settles debates over time; settled ones move up.
- **Digested sources** — the provenance log. New articles append here; their claims
  get sorted into the tiers above, and where we deviate from a source we say so.

Project-layer skills (e.g. `design-system`, `project-context`) win over this file on
conflict.

---

## Principles — the why behind every rule

1. **Layers exist because change rates differ.** Markup changes daily, domain logic
   monthly, transport almost never. Separating them means a change in one doesn't
   require understanding the others. Structure is for maintainability; looking clean
   is a side effect.
2. **A component acts as a pure function: data in, markup out.** It owns the fact
   that an event happened (click, submit, hover). What happens as a *consequence* of
   the event is domain logic and does not belong in the component.
3. **Design from the screen backwards.** The data contract is shaped by what the page
   needs, not by entity-modeling purism. One request that returns what the screen
   shows beats three RESTfully-correct waterfall requests. The backend decides what
   to return; the frontend decides how to render it.
4. **Fight errors at their origin.** Validate where untrusted data enters (the
   transport layer), not in every leaf component that touches it.
5. **Prefer deep modules.** A good abstraction is an iceberg: small returned surface,
   large hidden implementation (`usePrompt()` returning `{ prompt, handleSubmit }`).
   A shallow module — big surface, little hidden — is not worth having; inline it.
6. **First draft, then tidy — every time.** Get it working in one place, then edit as
   you go. Design is continuous, not a refactoring quarter. But the first draft never
   ships.

## The layers

```
component  →  domain hook        →  client            →  constants
(markup,      (what data, when,     (transport: HTTP,     (endpoints,
 events)       consequences of       one function per      query keys)
               events)               call)
```

What each layer must NOT know:

| Layer | Must not know |
|---|---|
| Component | how data is fetched (fetch/axios/HTTP/WS/hardcoded), cache keys, data-shaping libraries |
| Domain hook | anything about markup or the DOM |
| Client | anything about React — no hooks, no components; callable from anywhere |
| Constants | nothing to know — dumb values with meaningful names |

**Server Components translation.** In an RSC / Next.js App Router project the same
layering holds with different mechanics: the domain-hook layer becomes server-side
data functions (called from Server Components), the client layer stays identical, and
client-side query caching (React Query) is reserved for genuinely client-interactive
data. Do not bolt a client-fetching stack onto a server-components app by habit — the
layer boundaries transfer, the tools don't.

## Do

- **Shape API contracts around the page.** If the screen needs the prompt, the
  answers, and whether the user answered, ask the backend for one endpoint returning
  exactly that. Raise contract needs with the backend engineer via the issue, early.
- **Communicate state with explicit fields.** `answered: boolean`, not
  `answers: null`-as-a-signal. Encoding meaning in a type's emptiness is a
  Chesterton's Fence: someone will "fix" the null to `[]` and silently break the UI.
- **Write the client as plain exported functions** in one file per API, on a
  preconfigured instance (base URL set once). No classes when there's no state to
  hide — the file provides the cohesion.
- **Extract meaningful-string constants**: endpoints in one object, query keys in
  another, each living next to their usage. Duplicate *values* with distinct *names*
  (`activePrompt` and `createAnswer` both `'/prompts'`) are fine — the name is the
  meaning.
- **Validate at the trust boundary with a schema** (e.g. zod): `schema.parse(data)`
  inside the client, so everything downstream works with proven shapes. This applies
  to every external source — API responses now; files, sockets, third-party payloads
  when they appear.
- **Handle every fetch's three shadows**: loading, error, empty. They are part of the
  feature, not polish. Decide what each looks like before reporting done.
- **Use guard clauses; avoid `else`.** Invert the condition, return early for the
  faulty/simple case, keep the golden path at base indentation.
- **Extract a child component when JSX conditionals nest.** One ternary is fine; a
  ternary inside a ternary means a component is hiding in there. Same rule as
  splitting an overgrown function.
- **Let layouts own placement.** Navigation renders *inside* a layout because where
  it goes is the layout's decision (top bar here, sidebar there). Multiple layouts
  per app is normal; create the second one when the second design appears, not
  before.
- **Prototype against hardcoded data — inside the client.** The rest of the app
  can't tell hardcoded from fetched, so swapping in the real API later touches one
  file. Never hardcode data in a component.
- **Adopt a data-fetching abstraction early** (React Query or the framework's
  equivalent) even under a general go-slow-on-libraries instinct — request-state
  bookkeeping (loading/error/refetch/invalidation) is the single biggest source of
  hand-rolled frontend complexity, and it's undifferentiated.

## Don't

- **Don't cast API responses to TypeScript types without runtime validation.** Types
  are erased at runtime; a cast is a wish. This is false security, and it's the most
  common form of it.
- **Don't let a component know its data's transport.** If you can tell from reading
  a component whether the data came over HTTP, the layers have leaked.
- **Don't put data-validity checks in leaf components** (`if (!Array.isArray(...))`
  scattered through the tree). Checks belong at the boundary; components trust their
  props.
- **Don't rush reusable extractions.** Extract on the second real usage, not on the
  prediction of one. (Exception: the layout — page structure is guaranteed to repeat,
  so extract it immediately.)
- **Don't mask loading with fake initial data.** `initialData: emptyObject` makes the
  UI render a lie while the real data is in flight and hides the loading state you
  were required to design. Model "not loaded yet" honestly (`undefined` + explicit
  loading UI). *Deviation from source: Kondov's article uses this pattern while
  prototyping; we rule against shipping it.*
- **Don't ship the first draft.** The single-component version proves the feature is
  possible. The layered version is the feature.

## Debated — pick a side consciously, argue it in your report

- **Where does display formatting live?** Source says data shaping (e.g.
  `dayjs(createdAt).fromNow()`) is domain logic → do it in the hook (ideally via the
  query's `select`). Counterposition: relative time and similar are *presentation* —
  locale-dependent (`Intl`), and the same domain value legitimately renders
  differently in different components; by the source's own "component decides how to
  render" rule it belongs at render time. Lean: transformations that change *meaning*
  (filtering, joining, deriving) → hook; transformations that change *appearance*
  (dates, currency, pluralization) → render, with `Intl`. Not yet settled by the
  owner.
- **Default vs named exports for components.** Source uses default exports.
  Named exports grep and refactor better and prevent import-name drift; frameworks
  (Next.js pages) sometimes force default. Follow the project's existing pattern;
  greenfield lean: named.
- **How much schema validation on very large/hot responses?** Parsing everything at
  the boundary is the rule; for genuinely huge payloads on hot paths the parse cost
  is real. Options: `schema.parse` everywhere (default), partial schemas for the
  fields actually used, or parse-in-dev/trust-in-prod. Default stands until a
  measured problem says otherwise.

## Digested sources

- **Alex Kondov — "Clean Architecture in React"** (Full-Stack Tao ch. 4, Feb 2024,
  alexkondov.com/full-stack-tao-clean-architecture-react/). Digested 2026-08-16.
  Contributed: the four-layer model, component-as-pure-function, event vs
  consequence, screen-backwards API design, explicit flags over null-communication,
  schema validation at trust boundaries, deep/shallow modules, guard clauses,
  nested-ternary extraction, layout ownership, hardcode-in-the-client prototyping.
  We deviate on: `initialData` placeholders (rejected), formatting-in-the-hook
  (demoted to Debated). RSC translation section is ours, not the source's.
