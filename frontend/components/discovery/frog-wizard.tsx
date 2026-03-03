"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  suggestDiscovery,
  getRequestBank,
  generateDocument,
  downloadBlob,
  CLAIM_TYPES,
  type BankCategoryInfo,
  type BankItemInfo,
  type DiscoveryToolType,
} from "@/lib/discovery-api";
import { useDiscovery } from "@/lib/discovery-context";
import WizardStepper from "./wizard-stepper";
import WizardNavigation from "./wizard-navigation";
import CaseInfoForm from "./case-info-form";
import ClaimSelector from "./claim-selector";
import PartyRoleSelector from "./party-role-selector";
import InterrogatoryPicker from "./interrogatory-picker";
import PreviewPanel from "./preview-panel";

// ── Types ────────────────────────────────────────────────────────────

interface FrogWizardProps {
  toolType: DiscoveryToolType;
  title: string;
  formLabel: string;
}

const STEPS = [
  { label: "Case Info" },
  { label: "Claims" },
  { label: "Sections" },
  { label: "Review" },
  { label: "Generate" },
];

// ── Claim label lookup ───────────────────────────────────────────────

const claimLabelMap: Record<string, string> = Object.fromEntries(
  CLAIM_TYPES.map((ct) => [ct.value, ct.label])
);

// ── Component ────────────────────────────────────────────────────────

export default function FrogWizard({
  toolType,
  title,
  formLabel,
}: FrogWizardProps) {
  const {
    state,
    setToolType,
    setStep,
    nextStep,
    prevStep,
    setPartyRole,
    toggleClaim,
    setCaseInfo,
    setPlaintiffs,
    setDefendants,
    setAttorney,
    setSelectedSections,
    setRespondingIsEntity,
    buildCaseInfo,
  } = useDiscovery();

  // Bank data
  const [categories, setCategories] = useState<BankCategoryInfo[]>([]);
  const [items, setItems] = useState<BankItemInfo[]>([]);
  const [suggested, setSuggested] = useState<string[]>([]);
  const [bankLoading, setBankLoading] = useState(false);
  const [suggestLoading, setSuggestLoading] = useState(false);

  // Generation state
  const [generating, setGenerating] = useState(false);
  const [genError, setGenError] = useState<string | null>(null);
  const [genSuccess, setGenSuccess] = useState(false);

  // Init tool type on mount — preserve case info + claims, reset tool-specific state
  useEffect(() => {
    if (state.toolType !== toolType) {
      setToolType(toolType);
      setStep(0);
      setSelectedSections([]);
    }
  }, [toolType]); // eslint-disable-line react-hooks/exhaustive-deps

  // Load bank when entering sections step
  useEffect(() => {
    if (state.currentStep === 2 && categories.length === 0) {
      setBankLoading(true);
      getRequestBank(toolType)
        .then((data) => {
          setCategories(data.categories);
          setItems(data.items);
        })
        .catch(() => {})
        .finally(() => setBankLoading(false));
    }
  }, [state.currentStep, toolType, categories.length]);

  // Load suggestions when entering sections step with claims
  useEffect(() => {
    if (state.currentStep === 2 && state.selectedClaims.length > 0) {
      setSuggestLoading(true);
      suggestDiscovery(state.selectedClaims, state.partyRole, toolType, {
        responding_is_entity: state.respondingIsEntity,
      })
        .then((data) => {
          const sections = data.suggested_sections.map((s) => s.section_number);
          setSuggested(sections);
          // Auto-select suggested if nothing selected yet
          if (state.selectedSections.length === 0) {
            setSelectedSections(sections);
          }
        })
        .catch(() => {})
        .finally(() => setSuggestLoading(false));
    }
  }, [state.currentStep, state.selectedClaims, state.partyRole, state.respondingIsEntity, toolType]); // eslint-disable-line react-hooks/exhaustive-deps

  // Validation per step
  const canProceed = useMemo(() => {
    switch (state.currentStep) {
      case 0: {
        const ci = state.caseInfo;
        return (
          ci.case_number.trim() !== "" &&
          ci.court_county.trim() !== "" &&
          ci.plaintiffs.some((p) => p.name.trim() !== "") &&
          ci.defendants.some((d) => d.name.trim() !== "") &&
          ci.attorney.name.trim() !== "" &&
          ci.attorney.address.trim() !== "" &&
          ci.attorney.city_state_zip.trim() !== "" &&
          ci.attorney.phone.trim() !== "" &&
          ci.attorney.email.trim() !== ""
        );
      }
      case 1:
        return state.selectedClaims.length > 0;
      case 2:
        return state.selectedSections.length > 0;
      case 3:
        return true; // review step
      case 4:
        return true; // generate step
      default:
        return false;
    }
  }, [state.currentStep, state.caseInfo, state.selectedClaims, state.selectedSections]);

  const handleGenerate = useCallback(async () => {
    setGenerating(true);
    setGenError(null);
    setGenSuccess(false);

    try {
      const caseInfo = buildCaseInfo();
      const { blob, filename } = await generateDocument({
        tool_type: toolType,
        case_info: caseInfo,
        selected_sections: state.selectedSections,
      });
      downloadBlob(blob, filename);
      setGenSuccess(true);
    } catch (err) {
      setGenError(err instanceof Error ? err.message : "Generation failed");
    } finally {
      setGenerating(false);
    }
  }, [buildCaseInfo, toolType, state.selectedSections]);

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="border-b border-border bg-surface px-4 py-4 sm:px-6">
        <h1 className="text-lg font-bold text-text-primary">{title}</h1>
        <p className="text-xs text-text-tertiary mt-1">{formLabel}</p>
        <div className="mt-3">
          <WizardStepper steps={STEPS} currentStep={state.currentStep} />
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-4 py-6 sm:px-6">
        <div className="mx-auto max-w-2xl">
          {/* Step 0: Case Info */}
          {state.currentStep === 0 && (
            <div className="animate-fade-in">
              <PartyRoleSelector
                value={state.partyRole}
                onChange={setPartyRole}
              />
              <div className="mt-4">
                <label className="flex items-center gap-2 text-sm text-text-secondary cursor-pointer mb-4">
                  <input
                    type="checkbox"
                    checked={state.respondingIsEntity}
                    onChange={(e) => setRespondingIsEntity(e.target.checked)}
                    className="rounded border-border"
                  />
                  Responding party is a business entity
                </label>
              </div>
              <CaseInfoForm
                caseInfo={state.caseInfo}
                onCaseInfoChange={setCaseInfo}
                onPlaintiffsChange={setPlaintiffs}
                onDefendantsChange={setDefendants}
                onAttorneyChange={setAttorney}
              />
            </div>
          )}

          {/* Step 1: Claims */}
          {state.currentStep === 1 && (
            <div className="animate-fade-in">
              <ClaimSelector
                selected={state.selectedClaims}
                onToggle={toggleClaim}
              />
            </div>
          )}

          {/* Step 2: Sections */}
          {state.currentStep === 2 && (
            <div className="animate-fade-in">
              {bankLoading || suggestLoading ? (
                <div className="flex items-center justify-center py-12">
                  <div className="text-sm text-text-tertiary">
                    Loading sections…
                  </div>
                </div>
              ) : (
                <InterrogatoryPicker
                  categories={categories}
                  items={items}
                  selected={state.selectedSections}
                  suggested={suggested}
                  onToggle={(id) => {
                    const next = state.selectedSections.includes(id)
                      ? state.selectedSections.filter((s) => s !== id)
                      : [...state.selectedSections, id];
                    setSelectedSections(next);
                  }}
                  onSetAll={setSelectedSections}
                />
              )}
            </div>
          )}

          {/* Step 3: Review */}
          {state.currentStep === 3 && (
            <div className="animate-fade-in">
              <PreviewPanel
                toolType={toolType}
                caseInfo={buildCaseInfo()}
                selectedClaims={state.selectedClaims}
                claimLabels={claimLabelMap}
                selectedSections={state.selectedSections}
                categories={categories}
                items={items}
              />
            </div>
          )}

          {/* Step 4: Generate */}
          {state.currentStep === 4 && (
            <div className="animate-fade-in space-y-4">
              <div className="rounded-lg border border-border p-6 text-center">
                <h3 className="text-lg font-semibold text-text-primary mb-2">
                  Ready to Generate
                </h3>
                <p className="text-sm text-text-secondary mb-6">
                  Your {formLabel} will be generated as an editable PDF with{" "}
                  {state.selectedSections.length} section
                  {state.selectedSections.length !== 1 ? "s" : ""} selected.
                </p>

                <button
                  type="button"
                  onClick={handleGenerate}
                  disabled={generating}
                  className={`min-h-[44px] rounded-lg px-8 py-3 text-sm font-semibold transition-colors ${
                    generating
                      ? "cursor-not-allowed bg-accent/30 text-text-tertiary"
                      : genSuccess
                        ? "bg-verified-bg text-verified-text border border-verified-border"
                        : "bg-accent text-white hover:bg-accent-hover"
                  }`}
                >
                  {generating ? (
                    <span className="flex items-center gap-2">
                      <svg
                        className="h-4 w-4 animate-spin"
                        viewBox="0 0 24 24"
                        fill="none"
                      >
                        <circle
                          className="opacity-25"
                          cx="12"
                          cy="12"
                          r="10"
                          stroke="currentColor"
                          strokeWidth="4"
                        />
                        <path
                          className="opacity-75"
                          fill="currentColor"
                          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                        />
                      </svg>
                      Generating PDF…
                    </span>
                  ) : genSuccess ? (
                    "Downloaded!"
                  ) : (
                    "Generate & Download PDF"
                  )}
                </button>

                {genError && (
                  <p className="mt-4 rounded-lg border border-error-border bg-error-bg px-3 py-2 text-xs text-error-text">
                    {genError}
                  </p>
                )}

                {genSuccess && (
                  <p className="mt-4 text-sm text-verified-text">
                    Your PDF has been downloaded. You can open it in any PDF
                    editor to make further changes.
                  </p>
                )}
              </div>

              <p className="rounded-lg border border-warning-border bg-warning-bg px-4 py-3 text-xs text-warning-text">
                This tool generates discovery documents based on your
                selections. It does not constitute legal advice. Generated
                documents should be reviewed by a licensed California attorney
                before filing.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Navigation */}
      <WizardNavigation
        currentStep={state.currentStep}
        totalSteps={STEPS.length}
        onBack={prevStep}
        onNext={nextStep}
        nextDisabled={!canProceed}
        onGenerate={state.currentStep === STEPS.length - 1 ? handleGenerate : undefined}
        generateDisabled={generating}
        generating={generating}
      />
    </div>
  );
}
