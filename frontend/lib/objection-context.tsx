"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useReducer,
  type ReactNode,
} from "react";
import type {
  ContentScope,
  ExtractedMetadataInfo,
  GenerateResponse,
  ParsedRequestInfo,
  PartyRole,
  ResponseDiscoveryType,
  SkippedSectionInfo,
  Verbosity,
} from "./objection-api";

// ── State ────────────────────────────────────────────────────────────

export interface ObjectionDrafterState {
  currentStep: number;

  // Setup (Step 1)
  discoveryType: ResponseDiscoveryType | "auto";
  verbosity: Verbosity;
  partyRole: PartyRole;
  includeWaiverLanguage: boolean;

  // Input (Step 2)
  rawText: string;

  // Review (Step 3)
  parsedRequests: ParsedRequestInfo[];
  selectedRequestIds: Set<string>;
  skippedSections: SkippedSectionInfo[];
  extractedMetadata: ExtractedMetadataInfo;
  detectedType: string | null;
  isResponseShell: boolean;
  parseWarnings: string[];

  // Results (Step 4)
  generateResponse: GenerateResponse | null;
  contentScope: ContentScope;
  /** Per-objection toggles: key = `${requestNumber}-${groundId}`, value = enabled */
  objectionToggles: Record<string, boolean>;

  // Loading / Error
  isParsing: boolean;
  isGenerating: boolean;
  error: string | null;
}

const initialMetadata: ExtractedMetadataInfo = {
  propounding_party: "",
  responding_party: "",
  set_number: null,
  case_name: "",
};

const initialState: ObjectionDrafterState = {
  currentStep: 0,
  discoveryType: "auto",
  verbosity: "medium",
  partyRole: "defendant",
  includeWaiverLanguage: false,
  rawText: "",
  parsedRequests: [],
  selectedRequestIds: new Set(),
  skippedSections: [],
  extractedMetadata: initialMetadata,
  detectedType: null,
  isResponseShell: false,
  parseWarnings: [],
  generateResponse: null,
  contentScope: "objections_only",
  objectionToggles: {},
  isParsing: false,
  isGenerating: false,
  error: null,
};

// ── Actions ──────────────────────────────────────────────────────────

type Action =
  | { type: "SET_STEP"; step: number }
  | { type: "SET_DISCOVERY_TYPE"; discoveryType: ResponseDiscoveryType | "auto" }
  | { type: "SET_VERBOSITY"; verbosity: Verbosity }
  | { type: "SET_PARTY_ROLE"; partyRole: PartyRole }
  | { type: "SET_WAIVER_LANGUAGE"; include: boolean }
  | { type: "SET_RAW_TEXT"; text: string }
  | {
      type: "PARSE_START";
    }
  | {
      type: "PARSE_SUCCESS";
      requests: ParsedRequestInfo[];
      skippedSections: SkippedSectionInfo[];
      metadata: ExtractedMetadataInfo;
      detectedType: string | null;
      isResponseShell: boolean;
      warnings: string[];
    }
  | { type: "PARSE_ERROR"; error: string }
  | { type: "TOGGLE_REQUEST"; id: string }
  | { type: "SELECT_ALL_REQUESTS" }
  | { type: "DESELECT_ALL_REQUESTS" }
  | { type: "UPDATE_REQUEST"; id: string; text: string }
  | { type: "SPLIT_REQUEST"; id: string; splitIndex: number }
  | { type: "MERGE_REQUESTS"; id: string }
  | { type: "ADD_REQUEST"; text: string; discoveryType: string }
  | { type: "REMOVE_REQUEST"; id: string }
  | { type: "GENERATE_START" }
  | { type: "GENERATE_SUCCESS"; response: GenerateResponse }
  | { type: "GENERATE_ERROR"; error: string }
  | { type: "SET_CONTENT_SCOPE"; scope: ContentScope }
  | { type: "TOGGLE_OBJECTION"; key: string }
  | { type: "CLEAR_ERROR" }
  | { type: "RESET" };

function reducer(state: ObjectionDrafterState, action: Action): ObjectionDrafterState {
  switch (action.type) {
    case "SET_STEP":
      return { ...state, currentStep: action.step, error: null };
    case "SET_DISCOVERY_TYPE":
      return { ...state, discoveryType: action.discoveryType };
    case "SET_VERBOSITY":
      return { ...state, verbosity: action.verbosity };
    case "SET_PARTY_ROLE":
      return { ...state, partyRole: action.partyRole };
    case "SET_WAIVER_LANGUAGE":
      return { ...state, includeWaiverLanguage: action.include };
    case "SET_RAW_TEXT":
      return { ...state, rawText: action.text };
    case "PARSE_START":
      return { ...state, isParsing: true, error: null };
    case "PARSE_SUCCESS": {
      const ids = new Set(
        action.requests.filter((r) => r.is_selected).map((r) => r.id)
      );
      return {
        ...state,
        isParsing: false,
        parsedRequests: action.requests,
        selectedRequestIds: ids,
        skippedSections: action.skippedSections,
        extractedMetadata: action.metadata,
        detectedType: action.detectedType,
        isResponseShell: action.isResponseShell,
        parseWarnings: action.warnings,
        currentStep: 2, // Advance to Review step
      };
    }
    case "PARSE_ERROR":
      return { ...state, isParsing: false, error: action.error };
    case "TOGGLE_REQUEST": {
      const next = new Set(state.selectedRequestIds);
      if (next.has(action.id)) next.delete(action.id);
      else next.add(action.id);
      return { ...state, selectedRequestIds: next };
    }
    case "SELECT_ALL_REQUESTS":
      return {
        ...state,
        selectedRequestIds: new Set(state.parsedRequests.map((r) => r.id)),
      };
    case "DESELECT_ALL_REQUESTS":
      return { ...state, selectedRequestIds: new Set() };
    case "UPDATE_REQUEST":
      return {
        ...state,
        parsedRequests: state.parsedRequests.map((r) =>
          r.id === action.id ? { ...r, request_text: action.text } : r
        ),
      };
    case "SPLIT_REQUEST": {
      const idx = state.parsedRequests.findIndex((r) => r.id === action.id);
      if (idx === -1) return state;
      const orig = state.parsedRequests[idx];
      const text = orig.request_text;
      const before = text.slice(0, action.splitIndex).trim();
      const after = text.slice(action.splitIndex).trim();
      if (!before || !after) return state;
      const newId = `manual-${Date.now()}`;
      const updated = [...state.parsedRequests];
      updated[idx] = { ...orig, request_text: before };
      updated.splice(idx + 1, 0, {
        id: newId,
        request_number: `${orig.request_number}b`,
        request_text: after,
        discovery_type: orig.discovery_type,
        is_selected: true,
      });
      const ids = new Set(state.selectedRequestIds);
      ids.add(newId);
      return { ...state, parsedRequests: updated, selectedRequestIds: ids };
    }
    case "MERGE_REQUESTS": {
      const idx = state.parsedRequests.findIndex((r) => r.id === action.id);
      if (idx === -1 || idx >= state.parsedRequests.length - 1) return state;
      const current = state.parsedRequests[idx];
      const next = state.parsedRequests[idx + 1];
      const merged = {
        ...current,
        request_text: `${current.request_text}\n\n${next.request_text}`,
      };
      const updated = [...state.parsedRequests];
      updated.splice(idx, 2, merged);
      const ids = new Set(state.selectedRequestIds);
      ids.delete(next.id);
      return { ...state, parsedRequests: updated, selectedRequestIds: ids };
    }
    case "ADD_REQUEST": {
      const newId = `manual-${Date.now()}`;
      const maxNum = state.parsedRequests.reduce((max, r) => {
        const n = typeof r.request_number === "number" ? r.request_number : 0;
        return Math.max(max, n);
      }, 0);
      const newReq: ParsedRequestInfo = {
        id: newId,
        request_number: maxNum + 1,
        request_text: action.text,
        discovery_type: action.discoveryType,
        is_selected: true,
      };
      const ids = new Set(state.selectedRequestIds);
      ids.add(newId);
      return {
        ...state,
        parsedRequests: [...state.parsedRequests, newReq],
        selectedRequestIds: ids,
      };
    }
    case "REMOVE_REQUEST": {
      const ids = new Set(state.selectedRequestIds);
      ids.delete(action.id);
      return {
        ...state,
        parsedRequests: state.parsedRequests.filter((r) => r.id !== action.id),
        selectedRequestIds: ids,
      };
    }
    case "GENERATE_START":
      return { ...state, isGenerating: true, error: null };
    case "GENERATE_SUCCESS": {
      // Initialize all objection toggles to ON
      const toggles: Record<string, boolean> = {};
      for (const result of action.response.results) {
        for (const obj of result.objections) {
          toggles[`${result.request_number}-${obj.ground_id}`] = true;
        }
      }
      return {
        ...state,
        isGenerating: false,
        generateResponse: action.response,
        objectionToggles: toggles,
        currentStep: 3, // Advance to Results step
      };
    }
    case "GENERATE_ERROR":
      return { ...state, isGenerating: false, error: action.error };
    case "SET_CONTENT_SCOPE":
      return { ...state, contentScope: action.scope };
    case "TOGGLE_OBJECTION": {
      const toggles = { ...state.objectionToggles };
      toggles[action.key] = !toggles[action.key];
      return { ...state, objectionToggles: toggles };
    }
    case "CLEAR_ERROR":
      return { ...state, error: null };
    case "RESET":
      return initialState;
    default:
      return state;
  }
}

// ── Context ──────────────────────────────────────────────────────────

interface ObjectionDrafterContextValue {
  state: ObjectionDrafterState;
  dispatch: React.Dispatch<Action>;
  // Convenience helpers
  selectedCount: number;
  nextStep: () => void;
  prevStep: () => void;
  setStep: (step: number) => void;
}

const ObjectionDrafterContext = createContext<ObjectionDrafterContextValue | null>(
  null
);

export function ObjectionDrafterProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState);

  const selectedCount = useMemo(
    () => state.selectedRequestIds.size,
    [state.selectedRequestIds]
  );

  const nextStep = useCallback(
    () => dispatch({ type: "SET_STEP", step: state.currentStep + 1 }),
    [state.currentStep]
  );

  const prevStep = useCallback(
    () => dispatch({ type: "SET_STEP", step: Math.max(0, state.currentStep - 1) }),
    [state.currentStep]
  );

  const setStep = useCallback(
    (step: number) => dispatch({ type: "SET_STEP", step }),
    []
  );

  const value = useMemo(
    () => ({ state, dispatch, selectedCount, nextStep, prevStep, setStep }),
    [state, dispatch, selectedCount, nextStep, prevStep, setStep]
  );

  return (
    <ObjectionDrafterContext.Provider value={value}>
      {children}
    </ObjectionDrafterContext.Provider>
  );
}

export function useObjectionDrafter(): ObjectionDrafterContextValue {
  const ctx = useContext(ObjectionDrafterContext);
  if (!ctx) {
    throw new Error(
      "useObjectionDrafter must be used within ObjectionDrafterProvider"
    );
  }
  return ctx;
}
