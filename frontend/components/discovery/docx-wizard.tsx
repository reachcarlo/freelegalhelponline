"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  suggestDiscovery,
  getRequestBank,
  getDefinitions,
  generateDocument,
  downloadBlob,
  CLAIM_TYPES,
  type BankCategoryInfo,
  type DiscoveryRequest,
  type DiscoveryToolType,
} from "@/lib/discovery-api";
import { useDiscovery } from "@/lib/discovery-context";
import WizardStepper from "./wizard-stepper";
import WizardNavigation from "./wizard-navigation";
import CaseInfoForm from "./case-info-form";
import ClaimSelector from "./claim-selector";
import PartyRoleSelector from "./party-role-selector";
import RequestBuilder from "./request-builder";
import DefinitionEditor from "./definition-editor";
import PreviewPanel from "./preview-panel";

// ── Types ────────────────────────────────────────────────────────────

interface DocxWizardProps {
  toolType: DiscoveryToolType;
  title: string;
  toolLabel: string;
  /** Request limit (35 for SROGs, null for RFPDs) */
  limit: number | null;
  /** For RFAs: only count "fact" toward limit */
  limitType?: "fact" | null;
  limitLabel?: string;
  /** Show production instructions step (RFPDs) */
  showProductionInstructions?: boolean;
}

// ── Claim label lookup ───────────────────────────────────────────────

const claimLabelMap: Record<string, string> = Object.fromEntries(
  CLAIM_TYPES.map((ct) => [ct.value, ct.label])
);

// ── Component ────────────────────────────────────────────────────────

export default function DocxWizard({
  toolType,
  title,
  toolLabel,
  limit,
  limitType,
  limitLabel = "requests",
  showProductionInstructions = false,
}: DocxWizardProps) {
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
    setSelectedRequests,
    setDefinitions,
    setDefinition,
    removeDefinition,
    setIncludeDefinitions,
    resetState,
    buildCaseInfo,
  } = useDiscovery();

  // Bank data
  const [categories, setCategories] = useState<BankCategoryInfo[]>([]);
  const [suggestedCategories, setSuggestedCategories] = useState<string[]>([]);
  const [bankLoading, setBankLoading] = useState(false);
  const [suggestLoading, setSuggestLoading] = useState(false);
  const [defsLoaded, setDefsLoaded] = useState(false);

  // Production instructions (RFPDs)
  const [productionInstructions, setProductionInstructions] = useState("");

  // Generation state
  const [generating, setGenerating] = useState(false);
  const [genError, setGenError] = useState<string | null>(null);
  const [genSuccess, setGenSuccess] = useState(false);

  // Steps are dynamic based on tool
  const steps = useMemo(() => {
    const base = [
      { label: "Case Info" },
      { label: "Claims" },
      { label: "Requests" },
    ];
    if (showProductionInstructions) {
      base.push({ label: "Instructions" });
    }
    base.push({ label: "Definitions" });
    base.push({ label: "Review" });
    base.push({ label: "Generate" });
    return base;
  }, [showProductionInstructions]);

  // Map logical step names to indices
  const stepIndex = useMemo(() => {
    const map: Record<string, number> = {};
    steps.forEach((s, i) => (map[s.label] = i));
    return map;
  }, [steps]);

  // Set tool type on mount — state always starts fresh (no hydration)
  useEffect(() => {
    setToolType(toolType);
  }, [toolType, setToolType]);

  // Load bank when entering requests step
  useEffect(() => {
    if (state.currentStep === stepIndex["Requests"] && categories.length === 0) {
      setBankLoading(true);
      getRequestBank(toolType)
        .then((data) => {
          setCategories(data.categories);
          // Convert bank items to DiscoveryRequest format with is_selected=false initially
          if (state.selectedRequests.length === 0) {
            const reqs: DiscoveryRequest[] = data.items.map((item) => ({
              id: item.id,
              text: item.text,
              category: item.category,
              is_selected: false,
              is_custom: false,
              order: item.order,
              notes: null,
              rfa_type: item.rfa_type || null,
            }));
            setSelectedRequests(reqs);
          }
        })
        .catch(() => {})
        .finally(() => setBankLoading(false));
    }
  }, [state.currentStep, toolType, categories.length, stepIndex]); // eslint-disable-line react-hooks/exhaustive-deps

  // Load suggestions when entering requests step
  useEffect(() => {
    if (
      state.currentStep === stepIndex["Requests"] &&
      state.selectedClaims.length > 0
    ) {
      setSuggestLoading(true);
      suggestDiscovery(state.selectedClaims, state.partyRole, toolType)
        .then((data) => {
          const cats = data.suggested_categories.map((c) => c.category);
          setSuggestedCategories(cats);
          // Auto-select suggested category requests if nothing selected yet
          if (
            state.selectedRequests.length > 0 &&
            !state.selectedRequests.some((r) => r.is_selected)
          ) {
            const catSet = new Set(cats);
            setSelectedRequests(
              state.selectedRequests.map((r) => ({
                ...r,
                is_selected: catSet.has(r.category),
              }))
            );
          }
        })
        .catch(() => {})
        .finally(() => setSuggestLoading(false));
    }
  }, [state.currentStep, state.selectedClaims, state.partyRole, toolType, stepIndex]); // eslint-disable-line react-hooks/exhaustive-deps

  // Load standard definitions when entering definitions step
  useEffect(() => {
    if (state.currentStep === stepIndex["Definitions"] && !defsLoaded) {
      getDefinitions()
        .then((data) => {
          // Only set if user hasn't added custom ones yet
          if (Object.keys(state.definitions).length === 0) {
            const defs: Record<string, string> = {};
            for (const d of data.definitions) {
              defs[d.term] = d.definition;
            }
            setDefinitions(defs);
          }
          if (showProductionInstructions && !productionInstructions) {
            setProductionInstructions(data.production_instructions);
          }
          setDefsLoaded(true);
        })
        .catch(() => {});
    }
  }, [state.currentStep, defsLoaded, stepIndex]); // eslint-disable-line react-hooks/exhaustive-deps

  // Validation per step
  const canProceed = useMemo(() => {
    const step = state.currentStep;
    if (step === stepIndex["Case Info"]) {
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
    if (step === stepIndex["Claims"]) {
      return state.selectedClaims.length > 0;
    }
    if (step === stepIndex["Requests"]) {
      return state.selectedRequests.some((r) => r.is_selected);
    }
    return true;
  }, [state.currentStep, state.caseInfo, state.selectedClaims, state.selectedRequests, stepIndex]);

  const handleGenerate = useCallback(async () => {
    setGenerating(true);
    setGenError(null);
    setGenSuccess(false);

    try {
      const caseInfo = buildCaseInfo();
      const customDefs =
        Object.keys(state.definitions).length > 0
          ? state.definitions
          : undefined;

      const { blob, filename } = await generateDocument({
        tool_type: toolType,
        case_info: caseInfo,
        selected_requests: state.selectedRequests.filter((r) => r.is_selected),
        include_definitions: state.includeDefinitions,
        custom_definitions: customDefs,
      });
      downloadBlob(blob, filename);
      setGenSuccess(true);
    } catch (err) {
      setGenError(err instanceof Error ? err.message : "Generation failed");
    } finally {
      setGenerating(false);
    }
  }, [buildCaseInfo, toolType, state.selectedRequests, state.definitions, state.includeDefinitions]);

  // Current step label
  const currentStepLabel = steps[state.currentStep]?.label || "";

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="border-b border-border bg-surface px-4 py-4 sm:px-6">
        <Link
          href="/tools/discovery"
          className="inline-flex items-center gap-1 text-xs text-text-tertiary hover:text-accent"
          data-testid="breadcrumb-discovery"
        >
          &larr; Discovery Tools
        </Link>
        <h1 className="text-lg font-bold text-text-primary mt-1">{title}</h1>
        <p className="text-xs text-text-tertiary mt-1">{toolLabel}</p>
        <div className="mt-3">
          <WizardStepper steps={steps} currentStep={state.currentStep} />
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-4 py-6 sm:px-6">
        <div className="mx-auto max-w-2xl">
          {/* Case Info */}
          {currentStepLabel === "Case Info" && (
            <div className="animate-fade-in">
              <PartyRoleSelector
                value={state.partyRole}
                onChange={setPartyRole}
              />
              <div className="mt-4">
                <CaseInfoForm
                  caseInfo={state.caseInfo}
                  onCaseInfoChange={setCaseInfo}
                  onPlaintiffsChange={setPlaintiffs}
                  onDefendantsChange={setDefendants}
                  onAttorneyChange={setAttorney}
                />
              </div>
            </div>
          )}

          {/* Claims */}
          {currentStepLabel === "Claims" && (
            <div className="animate-fade-in">
              <ClaimSelector
                selected={state.selectedClaims}
                onToggle={toggleClaim}
              />
            </div>
          )}

          {/* Requests */}
          {currentStepLabel === "Requests" && (
            <div className="animate-fade-in">
              {bankLoading || suggestLoading ? (
                <div className="flex items-center justify-center py-12">
                  <div className="text-sm text-text-tertiary">
                    Loading request bank…
                  </div>
                </div>
              ) : (
                <RequestBuilder
                  requests={state.selectedRequests}
                  categories={categories}
                  suggestedCategories={suggestedCategories}
                  onRequestsChange={setSelectedRequests}
                  limit={limit}
                  limitType={limitType}
                  limitLabel={limitLabel}
                  toolLabel={toolLabel}
                />
              )}
            </div>
          )}

          {/* Production Instructions (RFPDs only) */}
          {currentStepLabel === "Instructions" && (
            <div className="animate-fade-in">
              <h3 className="text-sm font-semibold text-text-primary mb-3">
                Production Instructions
              </h3>
              <p className="text-xs text-text-tertiary mb-4">
                Standard production instructions are included below. Edit as
                needed for your case.
              </p>
              <textarea
                value={productionInstructions}
                onChange={(e) => setProductionInstructions(e.target.value)}
                rows={12}
                className="w-full rounded-lg border border-border bg-input-bg px-3 py-2 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent focus:outline-none resize-y"
              />
            </div>
          )}

          {/* Definitions */}
          {currentStepLabel === "Definitions" && (
            <div className="animate-fade-in">
              <DefinitionEditor
                definitions={state.definitions}
                onSetDefinition={setDefinition}
                onRemoveDefinition={removeDefinition}
                includeDefinitions={state.includeDefinitions}
                onIncludeChange={setIncludeDefinitions}
              />
            </div>
          )}

          {/* Review */}
          {currentStepLabel === "Review" && (
            <div className="animate-fade-in">
              <PreviewPanel
                toolType={toolType}
                caseInfo={buildCaseInfo()}
                selectedClaims={state.selectedClaims}
                claimLabels={claimLabelMap}
                selectedRequests={state.selectedRequests}
                definitions={state.definitions}
                includeDefinitions={state.includeDefinitions}
              />
            </div>
          )}

          {/* Generate */}
          {currentStepLabel === "Generate" && (() => {
            const selectedReqs = state.selectedRequests.filter((r) => r.is_selected);
            const limitedCount = limitType === "fact"
              ? selectedReqs.filter((r) => r.rfa_type === "fact").length
              : selectedReqs.length;
            const needsDeclaration = limit !== null && limitedCount > limit;

            return (
            <div className="animate-fade-in space-y-4">
              {needsDeclaration && (
                <div className="rounded-lg border border-warning-border bg-warning-bg px-4 py-3 text-sm text-warning-text">
                  <p className="font-semibold">Declaration of Necessity Required</p>
                  <p className="mt-1 text-xs">
                    You have {limitedCount} {limitLabel} selected, exceeding the
                    {" "}{limit}-question limit. Per{" "}
                    {toolLabel === "RFAs" ? "CCP \u00A7 2033.050" : "CCP \u00A7 2030.050"},
                    you must file a separate Declaration of Necessity stating that
                    each additional question is warranted by the complexity or
                    quantity of existing and potential issues in the case.
                  </p>
                </div>
              )}
              <div className="rounded-lg border border-border p-6 text-center">
                <h3 className="text-lg font-semibold text-text-primary mb-2">
                  Ready to Generate
                </h3>
                <p className="text-sm text-text-secondary mb-6">
                  Your {toolLabel} will be generated as an editable Word document
                  with {selectedReqs.length} request
                  {selectedReqs.length !== 1 ? "s" : ""} selected.
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
                      Generating…
                    </span>
                  ) : genSuccess ? (
                    "Downloaded!"
                  ) : (
                    "Generate & Download .docx"
                  )}
                </button>

                {genError && (
                  <p className="mt-4 rounded-lg border border-error-border bg-error-bg px-3 py-2 text-xs text-error-text">
                    {genError}
                  </p>
                )}

                {genSuccess && (
                  <>
                    <p className="mt-4 text-sm text-verified-text">
                      Your document has been downloaded. Open it in Word or
                      LibreOffice to review and finalize.
                    </p>
                    <div className="mt-4 flex flex-wrap items-center justify-center gap-3">
                      <button
                        type="button"
                        data-testid="start-over"
                        onClick={() => {
                          resetState();
                          setToolType(toolType);
                        }}
                        className="rounded-lg border border-border px-6 py-2 text-sm font-medium text-text-secondary hover:bg-surface transition-colors"
                      >
                        Start Over
                      </button>
                      <Link
                        href="/tools/discovery"
                        className="rounded-lg px-6 py-2 text-sm font-medium text-text-tertiary hover:text-accent transition-colors"
                      >
                        Back to Discovery Tools
                      </Link>
                    </div>
                  </>
                )}
              </div>

              <p className="rounded-lg border border-warning-border bg-warning-bg px-4 py-3 text-xs text-warning-text">
                This tool generates discovery documents based on your
                selections. It does not constitute legal advice. Generated
                documents should be reviewed by a licensed California attorney
                before filing.
              </p>
            </div>
            );
          })()}
        </div>
      </div>

      {/* Navigation */}
      <WizardNavigation
        currentStep={state.currentStep}
        totalSteps={steps.length}
        onBack={prevStep}
        onNext={nextStep}
        nextDisabled={!canProceed}
        onGenerate={
          state.currentStep === steps.length - 1 ? handleGenerate : undefined
        }
        generateDisabled={generating}
        generating={generating}
      />
    </div>
  );
}
