"use client";

import { use } from "react";
import ChatPanel from "@/components/litigagent/chat-panel";

/**
 * Chat view — full-panel chat elevated from the drawer overlay.
 *
 * Renders inside the workspace shell's tool canvas area.
 */
export default function ChatPage({
  params,
}: {
  params: Promise<{ caseId: string }>;
}) {
  const { caseId } = use(params);
  return <ChatPanel caseId={caseId} />;
}
