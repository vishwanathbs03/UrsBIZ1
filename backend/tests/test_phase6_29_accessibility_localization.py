"""Phase 6.29 — Accessibility, Localization & Complete Kannada Parity Test Suite.

Verifies:
1. Complete Kannada and English bilingual dictionary parity for:
   - All 20+ navigation routes and 7 navigation groups
   - Core MSME financial vocabulary (DSO, Working Capital, Cash Flow, Gross Margin, Net Profit, etc.)
   - All RBAC roles (Owner, Administrator, Manager, Analyst, Viewer)
   - All decision workflow statuses (Draft, Proposed, Pending Approval, Approved, Rejected, Executed)
   - All frozen feedback evaluation categories (Helpful, Incorrect, Missing Evidence, Outdated, Difficult)
2. Indian currency formatting (INR / ₹) with Indian numbering grouping (Lakhs / Crores)
3. Standardized calendar date formatting strictly conforming to Indian business convention (DD-MM-YYYY)
4. Kannada font embedding integrity and Unicode glyph coverage in the ReportLab engine
5. WCAG AA accessibility compliance contracts and skip-link labels
6. Deterministic Kannada fallback currency and numerical preservation
"""

from pathlib import Path
import pytest
from app.services.report_export_service import (
    _BUNDLED_KANNADA_FONT,
    _KANNADA_FONT_REGISTERED,
    _UNICODE_FONT_NAME,
    check_kannada_glyph_coverage,
)
from app.services.ai.providers.base import (
    AssistantContext,
    AssistantContextDna,
    AssistantContextScore,
    AssistantContextRecommendation,
    AssistantContextRoadmap,
    AssistantContextRule,
    AssistantContextInsight,
    AssistantRequest,
    DeterministicFallbackProvider,
)


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def test_bundled_kannada_font_exists_and_registered():
    """Verify bundled NotoSansKannada-Regular font exists and is registered in ReportLab."""
    assert _BUNDLED_KANNADA_FONT.exists(), f"Bundled font missing at {_BUNDLED_KANNADA_FONT}"
    assert _BUNDLED_KANNADA_FONT.stat().st_size > 100_000, "Font file appears truncated"
    assert _KANNADA_FONT_REGISTERED is True, "Kannada font was not registered in ReportLab"
    assert _UNICODE_FONT_NAME == "UrsBizKannada"


def test_kannada_glyph_coverage_for_business_terms():
    """Verify ReportLab Unicode font has 100% glyph coverage for complex Kannada ligatures."""
    sample_phrases = [
        "ಶ್ರೀ ಬಸವೇಶ್ವರ ಎಂಟರ್‌ಪ್ರೈಸಸ್ (Basaveshwara Enterprises)",
        "ಕಾರ್ಯನಿರತ ಬಂಡವಾಳ ಮತ್ತು ನಗದು ಹರಿವು",
        "ವಸೂಲಾತಿ ಬಾಕಿ ದಿನಗಳು (DSO): 45 ದಿನಗಳು",
        "ಒಟ್ಟು ಲಾಭಾಂಶ ಮತ್ತು ನಿವ್ವಳ ಲಾಭ: ₹12,34,567.89",
        "ದಾಸ್ತಾನು ವಹಿವಾಟು ದರ ಹಾಗೂ ಗ್ರಾಹಕರ ಸಾಂದ್ರತೆ",
        "ಅನುಮೋದಿತ • ತಿರಸ್ಕೃತ • ಕಾರ್ಯಗತಗೊಳಿಸಲಾಗಿದೆ",
        "ಶೂನ್ಯ-ಧಾರಣ ದತ್ತಾಂಶ ಸಾರ್ವಭೌಮತ್ವ",
    ]
    for phrase in sample_phrases:
        covered, missing = check_kannada_glyph_coverage(_UNICODE_FONT_NAME, phrase)
        assert covered is True, f"Missing glyphs for phrase '{phrase}': {missing}"


def test_frontend_translations_file_integrity(repo_root: Path):
    """Verify frontend translations file contains complete English and Kannada dictionaries."""
    trans_file = repo_root / "frontend" / "i18n" / "translations.ts"
    assert trans_file.exists(), f"Missing translations file at {trans_file}"
    content = trans_file.read_text(encoding="utf-8")

    # 1. Navigation Routes & Groups Parity
    nav_keys = [
        "home", "dashboard", "business", "intelligence", "sales",
        "analytics", "predictiveAnalytics", "insights", "dataConfidence",
        "metrics", "advisor", "actionBoard", "decisionWorkbench",
        "whatIf", "goals", "schemes", "assistant", "reports",
        "collaboration", "integrations", "notifications",
        "groupOverview", "groupBusiness", "groupIntelligence",
        "groupActions", "groupDiscover", "groupAssistant", "groupWorkspace",
        "badgeNew", "badgeAi", "badgeRbac", "more",
    ]
    for key in nav_keys:
        assert f"{key}:" in content, f"Missing nav key: {key}"

    # 2. Core Financial Terms
    financial_terms = [
        "dso", "workingCapital", "cashFlow", "grossMargin", "netProfit",
        "revenue", "operatingExpenses", "accountsReceivable", "accountsPayable",
        "inventoryTurnover", "burnRate", "customerConcentration", "cashRunway",
    ]
    for term in financial_terms:
        assert f"{term}:" in content, f"Missing financial term: {term}"

    # 3. RBAC Roles
    roles = ["owner", "administrator", "manager", "analyst", "viewer"]
    for role in roles:
        assert f"{role}:" in content, f"Missing role: {role}"

    # 4. Decisions Workflow
    decisions = [
        "draft", "proposed", "pendingApproval", "approved", "rejected",
        "executed", "cancelled", "newDecision", "requestApproval",
        "approve", "reject", "soleOwnerAutoApproved",
    ]
    for dec in decisions:
        assert f"{dec}:" in content, f"Missing decision term: {dec}"

    # 5. Feedback Categories (Frozen 5)
    feedback_terms = [
        "helpful", "incorrectInformation", "missingEvidence",
        "outdatedData", "difficultToUnderstand", "qualityScore",
        "helpfulnessRate", "totalFeedback", "groundedVsFallback",
        "zeroRetention", "unvote",
    ]
    for fb in feedback_terms:
        assert f"{fb}:" in content, f"Missing feedback term: {fb}"

    # 6. Accessibility & Usability (a11y)
    a11y_keys = [
        "skipToContent", "openNavigation", "closeNavigation",
        "toggleTheme", "languageSelect", "currentLanguage",
        "externalLink", "breadcrumb", "loadingState",
    ]
    for a11y in a11y_keys:
        assert f"{a11y}:" in content, f"Missing a11y key: {a11y}"


def test_formatters_library_exports_and_contracts(repo_root: Path):
    """Verify formatters.ts exists and implements Indian formatting contracts."""
    fmt_file = repo_root / "frontend" / "lib" / "formatters.ts"
    assert fmt_file.exists(), f"Missing formatters.ts at {fmt_file}"
    content = fmt_file.read_text(encoding="utf-8")

    # Essential exported functions
    assert "export function formatINR(" in content
    assert "export function formatDate(" in content
    assert "export function formatPercentage(" in content
    assert "export function formatDSO(" in content
    assert "export function formatRelativeTime(" in content

    # Indian number grouping and bilingual units
    assert "1_00_00_000" in content  # 1 Crore
    assert "1_00_000" in content     # 1 Lakh
    assert "1_000" in content        # 1 Thousand
    assert "ಕೋಟಿ" in content         # Kannada Crore
    assert "ಲಕ್ಷ" in content         # Kannada Lakh
    assert "DD-MM-YYYY" in content   # Indian date format convention
    assert "ದಿನಗಳು" in content       # Kannada DSO unit


def test_layout_skip_to_content_accessibility(repo_root: Path):
    """Verify RootLayout includes accessible skip-to-content link in both English & Kannada."""
    layout_file = repo_root / "frontend" / "app" / "layout.tsx"
    assert layout_file.exists()
    content = layout_file.read_text(encoding="utf-8")

    assert 'href="#main-content"' in content
    assert "Skip to content / ಮುಖ್ಯ ವಿಷಯಕ್ಕೆ ತೆರಳಿ" in content
    assert "sr-only focus:not-sr-only" in content


def test_kannada_tailwind_font_family_configuration(repo_root: Path):
    """Verify tailwind.config.ts configures Noto Sans Kannada in fontFamily."""
    tailwind_file = repo_root / "frontend" / "tailwind.config.ts"
    assert tailwind_file.exists()
    content = tailwind_file.read_text(encoding="utf-8")

    assert "kannada:" in content
    assert "Noto Sans Kannada" in content


def test_deterministic_kannada_fallback_currency_and_evidence():
    """Verify DeterministicFallbackProvider renders fluent Kannada with ₹ preservation."""
    context = AssistantContext(
        business_id=42,
        legal_name="ಬಸವೇಶ್ವರ ಟೆಕ್ಸ್‌ಟೈಲ್ಸ್",
        trade_name="Basaveshwara Textiles",
        industry="Apparel",
        location="Bengaluru, Karnataka",
        business_type="Sole Proprietorship",
        employee_count="12",
        annual_revenue_inr=8500000,   # ₹85 Lakhs
        target_revenue_inr=12000000,  # ₹1.2 Crore
        overall_business_score=72,
        band="Established",
        dna=AssistantContextDna(archetype_key="quality_artisan", archetype_title="Artisan", match_score=85),
        scores=(
            AssistantContextScore(key="financial", title="Financial Health", score=78, level="Strong"),
            AssistantContextScore(key="market", title="Market Position", score=72, level="Strong"),
        ),
        recommendations=(
            AssistantContextRecommendation(
                id="rec_expand_stores",
                title="Expand Retail Distribution",
                category="growth",
                priority="High",
                estimated_score_gain=10,
                estimated_timeline="90 days",
                estimated_roi=500000,
            ),
        ),
        roadmap=(
            AssistantContextRoadmap(
                id="ms-01",
                title="30-day invoice cycle",
                phase="Q1",
                priority="High",
                estimated_start_order=1,
                completion_percentage=50,
                expected_score_improvement=5,
            ),
        ),
        rules=(
            AssistantContextRule(
                id="RULE-REV-01",
                title="Revenue Target Gap",
                category="financial",
                priority="Medium",
                estimated_impact=-5,
                reason="Revenue on track",
            ),
        ),
        insights=(
            AssistantContextInsight(
                id="INS-01",
                title="Working Capital Buffer",
                priority="Low",
                confidence=90,
            ),
        ),
    )

    req = AssistantRequest(
        user_prompt="ನಮ್ಮ ಪ್ರಸ್ತುತ ಆದಾಯ ಎಷ್ಟು?",
        context=context,
        language="kn",
    )
    fb = DeterministicFallbackProvider()
    resp = fb.complete(req)

    # 1. Fallback flag must be stamped
    assert resp.generation.fallback_used is True

    # 2. Currency symbol ₹ and exact rupee amounts must be preserved
    assert "₹" in resp.body

    # 3. Kannada phrasing and headers must be present
    assert "ಒಟ್ಟಾರೆ ವ್ಯವಹಾರ ಸ್ಕೋರ್:" in resp.body or "ವ್ಯವಹಾರ" in resp.body
    assert resp.generation.language == "kn"


def test_formatter_runtime_edge_cases_and_kannada_grammar(repo_root: Path):
    """Verify formatters.ts executes with 100% precision for edge cases and Kannada grammar."""
    import subprocess

    test_script = repo_root / "frontend" / "scripts" / "test_formatters.ts"
    assert test_script.exists(), f"Formatter test script missing at {test_script}"

    res = subprocess.run(
        ["npx", "--yes", "tsx", str(test_script)],
        cwd=repo_root,
        capture_output=True,
        text=True,
        shell=True,
    )
    assert res.returncode == 0, f"Formatter runtime check failed:\nSTDOUT: {res.stdout}\nSTDERR: {res.stderr}"
    assert "ALL_FORMATTER_RUNTIME_CHECKS_PASSED" in res.stdout


def test_wcag_modal_dialog_escape_handlers_and_touch_targets(repo_root: Path):
    """Verify all modal dialogs implement Escape key listeners and >=44px touch targets."""
    # 1. ReviewApprovalModal.tsx
    review_modal = repo_root / "frontend" / "features" / "collaboration" / "ReviewApprovalModal.tsx"
    assert review_modal.exists()
    rev_content = review_modal.read_text(encoding="utf-8")
    assert 'role="dialog"' in rev_content
    assert 'aria-modal="true"' in rev_content
    assert 'e.key === "Escape"' in rev_content
    assert "min-h-[44px] min-w-[44px]" in rev_content

    # 2. MetricsDictionaryView.tsx
    metrics_view = repo_root / "frontend" / "features" / "metrics-dictionary" / "components" / "MetricsDictionaryView.tsx"
    assert metrics_view.exists()
    met_content = metrics_view.read_text(encoding="utf-8")
    assert 'role="dialog"' in met_content
    assert 'aria-modal="true"' in met_content
    assert 'e.key === "Escape"' in met_content
    assert "min-h-[44px] min-w-[44px]" in met_content

    # 3. QualityEvaluationPanel.tsx
    eval_panel = repo_root / "frontend" / "features" / "assistant" / "QualityEvaluationPanel.tsx"
    assert eval_panel.exists()
    eval_content = eval_panel.read_text(encoding="utf-8")
    assert 'e.key === "Escape"' in eval_content
    assert "min-h-[44px]" in eval_content

    # 4. InviteMemberModal.tsx
    invite_modal = repo_root / "frontend" / "features" / "collaboration" / "InviteMemberModal.tsx"
    assert invite_modal.exists()
    inv_content = invite_modal.read_text(encoding="utf-8")
    assert 'role="dialog"' in inv_content
    assert 'aria-modal="true"' in inv_content
    assert 'e.key === "Escape"' in inv_content
    assert "min-h-[44px] min-w-[44px]" in inv_content

    # 5. ReportConfigModal.tsx
    cfg_modal = repo_root / "frontend" / "features" / "reports" / "ReportConfigModal.tsx"
    assert cfg_modal.exists()
    cfg_content = cfg_modal.read_text(encoding="utf-8")
    assert 'role="dialog"' in cfg_content
    assert 'aria-modal="true"' in cfg_content
    assert 'e.key === "Escape"' in cfg_content
    assert "min-h-[44px] min-w-[44px]" in cfg_content

    # 6. ReportPreviewModal.tsx
    prev_modal = repo_root / "frontend" / "features" / "reports" / "ReportPreviewModal.tsx"
    assert prev_modal.exists()
    prev_content = prev_modal.read_text(encoding="utf-8")
    assert 'role="dialog"' in prev_content
    assert 'aria-modal="true"' in prev_content
    assert 'e.key === "Escape"' in prev_content
    assert "min-h-[44px] min-w-[44px]" in prev_content

    # 7. ConnectionModal.tsx
    conn_modal = repo_root / "frontend" / "features" / "integrations" / "ConnectionModal.tsx"
    assert conn_modal.exists()
    conn_content = conn_modal.read_text(encoding="utf-8")
    assert 'role="dialog"' in conn_content
    assert 'aria-modal="true"' in conn_content
    assert 'e.key === "Escape"' in conn_content
    assert "min-h-[44px] min-w-[44px]" in conn_content


def test_modal_inventory_and_escape_handlers(repo_root: Path):
    """Verify modal inventory scanner runs and all core interactive modals enforce Escape key listeners."""
    import sys
    backend_path = str(repo_root / "backend")
    if backend_path not in sys.path:
        sys.path.insert(0, backend_path)
    from scripts.scan_modals import scan_modals

    items = scan_modals()
    assert len(items) >= 15, f"Expected >= 15 modal/overlay candidates, got {len(items)}"

    escape_enabled = {it["file"].replace("\\", "/") for it in items if it["has_escape"]}
    required_escapes = [
        "components/common/GlobalSearchModal.tsx",
        "components/common/SlideOver.tsx",
        "components/layout/MobileDrawer.tsx",
        "components/ui/sheet.tsx",
        "features/collaboration/ReviewApprovalModal.tsx",
        "features/collaboration/InviteMemberModal.tsx",
        "features/metrics-dictionary/components/MetricsDictionaryView.tsx",
        "features/reports/ReportConfigModal.tsx",
        "features/reports/ReportPreviewModal.tsx",
        "features/integrations/ConnectionModal.tsx",
        "features/advisor/ScenarioSimulationModal.tsx",
    ]
    for req in required_escapes:
        assert req in escape_enabled, f"Missing Escape handler in {req}"
