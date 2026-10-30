"use client";

/**
 * SPRINT AI-16 — Mixed-question answer composition.
 *
 * Renders the 7-section decomposition the engine stamps onto
 * ``ChatMessage.mixed_answer`` when the QU answer_mode is
 * "mixed" OR the capability tuple contains MIXED.
 *
 * Compact-first design (AI-6 concise-first contract)
 * --------------------------------------------------
 *
 * The brief is explicit: "Mixed UI: compact sections, no
 * forced 9-section answer, preserve AI-6 concise-first
 * experience." When only 1 section is populated, the renderer
 * renders its body_lines as a single paragraph — no section
 * chrome, no "Background" heading. When 2-3 sections are
 * populated, render compact cards. When ≥ 4 sections are
 * populated, render the cards in a 2-column grid on desktop.
 *
 * External-source labelling
 * -------------------------
 *
 * Each section with ``source_kind === "external"`` carries an
 * inline "From external source" badge so the user can see
 * which parts of the answer were sourced from outside UrsBiz.
 *
 * Missing-data highlighting
 * -------------------------
 *
 * The ``uncertainty`` section (when populated) renders with
 * an amber border + a "Tell us more" CTA pointing at the
 * suggested-questions panel. The CTA is informational — it
 * doesn't navigate; it just signals that filling the gap
 * would improve the next answer.
 *
 * Visual contract
 * ---------------
 *
 *   * Each populated section is its own ``<section
 *     aria-labelledby="…">`` with a ``h3`` heading.
 *   * The "From external source" badge uses text + colour
 *     (no icon-only / colour-only).
 *   * Body lines render as ``<p>`` for narrative sections
 *     and as ``<ul>`` for the recommendation + next-action
 *     sections (actionable lists read better as bullets).
 *   * Mobile: every grid stacks to a single column.
 */

import { AlertCircle, Info } from "lucide-react";
import type { MixedAnswer, MixedSection } from "./types";

export interface MixedSectionsProps {
  answer: MixedAnswer;
}

// --------------------------------------------------------------------------- //
// Body-line renderer — picks between paragraphs and bullets per
// section key. Actionable sections read better as lists; narrative
// sections read better as prose.
// --------------------------------------------------------------------------- //

const BULLET_SECTION_KEYS: ReadonlySet<MixedSection["key"]> = new Set([
  "recommendation",
  "next_action",
]);

function renderBody(section: MixedSection) {
  if (section.body_lines.length === 0) return null;
  if (BULLET_SECTION_KEYS.has(section.key)) {
    return (
      <ul className="list-disc space-y-1 pl-5 text-sm text-slate-800">
        {section.body_lines.map((line, i) => (
          <li key={i}>{line}</li>
        ))}
      </ul>
    );
  }
  return (
    <div className="space-y-2 text-sm text-slate-800">
      {section.body_lines.map((line, i) => (
        <p key={i}>{line}</p>
      ))}
    </div>
  );
}

// --------------------------------------------------------------------------- //
// One section renderer — compact card with title + source-kind
// badge + body.
// --------------------------------------------------------------------------- //

interface MixedSectionBlockProps {
  section: MixedSection;
  isUncertainty: boolean;
}

function MixedSectionBlock({
  section,
  isUncertainty,
}: MixedSectionBlockProps) {
  const headingId = `mixed-section-${section.key}`;
  const borderClass = isUncertainty
    ? "border-amber-300 bg-amber-50"
    : "border-slate-200 bg-white";

  return (
    <section
      aria-labelledby={headingId}
      className={`rounded-lg border p-3 ${borderClass}`}
      data-testid={`mixed-section-${section.key}`}
    >
      <div className="mb-2 flex items-center gap-2">
        <h3
          id={headingId}
          className={`text-sm font-semibold ${isUncertainty ? "text-amber-900" : "text-slate-900"}`}
        >
          {section.title}
        </h3>
        {section.source_kind === "external" ? (
          <span
            aria-label="Information sourced from external publisher"
            className="inline-flex items-center gap-1 rounded-md border border-violet-200 bg-violet-50 px-1.5 py-0.5 text-[10px] font-medium text-violet-800"
          >
            From external source
          </span>
        ) : null}
        {section.source_kind === "mixed" ? (
          <span
            aria-label="Section combines internal and external sources"
            className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-slate-50 px-1.5 py-0.5 text-[10px] font-medium text-slate-700"
          >
            Mixed source
          </span>
        ) : null}
      </div>

      {renderBody(section)}

      {isUncertainty ? (
        <p
          role="note"
          className="mt-2 flex items-start gap-1.5 text-xs text-amber-900"
        >
          <AlertCircle
            className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-600"
            aria-hidden="true"
          />
          <span>
            Tell us more — answering the suggested questions above
            will sharpen this section on your next turn.
          </span>
        </p>
      ) : null}

      {section.evidence_ids.length > 0 ? (
        <p className="mt-2 text-[10px] text-slate-500">
          {section.evidence_ids.length} supporting{" "}
          {section.evidence_ids.length === 1 ? "item" : "items"}
        </p>
      ) : null}
    </section>
  );
}

// --------------------------------------------------------------------------- //
// Single-section inline rendering — when only one section is
// populated, render its body_lines as a single paragraph. No
// section chrome — preserves AI-6 concise-first.
// --------------------------------------------------------------------------- //

function renderSingleSectionInline(section: MixedSection) {
  return (
    <div
      data-testid={`mixed-section-inline-${section.key}`}
      className="space-y-2 text-sm text-slate-800"
    >
      {section.body_lines.map((line, i) => (
        <p key={i}>{line}</p>
      ))}
      {section.source_kind === "external" ? (
        <p className="flex items-center gap-1 text-[10px] text-violet-700">
          <Info className="h-3 w-3" aria-hidden="true" />
          <span>From external source</span>
        </p>
      ) : null}
    </div>
  );
}

// --------------------------------------------------------------------------- //
// Component
// --------------------------------------------------------------------------- //

export function MixedSections({ answer }: MixedSectionsProps) {
  // Render gate: only render when the engine flagged the
  // prompt as mixed AND emitted at least one section.
  if (!answer.is_mixed) return null;
  const sections = answer.sections.filter((s) => s.body_lines.length > 0);
  if (sections.length === 0) return null;

  // Single-section inline — concise-first UX.
  if (sections.length === 1) {
    return (
      <div
        data-testid="mixed-sections"
        className="rounded-lg border border-slate-200 bg-white p-3"
      >
        {renderSingleSectionInline(sections[0])}
        {answer.rationale ? (
          <p className="mt-2 text-[10px] text-slate-500">{answer.rationale}</p>
        ) : null}
      </div>
    );
  }

  // 2-3 sections — compact single-column cards.
  if (sections.length <= 3) {
    return (
      <div data-testid="mixed-sections" className="space-y-2">
        {sections.map((s) => (
          <MixedSectionBlock
            key={s.key}
            section={s}
            isUncertainty={s.key === "uncertainty"}
          />
        ))}
        {answer.rationale ? (
          <p className="text-[10px] text-slate-500">{answer.rationale}</p>
        ) : null}
      </div>
    );
  }

  // ≥ 4 sections — grid on desktop, single column on mobile.
  return (
    <div data-testid="mixed-sections" className="space-y-2">
      <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
        {sections.map((s) => (
          <MixedSectionBlock
            key={s.key}
            section={s}
            isUncertainty={s.key === "uncertainty"}
          />
        ))}
      </div>
      {answer.rationale ? (
        <p className="text-[10px] text-slate-500">{answer.rationale}</p>
      ) : null}
    </div>
  );
}

export default MixedSections;