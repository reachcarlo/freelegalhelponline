import { redirect } from "next/navigation";

/**
 * Legacy case detail route — redirects to the new workspace.
 *
 * Old: /tools/litigagent/[caseId]
 * New: /cases/[caseId]/files
 */
export default async function CaseDetailPage({
  params,
}: {
  params: Promise<{ caseId: string }>;
}) {
  const { caseId } = await params;
  redirect(`/cases/${caseId}/files`);
}
