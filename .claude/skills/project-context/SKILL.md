---
name: project-context
description: What is true in THIS project — stack, architecture, how to run and test the app, domain glossary. Per-project layer; wins over conventions on conflict. Filled in by /plan-feature on first run in a project.
---

<!-- TEMPLATE -->
<!-- This is the unfilled template. /plan-feature's first run in a project replaces
     every section below and deletes the TEMPLATE marker above. Until then, agents
     should treat this project as not yet set up and say so in their reports. -->

# Project context

## What this project is
One paragraph: the product, who it's for.

## Stack
Languages, frameworks, database, hosting — with versions where they matter.

## Architecture
Where things live. The 5–10 directories/modules an engineer must know, one line each.

## Running things
```bash
# install:
# run the app (and the URL it serves on):
# run the full test suite:
# lint:
# deploy a preview/staging instance of a branch (and how to get its URL):
```
These exact commands are what the orchestrator uses for Gate 1 — keep them current.

## Test environment & user personas
Where the blind tester runs (preview/staging URL pattern, which data it's connected
to — test data only, never production).

The personas below must mirror THIS product's real user segmentation — plan tiers
(free / pro / enterprise / trial), roles (owner / member / guest), sides of a
marketplace, logged-out visitors — whatever segments actually exist. Do not default
to a generic admin/user split. One seeded account per persona:

| Persona | Who they are (one line, in product terms) | Login | Password |
|---|---|---|---|
| | | | |

Also list the **boundaries** between personas that matter in this product (what a
free user hits when they touch a paid feature, quota limits, trial expiry) — the
orchestrator uses these to pick which personas blind-test a feature.

How to seed/reset these accounts. These are throwaway test credentials — real
production credentials must never appear in this file or be handed to any agent.

## Domain glossary
Terms that mean something specific in this product.

## Project-specific overrides
Anything here that deliberately contradicts the `conventions` skill, with why.

## Project skills
Other skills that exist only in this project (e.g. `design-system`) and when to load
them.
