import { redirect } from "next/navigation";

/**
 * Default case workspace route — redirects to the files view.
 *
 * The canonical route for the files tool is /cases/[caseId]/files.
 * This redirect ensures bookmarks and direct navigation still work.
 */
export default async function CaseWorkspacePage({
  params,
}: {
  params: Promise<{ caseId: string }>;
}) {
  const { caseId } = await params;
  redirect(`/cases/${caseId}/files`);
}
