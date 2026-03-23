import { redirect } from "next/navigation";

/**
 * Legacy case list route — redirects to the new /cases page.
 *
 * Old: /tools/litigagent
 * New: /cases
 */
export default function LitigagentPage() {
  redirect("/cases");
}
