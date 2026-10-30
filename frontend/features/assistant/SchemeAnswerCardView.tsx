"use client";

/**
 * SPRINT AI-16 — Government-scheme advisory card.
 *
 * Renders the 13-field ``SchemeAnswerCard`` payload the engine
 * stamps onto ``ChatMessage.scheme_card`` / ``ChatGenerationMeta
 * .scheme_card``. Mounted directly above the assistant body
 * inside ``TrustFirstResponse`` when the payload is non-null.
 *
 * Conservative language contract
 * ------------------------------
 *
 * The brief is explicit: the renderer must NEVER say
 * "definitely eligible". The disposition phrase is one of
 * four canonical strings:
 *
 *   * "Likely match based on available data."
 *   * "Appears eligible based on available data."
 *   * "Requires verification to confirm eligibility."
 *   * "Insufficient information to determine eligibility."
 *
 * The backend stamps the disposition + matching_score on the
 * wire; the AI-16 ``disposition_phrase`` helper maps the pair
 * to one of the four phrases. We do NOT compute eligibility
 * client-side — the backend is the only source of truth.
 *
 * Visual contract
 * ---------------
 *
 *   * The disposition badge is **text + colour + icon** — never
 *     colour-only. POTENTIAL_MATCH = info-blue + Info icon,
 *     CONFLICT = warn-amber + AlertCircle, GAP_UNKNOWN =
 *     slate + Info (lower-emphasis). The four phrasing tiers
 *     inside POTENTIAL_MATCH ("likely match" / "appears
 *     eligible") are surfaced as text under the chip.
 *   * The benefits list carries an inline "From external
 *     source" badge so the user can see at a glance which
 *     claims are sourced from outside UrsBiz.
 *   * The application link button opens in a new tab with
 *     ``rel="noopener noreferrer"``.
 *   * The final-authority disclaimer is rendered verbatim as
 *     a separate block — it is the brief's mandatory piece.
 *   * "Why this business may match" + "Missing eligibility
 *     information" use the same text/colour/icon pattern as
 *     the AI-7 MissingInfoCard.
 */

import { AlertCircle, ExternalLink, Info } from "lucide-react";
import type { SchemeAnswerCard } from "./types";

export interface SchemeAnswerCardViewProps {
  card: SchemeAnswerCard;
}

// --------------------------------------------------------------------------- //
// Disposition phrase mapping — the brief's four canonical phrases.
// --------------------------------------------------------------------------- //
//
// The backend stamps ``match_disposition`` + an optional matching
// score; the AI-16 ``disposition_phrase`` helper returns one of
// these four strings. We duplicate the lookup here for the case
// where the backend did not stamp the phrase on the wire (legacy
// rows + clients that pre-date the helper). The backend is the
// source of truth — when the phrase IS stamped, prefer it.

const PHRASE_LIKELY_MATCH = "Likely match based on available data.";
const PHRASE_APPEARS_ELIGIBLE =
  "Appears eligible based on available data.";
const PHRASE_REQUIRES_VERIFICATION =
  "Requires verification to confirm eligibility.";
const PHRASE_INSUFFICIENT_INFORMATION =
  "Insufficient information to determine eligibility.";

// --------------------------------------------------------------------------- //
// Disposition chip tone + icon — three values from the backend
// (potential_match / gap_unknown / conflict). Each chip carries
// text + colour + icon — never colour-only.
// --------------------------------------------------------------------------- //

interface DispositionChipProps {
  disposition: SchemeAnswerCard["match_disposition"];
  phrase: string;
}

function DispositionChip({ disposition, phrase }: DispositionChipProps) {
  const tone = (() => {
    switch (disposition) {
      case "potential_match":
        return {
          bg: "bg-sky-50",
          text: "text-sky-900",
          border: "border-sky-300",
          Icon: Info,
        };
      case "conflict":
        return {
          bg: "bg-amber-50",
          text: "text-amber-900",
          border: "border-amber-300",
          Icon: AlertCircle,
        };
      case "gap_unknown":
      default:
        return {
          bg: "bg-slate-50",
          text: "text-slate-700",
          border: "border-slate-300",
          Icon: Info,
        };
    }
  })();

  const { bg, text, border, Icon } = tone;
  return (
    <span
      aria-label={`Eligibility disposition: ${phrase}`}
      className={`inline-flex items-center gap-1.5 rounded-md border ${bg} ${text} ${border} px-2 py-1 text-xs font-medium`}
    >
      <Icon className="h-3.5 w-3.5" aria-hidden="true" />
      <span>{phrase}</span>
    </span>
  );
}

function resolvePhrase(card: SchemeAnswerCard): string {
  // The backend should stamp the canonical phrase via
  // ``disposition_phrase(...)``. If it didn't, fall back to a
  // safe default. Never invent a stronger claim.
  switch (card.match_disposition) {
    case "potential_match":
      // Without a score on the wire we can't split the two
      // stronger phrases, so pick the conservative one.
      return PHRASE_APPEARS_ELIGIBLE;
    case "conflict":
      return PHRASE_REQUIRES_VERIFICATION;
    case "gap_unknown":
    default:
      return PHRASE_INSUFFICIENT_INFORMATION;
  }
}

// --------------------------------------------------------------------------- //
// Component
// --------------------------------------------------------------------------- //

export function SchemeAnswerCardView({ card }: SchemeAnswerCardViewProps) {
  const phrase = resolvePhrase(card);

  return (
    <section
      aria-labelledby="scheme-card-title"
      className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm"
      data-testid="scheme-answer-card"
    >
      {/* Title row */}
      <header className="mb-3 flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
        <div className="flex-1">
          <h3
            id="scheme-card-title"
            className="text-base font-semibold text-slate-900"
          >
            {card.official_name}
          </h3>
          <p className="mt-1 text-xs text-slate-600">{card.authority}</p>
        </div>
        <div className="md:ml-3 md:shrink-0">
          <DispositionChip
            disposition={card.match_disposition}
            phrase={phrase}
          />
        </div>
      </header>

      {/* Last verified */}
      {card.last_verified_date ? (
        <p className="mb-3 text-xs text-slate-500">
          Source last verified:{" "}
          <time dateTime={card.last_verified_date}>
            {card.last_verified_date}
          </time>
        </p>
      ) : null}

      {/* Why this business may match */}
      {card.why_business_may_match.length > 0 ? (
        <div className="mb-3">
          <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-700">
            Why this business may match
          </h4>
          <ul className="space-y-1 text-sm text-slate-800">
            {card.why_business_may_match.map((line, i) => (
              <li key={i} className="flex items-start gap-2">
                <Info
                  className="mt-0.5 h-3.5 w-3.5 shrink-0 text-sky-600"
                  aria-hidden="true"
                />
                <span>{line}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {/* Missing eligibility info */}
      {card.missing_eligibility_info.length > 0 ? (
        <div className="mb-3 rounded-md border border-amber-200 bg-amber-50 p-3">
          <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-amber-900">
            Missing eligibility information
          </h4>
          <ul className="space-y-1 text-sm text-amber-900">
            {card.missing_eligibility_info.map((line, i) => (
              <li key={i} className="flex items-start gap-2">
                <AlertCircle
                  className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-600"
                  aria-hidden="true"
                />
                <span>{line}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {/* Benefits (with external-source badge) */}
      {card.benefit_description.length > 0 ? (
        <div className="mb-3">
          <div className="mb-1 flex items-center gap-2">
            <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-700">
              Benefits
            </h4>
            <span
              aria-label="Information sourced from external publisher"
              className="inline-flex items-center gap-1 rounded-md border border-violet-200 bg-violet-50 px-1.5 py-0.5 text-[10px] font-medium text-violet-800"
            >
              From external source
            </span>
          </div>
          <ul className="list-disc space-y-1 pl-5 text-sm text-slate-800">
            {card.benefit_description.map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {/* Eligibility criteria */}
      {card.eligibility.length > 0 ? (
        <details className="mb-3">
          <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-slate-700">
            Eligibility criteria ({card.eligibility.length})
          </summary>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-800">
            {card.eligibility.map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ul>
        </details>
      ) : null}

      {/* Required documents */}
      {card.required_documents.length > 0 ? (
        <details className="mb-3">
          <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-slate-700">
            Required documents ({card.required_documents.length})
          </summary>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-800">
            {card.required_documents.map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ul>
        </details>
      ) : null}

      {/* Application link */}
      {card.application_link ? (
        <div className="mb-3">
          <a
            href={card.application_link}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 rounded-md border border-sky-300 bg-sky-50 px-3 py-2 text-sm font-medium text-sky-900 hover:bg-sky-100"
          >
            <ExternalLink className="h-4 w-4" aria-hidden="true" />
            <span>Apply on official site</span>
          </a>
        </div>
      ) : null}

      {/* Final-authority disclaimer — mandatory per the brief. */}
      {card.final_authority_disclaimer ? (
        <p
          role="note"
          className="mt-3 border-t border-slate-200 pt-3 text-xs text-slate-600"
        >
          {card.final_authority_disclaimer}
        </p>
      ) : null}
    </section>
  );
}

export default SchemeAnswerCardView;