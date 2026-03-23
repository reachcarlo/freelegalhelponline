"use client";

import { use, useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { CaseFileInfo, listFiles } from "@/lib/litigagent-api";
import CaseInfoPanel from "@/components/litigagent/case-info";

/**
 * Info view — full-panel Case Info elevated from the toggle overlay.
 *
 * Fetches files independently (needed for source attribution in facts).
 * "Close" navigates back to the files view.
 */
export default function InfoPage({
  params,
}: {
  params: Promise<{ caseId: string }>;
}) {
  const { caseId } = use(params);
  const router = useRouter();
  const [files, setFiles] = useState<CaseFileInfo[]>([]);

  useEffect(() => {
    listFiles(caseId)
      .then(setFiles)
      .catch(() => {});
  }, [caseId]);

  const handleClose = useCallback(() => {
    router.push(`/cases/${caseId}/files`);
  }, [router, caseId]);

  return (
    <CaseInfoPanel
      caseId={caseId}
      files={files}
      onClose={handleClose}
    />
  );
}
