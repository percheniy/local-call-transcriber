---
name: Транскрибаторус
description: Local call transcription in the supplied black-and-red utility world.
colors:
  ink: "#000"
  surface: "#fff"
  paper: "#f4f4f0"
  muted: "#655f5b"
  red: "#dc341e"
  pink: "#ff90e9"
  green: "#23a094"
typography:
  headline:
    fontFamily: "Manrope, system-ui, sans-serif"
    fontSize: "24px"
    fontWeight: 700
    lineHeight: 1.3
    letterSpacing: "-0.01em"
  title:
    fontFamily: "Manrope, system-ui, sans-serif"
    fontSize: "20px"
    fontWeight: 700
    lineHeight: 1.4
  body:
    fontFamily: "Manrope, system-ui, sans-serif"
    fontSize: "14px"
    lineHeight: 1.4
  path:
    fontFamily: "ui-monospace, Menlo, Consolas, monospace"
    fontSize: "13px"
rounded:
  panel: "4px"
  pill: "9999px"
spacing:
  small: "8px"
  medium: "16px"
  large: "24px"
  section: "32px"
components:
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.surface}"
    rounded: "{rounded.pill}"
    padding: "0 18px"
    height: "44px"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.pill}"
    padding: "0 18px"
    height: "44px"
  setup-panel:
    backgroundColor: "{colors.paper}"
    rounded: "{rounded.panel}"
    padding: "24px"
---

# Design System: Транскрибаторус

## Overview

**Creative North Star: "Black canvas, red matrix, white utility panel"**

Preserve the user's supplied visual authority: `.work/design-reference/Расшифровка звонков.dc.html`, from `Сервис расшифровки звонков.zip`. The implemented surface is a compact local utility with strong black outlines, a red offset panel, and conversational Russian copy. This document records the implementation; it does not introduce a new visual direction.

**Key Characteristics:**
- Black canvas with a red matrix of typed background lines: plausible pipeline log, humorous series, and rare Matrix easter eggs, placed in the areas the panel leaves visible. Copy lives in `web/matrix-lines.js`.
- White panel, crisp borders, pill actions, and locally bundled Manrope.
- Compact, bounded operational feedback.

## Colors

Red is the signature accent for the canvas and structural offset. Pink marks selection and primary hover feedback. Green denotes activity and completed progress. Ink defines text and outlines; surface and paper separate the main panel from setup; muted supports secondary information. Error and preparing states retain their implemented red and yellow status treatments.

## Typography

Use the bundled Manrope weights for interface copy and the system monospace stack for paths, filenames, and event times. Headlines are bold and compact; metric values are light, tabular numerals. Labels use uppercase, 12px bold text with 0.04em tracking. Preserve the literal heading “Транскрибаторус” and subtitle “Встречи, интервью и звонки — в текст. Прямо на вашем компьютере.”

## Layout

The main panel is at most 880px wide, with width `calc(100% - 32px)`, a 48px vertical margin, and padding `40px 32px 48px`. Sections use a 32px gap. Setup holds source and destination rows, folder actions, concurrency choice, and resource feedback. Metrics appear when available, followed by processing, recent results, and the bounded journal.

At 650px and below, the panel margin becomes 24px, padding becomes `28px 20px`, and the gap becomes 26px. The heading becomes 22px; path fields occupy a full row; metrics use two columns; job rows stack. Long paths and results wrap without horizontal overflow.

## Elevation & Depth

Depth comes from hard offsets and outlines. The main panel has an 8px red offset, reduced to 5px on mobile. Result dialogs use a 6px red offset over a translucent black backdrop. Primary-button hover uses a 4px pink offset; active buttons move 2px and lose the shadow. Avoid replacing these structural offsets with diffuse elevation.

## Shapes

Containers, path fields, empty states, and job rows use small corners and thin black borders. Actions and status badges use pill shapes. The destination field and empty states use dashed borders. Native concurrency selection retains its implemented 6px corner radius.

## Components

- **Author credit:** keep the readable footer credit for percheniy with visible, clickable gridchin.ru and t.me/gridchin links; follow ATTRIBUTION.md during redesigns and forks.
- **Folder controls:** read-only source path with a native folder picker; destination is visually subordinate and dashed. The “Проверить папку” action is an underlined text button.
- **Actions:** black primary and white secondary pills, at least 44px high. Secondary hover reverses to black. Disabled buttons reduce opacity to 0.45. Keyboard focus uses a visible offset outline; path focus outlines the containing field.
- **Indexing:** selecting a folder immediately shows a bounded audio count and progress bar. Discovery is indeterminate until the total is known; checking existing results uses measured progress. The completed summary retains found, pending, and existing-TXT counts.
- **Concurrency:** native select offers “Авто” and 1–5, with five slim worker indicators nearby in the processing heading.
- **Status:** outlined pill and small dot; preparing, running, done, and error states show actual state.
- **Progress and results:** outlined metric grid, green total progress, bordered job rows, and a scrollable result dialog. At most ten active and recent rows combined; journal shows at most ten events. No full-queue block.
- **Motion:** decorative matrix pauses drawing for reduced motion and hidden documents; button transitions are enabled only without reduced motion.

## Do's and Don'ts

- Do preserve the supplied Russian title and subtitle.
- Do keep paths readable and operational lists bounded.
- Do preserve visible keyboard focus and reduced-motion behavior.
- Don't replace the supplied canvas, panel, typography, or red offset with a new visual identity.
- Don't add a full-queue block or decorative dashboard sections.
