---
name: OpenDataFusion Console
description: "A flat-precision operations ledger for data work: near-white paper, ink, one cobalt accent, 1px rules, square corners, dense tabular layouts."
colors:
  paper: "#fbfbfc"
  surface: "#ffffff"
  ink: "#111827"
  body-slate: "#374151"
  graphite: "#4b5563"
  muted: "#6b7280"
  faint: "#9ca3af"
  rule: "#d1d5db"
  rule-soft: "#e5e7eb"
  grid-fill: "#f8f9fb"
  row-hover: "#f4f7ff"
  cobalt: "#1d4ed8"
  cobalt-deep: "#1e40af"
  cobalt-ink: "#172554"
  cobalt-wash: "#eff4ff"
  signal-green: "#15803d"
  signal-amber: "#b45309"
  signal-red: "#b91c1c"
  code-surface: "#0f172a"
  code-text: "#e2e8f0"
typography:
  display:
    fontFamily: "Archivo, PingFang SC, Microsoft YaHei, Noto Sans SC, sans-serif"
    fontSize: "clamp(64px, 9vw, 132px)"
    fontWeight: 700
    lineHeight: 0.84
    letterSpacing: "-0.07em"
  headline:
    fontFamily: "Archivo, PingFang SC, Microsoft YaHei, Noto Sans SC, sans-serif"
    fontSize: "26px"
    fontWeight: 650
    lineHeight: 1
    letterSpacing: "-0.035em"
  title:
    fontFamily: "Archivo, PingFang SC, Microsoft YaHei, Noto Sans SC, sans-serif"
    fontSize: "16px"
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: "-0.015em"
  body:
    fontFamily: "Archivo, PingFang SC, Microsoft YaHei, Noto Sans SC, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
  label:
    fontFamily: "Archivo, PingFang SC, Microsoft YaHei, Noto Sans SC, sans-serif"
    fontSize: "10px"
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: "0.045em"
  mono:
    fontFamily: "SFMono-Regular, Consolas, Liberation Mono, monospace"
    fontSize: "11px"
    fontWeight: 400
    lineHeight: 1.45
    letterSpacing: "normal"
rounded:
  none: "0px"
  dot: "50%"
spacing:
  "2xs": "2px"
  xs: "4px"
  sm: "6px"
  md: "8px"
  lg: "10px"
  xl: "12px"
  "2xl": "14px"
  "3xl": "16px"
  "4xl": "18px"
  page-x: "26px"
  page-y: "22px"
components:
  button-primary:
    backgroundColor: "{colors.cobalt}"
    textColor: "{colors.surface}"
    rounded: "{rounded.none}"
    height: "32px"
    padding: "0 12px"
  button-primary-hover:
    backgroundColor: "{colors.cobalt-deep}"
    textColor: "{colors.surface}"
    rounded: "{rounded.none}"
  button-primary-active:
    backgroundColor: "{colors.cobalt-ink}"
    textColor: "{colors.surface}"
    rounded: "{rounded.none}"
  button-default:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    height: "32px"
    padding: "0 12px"
  button-default-hover:
    backgroundColor: "{colors.cobalt-wash}"
    textColor: "{colors.cobalt}"
    rounded: "{rounded.none}"
  button-link:
    backgroundColor: "transparent"
    textColor: "{colors.cobalt}"
    rounded: "{rounded.none}"
    height: "auto"
    padding: "0"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    height: "32px"
    padding: "0 11px"
  input-focus:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
  card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "14px"
  tag:
    backgroundColor: "transparent"
    textColor: "{colors.muted}"
    rounded: "{rounded.none}"
    height: "19px"
    padding: "1px 6px"
  nav-item-active:
    backgroundColor: "{colors.cobalt-wash}"
    textColor: "{colors.cobalt}"
    rounded: "{rounded.none}"
    height: "30px"
    padding: "0 18px"
  table-header:
    backgroundColor: "{colors.grid-fill}"
    textColor: "{colors.muted}"
    rounded: "{rounded.none}"
    height: "32px"
    padding: "8px 12px"
  ledger-cell:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "13px 14px 12px"
  dialog:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "20px"
---

# Design System: OpenDataFusion Console

## Overview

**Creative North Star: "The Ruled Ledger"**

The console is a precision instrument laid on near-white paper. Structure comes from hairline rules and tonal layering, not from floating cards: a white cell sits inside a 1px rule grid, a 2px cobalt line marks where the operator is, and a dense table carries the work. The flatness is structural rather than stylistic. Every page is built from the same rail, top bar, ruled header, and data plane, so a pipeline editor and a dashboard read as two views of one ledger instead of two products.

The build is builder-first and Chinese-first. Type is one grotesque family, Archivo, with platform CJK fallbacks; numbers use tabular figures; monospace is reserved for code, IDs, cron expressions, and ports. Cobalt is a signal, not a surface: it appears as a spine, an active state, a link, or a primary action. State green, amber, and red are semantic only. The result should feel exact, quiet, and fast to scan over a long session, not decorative.

The shipped world explicitly refuses the category's icon-card grid, floating rounded panels, and hero-metric strip. The dashboard proves the alternative: four operational numbers share one ruled strip, the run table is the main body, and a narrow side column holds the governed exception and the next scheduled windows. Consumer-facing run views and public shares keep the same grammar with fewer controls.

**Key Characteristics:**
- Near-white paper, white surfaces, ink text, and one cobalt accent.
- 1px rules carry structure; resting surfaces have no shadow.
- Zero corner radius everywhere except circular status dots.
- Archivo with CJK fallback; tabular numerals; mono only for code and identifiers.
- The cobalt spine: 2px accents on active navigation, current tree nodes, page-header edges, and the brand mark.
- Dense Operate layout: 64px top bar, 232px grouped rail, 13px base type, 12px tables.
- Tenant accent is clamped for contrast before it reaches the theme variables.
- Status is always carried by a dot plus a text label, never color alone.

## Colors

A near-neutral paper-and-ink palette with one cobalt instrument light and a three-hue semantic state set. The palette is cool, not warm, and derives almost all separation from neutral steps rather than hue.

### Primary
- **Cobalt Instrument** (`#1d4ed8`): The single accent. Used for primary buttons, links, active navigation text and icon, the 2px spine, the active tab bar, focus rings, selected tree text, and the current-row wash. It is the default tenant accent and the value the legibility clamp starts from.
- **Cobalt Deep** (`#1e40af`): Hover state for primary buttons and link text. Derived from the tenant accent as 82% accent plus black.
- **Cobalt Ink** (`#172554`): Pressed state for primary buttons.
- **Cobalt Wash** (`#eff4ff`): Active navigation background, selected tree node background, current table row, and default-button hover fill. Derived as 8% accent plus white.

### Secondary
No secondary brand palette exists. Green, amber, and red are status roles, not decorative accents:
- **Signal Green** (`#15803d`): Online state, success, passing checks, healthy rows.
- **Signal Amber** (`#b45309`): Running or warning state, needs-attention markers.
- **Signal Red** (`#b91c1c`): Failed jobs, critical alerts, destructive actions.

### Neutral
- **Paper** (`#fbfbfc`): The application canvas behind panels and the login split.
- **Surface** (`#ffffff`): Cards, panels, tables, rail, top bar, dialogs, and controls.
- **Ink** (`#111827`): Primary text, headings, brand mark, active pagination fill, and the fallback accent after clamp exhaustion.
- **Body Slate** (`#374151`): Regular Element Plus text and secondary prose.
- **Graphite** (`#4b5563`): Navigation labels and statement copy.
- **Muted** (`#6b7280`): Metadata, labels, notes, table headers, placeholders, and quiet actions.
- **Faint** (`#9ca3af`): Icons at rest, separators inside metadata, and disabled-adjacent marks.
- **Rule** (`#d1d5db`): Structural 1px borders: rail, top bar, panels, cards, inputs, dialogs.
- **Rule Soft** (`#e5e7eb`): Internal row dividers, section separators, footer rules, and inactive borders.
- **Grid Fill** (`#f8f9fb`): Table header background and studio canvas fill.
- **Row Hover** (`#f4f7ff`): Table row hover.
- **Code Surface** (`#0f172a`): SQL and API code blocks.
- **Code Text** (`#e2e8f0`): Code block text.

### Named Rules
**The Cobalt Spine Rule.** A 2px cobalt line is the only accent allowed to be structural. It marks the active navigation item, the current tree node, the current page-header edge, and the brand mark. Selected table rows use the cobalt wash rather than a 2px bar; the build chooses the quieter treatment there.

**The One Accent Rule.** Cobalt occupies roughly 10% or less of any screen. State hues never become brand accents, and there is no second decorative color. If a surface needs emphasis, use a rule, weight, or spacing before adding color.

**The Legibility Clamp Rule.** Tenant branding may change the primary color, but never bypass contrast. The build accepts only a 6-digit hex; invalid values fall back to cobalt. It computes relative luminance, repeatedly multiplies RGB channels by 0.86 until contrast against white reaches 4.5:1, and falls back to ink after 12 steps. The clamped value is written to `--odf-primary`, `--odf-accent`, and `--el-color-primary`; deep and wash variants are derived with `color-mix` at 82% black and 8% white respectively.

**The Status Triplet Rule.** A state is never color alone. Pair the 6px dot with a text label, and usually an outlined tag, so the same state survives grayscale and color-vision differences.

## Typography

**Display Font:** Archivo (with PingFang SC, Microsoft YaHei, Noto Sans SC, sans-serif)
**Body Font:** Archivo (with the same CJK fallbacks)
**Label/Mono Font:** Archivo for labels; SFMono-Regular, Consolas, Liberation Mono for code and identifiers

**Character:** A precise grotesque with compressed, negative tracking at large sizes and wide tracking on tiny uppercase labels. Chinese text resolves through platform CJK faces at the same optical weight. The contrast is in scale and density, not in a second typeface.

### Hierarchy
- **Display** (700, `clamp(64px, 9vw, 132px)`, 0.84, -0.07em): The login hero only. Set as two lines with a hard break; the tight leading is intentional.
- **Headline** (650, 26px, 1, -0.035em): The top-bar page title. It is the largest recurring UI text and stays on one line.
- **Title** (600, 16px, 1.4, -0.015em): Section headings, dialog and drawer titles, and the login panel heading (24px on the login panel). Panel sub-headings use 13px at 600.
- **Body** (400, 13px, 1.5): The application base. Tables and controls drop to 12px; muted metadata to 11px; micro labels to 10px and 9px. The dashboard lede caps at 68ch; the login statement caps at 36ch.
- **Label** (500, 10px, 0.045em): Table headers and tight metadata. Navigation group labels are 9px at 600 with 0.12em tracking; clock and section labels use 9px with 0.08em. Uppercase is used for Latin micro labels, not for Chinese headings.
- **Mono** (400, 9-11px, 1.45): IDs, timestamps, cron expressions, API paths, ports, and code. Code blocks use 12px mono on Code Surface. Mono never carries prose, headings, or button labels.

Numeric display is a distinct behavior rather than a separate family: ledger and stat values use 30-31px at 650, line-height 0.95-1, letter-spacing -0.045 to -0.05em, and `font-variant-numeric: tabular-nums`. Dashboard and studio widget metrics use the same tabular treatment.

### Named Rules
**The Tabular Numerals Rule.** Every number that can be compared or scanned uses `font-variant-numeric: tabular-nums`: ledger cells, stat cards, clocks, table counts, inventory totals, and metrics. Proportional figures are a defect on operational data.

**The One Family Rule.** Archivo (plus CJK fallback) carries all UI text. There is no display serif, no decorative face, and no monospace heading. Mono is a data classification, not a mood.

**The Compression Rule.** Negative tracking scales with size: -0.07em at the login hero, -0.035em at the page title, -0.015em at section titles. Positive tracking appears only on uppercase micro labels, from 0.045em to 0.12em. Do not apply positive tracking to Chinese headings.

## Layout

The desktop shell is a fixed instrument: a 232px grouped rail on the left, a 64px top bar above the content, and a scrolling content plane. The rail is white with a 1px right border; the top bar is white with a 1px bottom border. The brand block is 64px tall with a 30px ink square, a 2px cobalt bottom edge, the product name at 14px/650, and a 9px uppercase descriptor. Navigation groups use 9px/600 labels at 0.12em tracking; items are 30px tall with 18px horizontal padding, a 14px icon, and 12.5px/450 text. The active item gets the cobalt wash, cobalt text at 550, and a 2px left spine. The rail footer holds a 6px service dot, an 11px status label, and 9px mono port/version metadata.

The top bar holds the page title at 26px/650 with a 11px project/role context line, a 32px search entry, a 128px project switch, a 10px online state, and a 28px square avatar. The search entry collapses to a 32px icon-only button below 1180px, and the context line disappears at the same breakpoint.

Pages use the shared `.page` rhythm: 22px top, 26px horizontal, 34px bottom. Toolbars sit above the data plane with 8px gaps, wrap at narrow widths, and use 10px gaps in denser views. The default rhythm is 2px inside a rule, 4-6px inside a control, 10-14px between controls and groups, and 14-16px between panels. Tables are the main body, not a card inside a card.

The dashboard is the signature composition. A ruled header carries a 68ch lede on the left and a right-aligned clock; a 96px x 2px cobalt spine sits on the header's bottom edge. Below it, a four-cell ledger strip shares one 1px rule grid with 1px gaps and no outer top border, so it attaches to the header. Each cell is white with 13px/14px padding: a 10px muted label, a 31px tabular value, and a 10px note. The body below is a `1.65fr / 0.9fr` grid with 14px gap and a 270px minimum side column. The run table occupies the wide column; the side column holds one governed exception and the next scheduled windows. An inventory line closes the page with a 1px top rule and 10px totals.

Studio shells are framed workspaces: `calc(100vh - 96px)` tall, 16px/20px margin, 1px rule border, a 48px tool header, a three-column body (`218px / minmax(0, 1fr) / 318px`), and a 214px console. The canvas is Grid Fill; the tree and config panes are white with 1px inner borders. The header wraps its action group and the side panes hide below 900px.

The login is a split composition: `minmax(0, 1.35fr) / minmax(420px, 0.65fr)`, intro on paper, form panel on white, separated by a 1px rule. A 2px cobalt vertical spine sits at the intro's left edge. The hero uses the display ramp; the form panel is capped at 352px. The public share view uses a 56px header, a 30px brand mark, and a 1200px maximum body width; it is the same ledger with the navigation removed.

Density is deliberate. The builder base is 13px, not 16px. Tables are 12px with 9px vertical cell padding; controls are 32px tall (26px small, 40px large); meta is 9-11px. The console is designed to remain usable at 1366px and to scale to wide monitors, so adding air means more rules and grouping, not larger type.

Responsive behavior observed in the build:
- **1180px:** rail narrows to 204px; search becomes an icon-only 32px button; the top-bar context line hides; studio columns become 180px / 1fr / 280px.
- **1100px:** Ops summary cards drop from six columns to three.
- **1000px:** catalog tree and detail stack into one column.
- **980px:** dashboard body stacks to one column; the side column follows the run table.
- **900px:** the rail becomes a horizontal scrolling strip above the content; group labels and rail footer hide; active items switch to a 2px bottom spine; top bar height drops to 56px and title to 17px; login stacks intro above panel; studio side panes hide and the shell height becomes automatic.
- **800px:** global page padding drops to 16px/14px/26px; dialogs become `calc(100vw - 24px)`.
- **720px:** dashboard padding tightens; the ledger becomes two columns; the inventory line wraps.

### Named Rules
**The Fixed Instrument Rule.** Desktop keeps the 64px top bar and 232px rail. Do not add a second frame, a floating content well, or a second navigation layer. Page identity belongs in the top bar; section grouping belongs in the rail.

**The Density With Air Rule.** Builder screens stay at a 13px base with 12px tables and controls. Create calm through grouping, ruled sections, and 10-14px gaps, not by inflating type or padding. A 16px body size on a builder table is a regression.

**The Single Collapse Rule.** The shell has one collapse behavior: below 900px the rail becomes a horizontal strip, the login stacks, and studio side panes hide. Do not introduce card-style mobile shells or a separate mobile navigation pattern.

## Elevation & Depth

The system is flat at rest. Depth is conveyed by tonal layering and rules: Paper is the canvas, Surface is the working plane, Grid Fill is a table header or studio canvas, and Rule/Rule Soft draw the boundaries. Cards, panels, tables, stat cells, navigation, and the studio frame carry no box-shadow. Shadows are reserved for surfaces that genuinely float above the page: dialogs, drawers, message boxes, messages, and poppers.

### Shadow Vocabulary
- **Overlay** (`box-shadow: 0 8px 22px rgba(17, 24, 39, 0.12)`): Dialogs, drawers, message boxes, messages, select/dropdown poppers. This is the only elevation shadow in the system.
- **Focus halo** (`box-shadow: 0 0 0 1px var(--odf-accent) inset, 0 0 0 3px rgba(29, 78, 216, 0.12)`): Input, select, and textarea focus. The inset 1px line stays crisp; the 3px halo is a soft confirmation.
- **Keyboard focus** (`outline: 2px solid var(--odf-accent); outline-offset: 2px`): Global `:focus-visible` treatment for links, buttons, and other focusable elements.

### Named Rules
**The Flat-At-Rest Rule.** No resting card, panel, table, stat cell, or studio pane gets a shadow. If a surface looks like it needs one, add a 1px rule or a tonal step instead.

**The Overlay-Only Shadow Rule.** The single `0 8px 22px rgba(17, 24, 39, 0.12)` shadow belongs to overlays. Using it on a static container is a system violation.

**The Focus Ring Rule.** Never remove focus. Use the 2px cobalt outline for general focus, and the inset 1px plus 3px halo for text fields. Focus is one of the few places the accent may glow.

## Shapes

The form language is square, ruled, and planar. The default radius is `0px` for buttons, inputs, cards, panels, dialogs, drawers, tags, tables, tree nodes, code blocks, and the studio shell. The only recurring circle is the 6px status dot; a 6px fact key and an 8px exception mark are squares. The brand mark and avatar are 30px and 28px squares. Status dots are the only `50%` radius in the system.

Borders are 1px. Structural borders use Rule; internal dividers use Rule Soft. The 2px cobalt spine is the only line that is both colored and structural. The dashboard ledger uses a 1px rule background with 1px gaps, so the rules themselves create the cell division. A 1px dashed Rule Soft line is used for the column-lineage separator; that is the single dashed exception.

A few scoped views still declare 6px, 8px, 10px, or 12px radii. Global overrides force the visible surfaces back to 0, and those declarations are not tokens. Do not reintroduce them on new surfaces.

### Named Rules
**The Square-Corner Rule.** Radius is `0` everywhere except circular status dots. If an Element Plus primitive defaults to a radius, the global override owns it; do not patch it locally with a new value.

**The Rule-Not-Box Rule.** Reach for a 1px line before a new container. Use a rule to separate, a tonal step to group, and a border to enclose. Do not solve hierarchy by adding a rounded card or a shadow.

## Components

### Buttons
- **Shape:** Square (0px radius), 1px border, no shadow, 120ms ease on background, border, and color.
- **Primary:** Cobalt background, white text, 32px minimum height, 0 12px padding, 12px/500 label. Hover is Cobalt Deep; pressed is Cobalt Ink. Used for the one confirming action in a toolbar or dialog.
- **Default:** White background, Rule border, Ink text. Hover is Cobalt Wash with Cobalt text and a Cobalt border. This is the workhorse for refresh, cancel, and secondary tools.
- **Link:** Transparent, no border, 11px Cobalt text, auto height. Hover darkens to Cobalt Deep and underlines with a 3px offset. Used inside table rows and panel headers.
- **Small / Large:** Small is 26px tall with 0 9px padding and 11px text; large is 40px tall with 0 16px padding and 13px text. Disabled state is 0.42 opacity, not a color swap.

### Chips (Tags)
- **Style:** Transparent background, 1px `currentColor` border, 0 radius, 10px/500 text, 1px 6px padding, 19px minimum height. The outline carries the state hue; the fill stays transparent so the tag reads as a stamp rather than a badge.
- **State:** Success uses Signal Green, warning Signal Amber, danger Signal Red, info Muted, primary Cobalt. Tags are labels, not buttons; interactive tags only appear in catalog search hits.

### Cards / Containers
- **Corner Style:** Square (0px).
- **Background:** Surface white on Paper; Grid Fill for table headers and studio canvas.
- **Shadow Strategy:** None at rest; see Elevation & Depth.
- **Border:** 1px Rule. Internal dividers use Rule Soft.
- **Internal Padding:** Card header 10px 14px, card body 14px. Dashboard panel header 10px 14px; panel body rows 9-14px vertical. Studio panes have no outer padding; their content owns it.
- **Headers:** Card and panel titles are 13px/600 with -0.01em tracking. A 10px muted sub-line sits 2px below. Section titles that need more weight use 16px/600 with a 1px Ink bottom rule.

### Inputs / Fields
- **Style:** Surface white, 0 radius, 1px inset Rule shadow, 32px minimum height, 12px text, 11px muted field labels. The inset line is used instead of a border so the control keeps a crisp edge at any zoom.
- **Focus:** 1px Cobalt inset plus the 3px 12% cobalt halo. Hover changes the inset line to Faint. Placeholder text is Muted.
- **Error / Disabled:** Errors use the Element Plus alert/message language (Signal Red border and a pale red surface for error alerts). Disabled controls rely on Element Plus opacity; form items keep a 14px bottom margin.
- **Form rhythm:** Labels sit above fields in the login and consumer forms; dense settings forms use a 90-110px left label column. Label text is 11px Muted with 4px bottom padding.

### Navigation
- **Rail:** 232px white column with a 1px Rule right border. Groups are separated by 6px and labeled at 9px/600 with 0.12em tracking. Items are 30px tall, 12.5px/450 Graphite, with 14px Faint icons. Hover is `#f8f9fb` with Ink text. Active is Cobalt Wash, Cobalt text at 550, Cobalt icon, and a 2px Cobalt left spine.
- **Top bar:** 64px white bar with a 1px Rule bottom border. The page title is 26px/650 with -0.035em tracking; the project/role context is 11px Muted. The search entry is a 32px Paper field with a 1px Rule border and 11px Muted text. The online state is a 6px dot plus a 10px label. The avatar is a 28px Ink square with 10px white text.
- **Mobile:** Below 900px the rail becomes a horizontal strip with hidden group labels and footer. Items keep 32px height and gain a 2px bottom spine when active. The top bar drops to 56px and the title to 17px; the user copy and online label hide.

### Tables
- **Style:** 12px Ink text on Surface, `size="small"` density. Header is Grid Fill with 10px/500 Muted text at 0.045em tracking, 8px vertical padding, and a 1px Rule bottom border. Cells have 9px vertical padding, 0 12px horizontal padding, 1.45 line-height, and 1px Rule Soft bottom borders; the last row loses its border.
- **States:** Hover is Row Hover (`#f4f7ff`). The current row is Cobalt Wash. Row-click tables add a pointer cursor. Empty state is a 90px minimum block with 12px Muted text. IDs and times use mono; quantities use tabular figures.
- **Selection:** The current row uses the wash, not a heavy outline. The 2px spine is reserved for navigation and tree current nodes.

### Ledger Strip (Signature)
The dashboard's four-cell operational strip is the signature data component. It is a `repeat(4, minmax(0, 1fr))` grid with a 1px Rule border, no top border when attached to the header, a Rule background, and 1px gaps. Each cell is white with 13px 14px 12px padding. The label is 10px/500 Muted; the value is 31px/650 with -0.05em tracking and tabular numerals; the note is 10px Muted with ellipsis. A failing value turns Signal Red. The strip replaces the icon-card grid and the hero-metric strip; it is not a card row.

### Status Marker
A 6px circle plus a 10px/500 label. Green for success/online, amber for running/warning, red for failure/critical, Faint for neutral/queued. The dashboard run table pairs the dot with the label; the alert panel uses an 8px square mark instead. Outlined tags can repeat the state, but the dot-plus-text pair is the minimum.

### Studio Shell
The framed editor for pipelines, APIs, datasets, dashboards, and apps. It is `calc(100vh - 96px)` tall with 16px/20px margin, a 1px Rule border, and no radius. The 48px header holds a back link, inline title and cron inputs, a published/draft tag, and a wrapped action row (save, validate, preview, run, backfill, cursors, enable, publish, versions). The body is a three-column grid: 218px asset tree, flexible canvas, 318px config. The tree and config use white with 1px inner borders; the canvas uses Grid Fill. The 214px console closes the frame with a 1px top rule. Below 1180px the columns narrow to 180px / 1fr / 280px; below 900px the side panes hide and the shell becomes a single column.

### Overlays
Dialogs, drawers, message boxes, and messages are square, 1px Rule, Surface white, and carry the single overlay shadow. Headers are 16px 20px with a 1px Rule bottom border; titles are 16px/600 with -0.015em tracking; bodies are 20px with 12px text; footers are 12px 20px with a Rule Soft top border. Drawers add a 1px Rule left border. Messages use the same square rule-and-shadow language; error, success, and warning messages take their state border. Alerts are square, 1px Rule, 10px 12px padding; error alerts use `#fff5f5` with `#fecaca`, info alerts use `#f8fafc`.

### Cobalt Spine Placements
- Active rail item: 2px left `::before`, full item height. On mobile it becomes a 2px bottom edge.
- Current tree node: `box-shadow: inset 2px 0 0 var(--odf-accent)` plus the wash background.
- Page header: 96px x 2px `::after` on the dashboard header's bottom edge.
- Login intro: 2px vertical line at the intro's left edge, with 0.9 opacity.
- Brand mark: 2px Cobalt bottom edge on the 30px Ink square, repeated in the rail, login, and public share.
- Active tab: 2px Cobalt `el-tabs` active bar.
- Selected dashboard widget: 2px Cobalt inset outline in edit mode.

## Do's and Don'ts

### Do:
- **Do** build structure with 1px rules: Rule for containers and major divisions, Rule Soft for internal rows. Use the ledger's 1px-gap rule grid for grouped numbers.
- **Do** keep corners at 0 and the only circle at a 6px status dot.
- **Do** use Cobalt as a line, a link, or a primary action; use Cobalt Wash for active and selected backgrounds. Keep it at roughly 10% of the screen or less.
- **Do** keep the page title at 26px/650 with -0.035em tracking, section titles at 16px/600, and panel titles at 13px/600.
- **Do** use tabular numerals for every operational number, and reserve mono for IDs, timestamps, cron, API paths, ports, and code.
- **Do** preserve the 64px top bar + 232px rail shell, the 22px/26px/34px page rhythm, and the 10-14px internal gaps.
- **Do** collapse the rail to a horizontal strip at 900px, stack the dashboard at 980px, and switch the ledger to two columns at 720px.
- **Do** clamp tenant accents with the luminance loop and let the deep/wash variants derive with `color-mix`.
- **Do** pair a status dot with a text label and, where useful, an outlined tag.

### Don't:
- **Don't** add a resting shadow to cards, panels, tables, stat cells, or studio panes. The only elevation shadow is the overlay `0 8px 22px rgba(17, 24, 39, 0.12)`.
- **Don't** introduce a radius other than 0; scoped 6/8/10/12px declarations are neutralized by global overrides and must not become new tokens.
- **Don't** use monospace for prose, headings, navigation labels, or button text.
- **Don't** add a second accent, a gradient, an icon-card grid, a floating rounded panel, or a hero-metric strip. The flat ledger is the alternative.
- **Don't** use status color alone, and don't promote green/amber/red to decorative brand roles.
- **Don't** let tenant branding bypass the contrast clamp or override radii, shadows, and rules.
- **Don't** promote the Ops summary cards' 3px hue-coded left borders (`#3b82f6`, `#ef4444`, `#f59e0b`) into the system; that is drift from the system, and status belongs to the dot/tag tokens.
- **Don't** inflate builder type to 16px or add a separate mobile card shell to solve density or responsiveness.
- **Don't** apply positive letter-spacing to Chinese headings; reserve tracking for uppercase Latin micro labels.
