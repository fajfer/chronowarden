// SPDX-FileCopyrightText: 2026 Damian Fajfer <damian@fajfer.org>
//
// SPDX-License-Identifier: EUPL-1.2

// Compliance report of one snapshot (ADR-020). All text comes in as JSON data from report.py, so values are
// shown as plain text and never interpreted as Typst markup.

#let data = json(bytes(sys.inputs.data))
#let snap = data.snapshot

#let colors = (green: rgb("#2e7d32"), amber: rgb("#b26a00"), red: rgb("#c62828"))
#let labels = (green: "GREEN", amber: "AMBER", red: "RED")
#let badge(status) = box(
  fill: colors.at(status).lighten(85%),
  stroke: 0.5pt + colors.at(status),
  inset: (x: 4pt, y: 2pt),
  radius: 2pt,
  text(fill: colors.at(status), weight: "bold", size: 8pt, labels.at(status)),
)
#let mono(value) = text(font: "DejaVu Sans Mono", size: 8pt, value)
#let or-dash(value) = if value == none or value == "" { "—" } else { value }

#set document(title: data.title, author: "Chronowarden")
#set text(font: "Libertinus Serif", size: 10pt, lang: "en")
#set page(
  paper: "a4",
  margin: (x: 2cm, top: 2cm, bottom: 2.2cm),
  footer: context [
    #set text(size: 8pt, fill: luma(90))
    Snapshot #snap.id · #mono(snap.sha256.slice(0, 16))…
    #h(1fr)
    Page #counter(page).display() of #counter(page).final().first()
  ],
)
#set heading(numbering: "1.")
#set table(stroke: 0.4pt + luma(170), inset: 5pt)
#let head(..cells) = table.header(..cells.pos().map(c => strong(c)))

// Cover
#align(center)[
  #v(3cm)
  #text(size: 22pt, weight: "bold", data.title)
  #v(4mm)
  #text(size: 13pt, data.subtitle)
  #v(1.5cm)
]

#table(
  columns: (auto, 1fr),
  fill: (x, _) => if x == 0 { luma(245) },
  [Snapshot], [#snap.id],
  [Taken at], [#snap.created_at],
  [Reporting period], [#or-dash(snap.period)],
  [Label], [#or-dash(snap.label)],
  [Scope], [#snap.scope_text],
  [Secrets], [#snap.row_count],
  [Corrects snapshot], [#or-dash(snap.supersedes)],
  [Snapshot SHA-256], [#mono(snap.sha256)],
  [Audit log head], [event #snap.audit.events, #mono(snap.audit.head_hash)],
  [Generated], [#data.generated_at by #data.generator],
)

#v(1fr)
#text(size: 8pt, fill: luma(80))[
  This report shows metadata only: secret paths, dates, owners and systems. Chronowarden never reads secret values.
  The snapshot's canonical JSON export (#mono(snap.export_path)) has the SHA-256 above.
]
#pagebreak()

= Summary

#if data.policies.len() == 0 [
  No compliance policies were configured when this snapshot was taken, so it holds no policy results.
] else [
  #table(
    columns: (1fr, auto, auto, auto, auto, auto),
    align: (left, left, center, center, center, center),
    head[Policy][Framework][Status][Green][Amber][Red],
    ..data.policies
      .map(p => (
        [#p.name],
        [#or-dash(p.framework_text)],
        badge(p.status),
        [#p.counts.green],
        [#p.counts.amber],
        [#p.counts.red],
      ))
      .flatten(),
  )
]

== Inventory

#table(
  columns: (1fr, auto),
  head[Status at snapshot time][Secrets],
  ..data.inventory.map(row => ([#row.label], [#row.count])).flatten(),
)

#for p in data.policies [
  #pagebreak()
  = #p.name
  #if p.framework_text != none [#text(fill: luma(80), p.framework_text)]

  #table(
    columns: (auto, 1fr, auto, auto, auto),
    align: (left, left, center, center, center),
    head[Control][Requirement][In scope][Failing][Status],
    ..p
      .controls
      .map(c => (
        [#c.id],
        [#c.title \ #text(size: 8pt, fill: luma(80))[#c.rule_text. #c.threshold_text.#if c.source != none [ Source: #c.source.]]],
        [#c.in_scope],
        [#c.failing],
        badge(c.status),
      ))
      .flatten(),
  )

  #for c in p.controls.filter(c => c.failing > 0) [
    == #c.id: failing secrets
    #table(
      columns: (1fr, auto),
      head[Secret][Owners],
      ..c.failing_secrets.map(s => (mono(s.full_path), [#or-dash(s.owners.join(", "))])).flatten(),
    )
  ]
]

#pagebreak()
= Methodology and limitations

- The inventory and every policy result were frozen when the snapshot was taken (#snap.created_at). Statuses are as
  of that moment, not of the end of the reporting period.
- A rotation is the backend's last update of the secret. Chronowarden reads metadata only and never secret values.
- Policies are the organization's own interpretation of its requirements, defined in Chronowarden's configuration.
  Example policies for regulations are a starting point, not legal advice.
- Secrets removed from the backend are listed in the inventory of periodic snapshots but not evaluated by policies.
- Without thresholds, one failing secret makes a control red. A control with no secrets in scope is green.
- The snapshot's SHA-256 covers its whole JSON document, including the policy results, and the audit log head ties
  it to Chronowarden's hash-chained audit log at that moment.
