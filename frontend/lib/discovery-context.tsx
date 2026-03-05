"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import type {
  AttorneyInfo,
  CaseInfo,
  DiscoveryRequest,
  DiscoveryToolType,
  PartyInfo,
  PartyRole,
} from "@/lib/discovery-api";

// ── State shape ──────────────────────────────────────────────────────

export interface DiscoveryState {
  toolType: DiscoveryToolType | null;
  currentStep: number;
  partyRole: PartyRole;
  selectedClaims: string[];
  caseInfo: CaseInfo;
  /** Selected FROG section numbers (e.g. ["1.1", "2.1"]) */
  selectedSections: string[];
  /** Selected requests for SROGs/RFPDs/RFAs */
  selectedRequests: DiscoveryRequest[];
  /** Custom legal definitions (term → definition) */
  definitions: Record<string, string>;
  includeDefinitions: boolean;
  adverseActions: string[];
  respondingIsEntity: boolean;
}

const DEFAULT_ATTORNEY: AttorneyInfo = {
  name: "",
  sbn: "",
  address: "",
  city_state_zip: "",
  phone: "",
  email: "",
  firm_name: null,
  fax: null,
  is_pro_per: false,
  attorney_for: "",
};

const DEFAULT_PARTY: PartyInfo = {
  name: "",
  is_entity: false,
  entity_type: null,
};

const DEFAULT_CASE_INFO: CaseInfo = {
  case_number: "",
  court_county: "",
  party_role: "plaintiff",
  plaintiffs: [{ ...DEFAULT_PARTY }],
  defendants: [{ ...DEFAULT_PARTY }],
  attorney: { ...DEFAULT_ATTORNEY },
  court_name: "Superior Court of California",
  court_branch: null,
  court_address: null,
  court_city_zip: null,
  judge_name: null,
  department: null,
  complaint_filed_date: null,
  trial_date: null,
  does_included: true,
  set_number: 1,
};

const DEFAULT_STATE: DiscoveryState = {
  toolType: null,
  currentStep: 0,
  partyRole: "plaintiff",
  selectedClaims: [],
  caseInfo: { ...DEFAULT_CASE_INFO },
  selectedSections: [],
  selectedRequests: [],
  definitions: {},
  includeDefinitions: true,
  adverseActions: [],
  respondingIsEntity: false,
};

const STORAGE_KEY = "eh-discovery-state";

// ── Context value ────────────────────────────────────────────────────

interface DiscoveryContextValue {
  state: DiscoveryState;
  setToolType: (t: DiscoveryToolType) => void;
  setStep: (n: number) => void;
  nextStep: () => void;
  prevStep: () => void;
  setPartyRole: (r: PartyRole) => void;
  setSelectedClaims: (claims: string[]) => void;
  toggleClaim: (claim: string) => void;
  setCaseInfo: (info: Partial<CaseInfo>) => void;
  setPlaintiffs: (parties: PartyInfo[]) => void;
  setDefendants: (parties: PartyInfo[]) => void;
  setAttorney: (info: Partial<AttorneyInfo>) => void;
  setSelectedSections: (sections: string[]) => void;
  toggleSection: (section: string) => void;
  setSelectedRequests: (requests: DiscoveryRequest[]) => void;
  toggleRequest: (id: string) => void;
  setDefinitions: (defs: Record<string, string>) => void;
  setDefinition: (term: string, definition: string) => void;
  removeDefinition: (term: string) => void;
  setIncludeDefinitions: (include: boolean) => void;
  setAdverseActions: (actions: string[]) => void;
  setRespondingIsEntity: (v: boolean) => void;
  resetState: () => void;
  /** Build the CaseInfo with partyRole synced from state */
  buildCaseInfo: () => CaseInfo;
}

const DiscoveryContext = createContext<DiscoveryContextValue | null>(null);

// ── Provider ─────────────────────────────────────────────────────────

export function DiscoveryProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<DiscoveryState>(DEFAULT_STATE);

  // Clear sessionStorage on unmount so switching tools or leaving
  // the workflow always starts fresh at step 0.
  useEffect(() => {
    return () => {
      try {
        sessionStorage.removeItem(STORAGE_KEY);
      } catch {
        // ignore
      }
    };
  }, []);

  const update = useCallback(
    (partial: Partial<DiscoveryState>) =>
      setState((prev) => ({ ...prev, ...partial })),
    []
  );

  const setToolType = useCallback(
    (t: DiscoveryToolType) => update({ toolType: t }),
    [update]
  );

  const setStep = useCallback(
    (n: number) => update({ currentStep: n }),
    [update]
  );

  const nextStep = useCallback(
    () => setState((prev) => ({ ...prev, currentStep: prev.currentStep + 1 })),
    []
  );

  const prevStep = useCallback(
    () =>
      setState((prev) => ({
        ...prev,
        currentStep: Math.max(0, prev.currentStep - 1),
      })),
    []
  );

  const setPartyRole = useCallback(
    (r: PartyRole) =>
      setState((prev) => ({
        ...prev,
        partyRole: r,
        caseInfo: { ...prev.caseInfo, party_role: r },
      })),
    []
  );

  const setSelectedClaims = useCallback(
    (claims: string[]) => update({ selectedClaims: claims }),
    [update]
  );

  const toggleClaim = useCallback(
    (claim: string) =>
      setState((prev) => ({
        ...prev,
        selectedClaims: prev.selectedClaims.includes(claim)
          ? prev.selectedClaims.filter((c) => c !== claim)
          : [...prev.selectedClaims, claim],
      })),
    []
  );

  const setCaseInfo = useCallback(
    (info: Partial<CaseInfo>) =>
      setState((prev) => ({
        ...prev,
        caseInfo: { ...prev.caseInfo, ...info },
      })),
    []
  );

  const setPlaintiffs = useCallback(
    (parties: PartyInfo[]) =>
      setState((prev) => ({
        ...prev,
        caseInfo: { ...prev.caseInfo, plaintiffs: parties },
      })),
    []
  );

  const setDefendants = useCallback(
    (parties: PartyInfo[]) =>
      setState((prev) => ({
        ...prev,
        caseInfo: { ...prev.caseInfo, defendants: parties },
      })),
    []
  );

  const setAttorney = useCallback(
    (info: Partial<AttorneyInfo>) =>
      setState((prev) => ({
        ...prev,
        caseInfo: {
          ...prev.caseInfo,
          attorney: { ...prev.caseInfo.attorney, ...info },
        },
      })),
    []
  );

  const setSelectedSections = useCallback(
    (sections: string[]) => update({ selectedSections: sections }),
    [update]
  );

  const toggleSection = useCallback(
    (section: string) =>
      setState((prev) => ({
        ...prev,
        selectedSections: prev.selectedSections.includes(section)
          ? prev.selectedSections.filter((s) => s !== section)
          : [...prev.selectedSections, section],
      })),
    []
  );

  const setSelectedRequests = useCallback(
    (requests: DiscoveryRequest[]) => update({ selectedRequests: requests }),
    [update]
  );

  const toggleRequest = useCallback(
    (id: string) =>
      setState((prev) => ({
        ...prev,
        selectedRequests: prev.selectedRequests.map((r) =>
          r.id === id ? { ...r, is_selected: !r.is_selected } : r
        ),
      })),
    []
  );

  const setDefinitions = useCallback(
    (defs: Record<string, string>) => update({ definitions: defs }),
    [update]
  );

  const setDefinition = useCallback(
    (term: string, definition: string) =>
      setState((prev) => ({
        ...prev,
        definitions: { ...prev.definitions, [term]: definition },
      })),
    []
  );

  const removeDefinition = useCallback(
    (term: string) =>
      setState((prev) => {
        const next = { ...prev.definitions };
        delete next[term];
        return { ...prev, definitions: next };
      }),
    []
  );

  const setIncludeDefinitions = useCallback(
    (include: boolean) => update({ includeDefinitions: include }),
    [update]
  );

  const setAdverseActions = useCallback(
    (actions: string[]) => update({ adverseActions: actions }),
    [update]
  );

  const setRespondingIsEntity = useCallback(
    (v: boolean) => update({ respondingIsEntity: v }),
    [update]
  );

  const resetState = useCallback(() => {
    setState({ ...DEFAULT_STATE });
    sessionStorage.removeItem(STORAGE_KEY);
  }, []);

  const buildCaseInfo = useCallback((): CaseInfo => {
    return { ...state.caseInfo, party_role: state.partyRole };
  }, [state.caseInfo, state.partyRole]);

  const value = useMemo(
    (): DiscoveryContextValue => ({
      state,
      setToolType,
      setStep,
      nextStep,
      prevStep,
      setPartyRole,
      setSelectedClaims,
      toggleClaim,
      setCaseInfo,
      setPlaintiffs,
      setDefendants,
      setAttorney,
      setSelectedSections,
      toggleSection,
      setSelectedRequests,
      toggleRequest,
      setDefinitions,
      setDefinition,
      removeDefinition,
      setIncludeDefinitions,
      setAdverseActions,
      setRespondingIsEntity,
      resetState,
      buildCaseInfo,
    }),
    [
      state,
      setToolType,
      setStep,
      nextStep,
      prevStep,
      setPartyRole,
      setSelectedClaims,
      toggleClaim,
      setCaseInfo,
      setPlaintiffs,
      setDefendants,
      setAttorney,
      setSelectedSections,
      toggleSection,
      setSelectedRequests,
      toggleRequest,
      setDefinitions,
      setDefinition,
      removeDefinition,
      setIncludeDefinitions,
      setAdverseActions,
      setRespondingIsEntity,
      resetState,
      buildCaseInfo,
    ]
  );

  return (
    <DiscoveryContext.Provider value={value}>
      {children}
    </DiscoveryContext.Provider>
  );
}

// ── Hook ─────────────────────────────────────────────────────────────

export function useDiscovery(): DiscoveryContextValue {
  const ctx = useContext(DiscoveryContext);
  if (!ctx)
    throw new Error("useDiscovery must be used within DiscoveryProvider");
  return ctx;
}
