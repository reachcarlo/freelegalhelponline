"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

// ── Icon components (Heroicons outline, 24x24) ──────────────────

function FolderIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z" />
    </svg>
  );
}

function ChatIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z" />
    </svg>
  );
}

function InfoIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M11.25 11.25l.041-.02a.75.75 0 011.063.852l-.708 2.836a.75.75 0 001.063.853l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z" />
    </svg>
  );
}

function SearchIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
    </svg>
  );
}

function ShieldIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
    </svg>
  );
}

function DocumentIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
    </svg>
  );
}

function ClockIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  );
}

function ChartIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5m.75-9l3-7.5 3 7.5m-6 0h6" />
    </svg>
  );
}

// ── Types ────────────────────────────────────────────────────────

type IconComponent = ({ className }: { className?: string }) => React.ReactElement;

interface NavItem {
  key: string;
  label: string;
  icon: IconComponent;
  /** Path segment after /cases/[caseId]/ — empty string means the default (files) route */
  segment: string;
  disabled?: boolean;
}

interface NavGroup {
  label: string;
  items: NavItem[];
}

// ── Navigation structure ─────────────────────────────────────────

const NAV_GROUPS: NavGroup[] = [
  {
    label: "Core",
    items: [
      { key: "files", label: "Files", icon: FolderIcon, segment: "files" },
      { key: "chat", label: "Chat", icon: ChatIcon, segment: "chat" },
      { key: "info", label: "Info", icon: InfoIcon, segment: "info" },
    ],
  },
  {
    label: "Work Product",
    items: [
      { key: "discovery", label: "Discovery", icon: SearchIcon, segment: "discovery" },
      { key: "objections", label: "Objections", icon: ShieldIcon, segment: "objections", disabled: true },
      { key: "demand", label: "Demand", icon: DocumentIcon, segment: "demand", disabled: true },
    ],
  },
  {
    label: "Analysis",
    items: [
      { key: "timeline", label: "Timeline", icon: ClockIcon, segment: "timeline", disabled: true },
      { key: "analysis", label: "Analysis", icon: ChartIcon, segment: "analysis", disabled: true },
    ],
  },
];

// ── Shared helpers ───────────────────────────────────────────────

/** Items shown in the mobile bottom tab bar (Core group only). */
const MOBILE_ITEMS: NavItem[] = NAV_GROUPS[0].items;

interface SharedNavProps {
  caseId: string;
  badges?: Record<string, number>;
}

function useActiveKey(caseId: string): string {
  const pathname = usePathname();
  const basePath = `/cases/${caseId}`;
  const afterBase = pathname.replace(basePath, "").replace(/^\//, "").split("/")[0];
  if (!afterBase) return "files";
  const match = NAV_GROUPS.flatMap((g) => g.items).find((i) => i.segment === afterBase);
  return match ? match.key : "files";
}

// ── Sidebar component (md+) ─────────────────────────────────────

/**
 * Sidebar navigation for the case workspace.
 *
 * Groups: Core (Files/Chat/Info), Work Product (Discovery/Objections/Demand),
 * Analysis (Timeline/Analysis). Active state derived from URL pathname.
 * Icon-only on md–lg; expanded with labels on lg+.
 */
export default function WorkspaceSidebar({ caseId, badges = {} }: SharedNavProps) {
  const basePath = `/cases/${caseId}`;
  const activeKey = useActiveKey(caseId);

  return (
    <nav
      className="flex h-full flex-col border-r border-border bg-surface"
      data-testid="workspace-sidebar"
      aria-label="Case workspace navigation"
    >
      {NAV_GROUPS.map((group, gi) => (
        <div key={group.label}>
          {/* Group divider (between groups, not before the first) */}
          {gi > 0 && <div className="mx-2 my-1.5 border-t border-border" />}

          {/* Group label — visible only at lg+ */}
          <p className="hidden px-3 pt-3 pb-1 text-[10px] font-semibold uppercase tracking-wider text-text-tertiary lg:block">
            {group.label}
          </p>

          {/* Items */}
          <ul className="flex flex-col gap-0.5 px-1.5 py-1">
            {group.items.map((item) => {
              const isActive = activeKey === item.key;
              const href = item.segment ? `${basePath}/${item.segment}` : basePath;
              const badge = badges[item.key];
              const Icon = item.icon;

              if (item.disabled) {
                return (
                  <li key={item.key}>
                    <span
                      className="group relative flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm text-text-tertiary/50 cursor-default"
                      title={`${item.label} (coming soon)`}
                    >
                      <Icon className="h-5 w-5 shrink-0" />
                      <span className="hidden truncate lg:inline">{item.label}</span>
                    </span>
                  </li>
                );
              }

              return (
                <li key={item.key}>
                  <Link
                    href={href}
                    className={`group relative flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm transition-colors ${
                      isActive
                        ? "bg-accent/10 text-accent font-medium"
                        : "text-text-secondary hover:bg-accent-surface hover:text-accent"
                    }`}
                    title={item.label}
                    aria-current={isActive ? "page" : undefined}
                  >
                    <Icon className="h-5 w-5 shrink-0" />
                    <span className="hidden truncate lg:inline">{item.label}</span>
                    {badge != null && badge > 0 && (
                      <span
                        className={`ml-auto hidden min-w-[20px] rounded-full px-1.5 py-0.5 text-center text-[10px] font-medium leading-none lg:inline-block ${
                          isActive
                            ? "bg-accent/20 text-accent"
                            : "bg-border text-text-tertiary"
                        }`}
                      >
                        {badge > 99 ? "99+" : badge}
                      </span>
                    )}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </nav>
  );
}

// ── Bottom tab bar component (<md) ───────────────────────────────

/**
 * Bottom tab bar for mobile viewports (<768px).
 * Shows the Core nav items (Files/Chat/Info) with icon + label.
 */
export function WorkspaceBottomBar({ caseId, badges = {} }: SharedNavProps) {
  const basePath = `/cases/${caseId}`;
  const activeKey = useActiveKey(caseId);

  return (
    <nav
      className="border-t border-border bg-surface pb-[env(safe-area-inset-bottom,0px)]"
      data-testid="workspace-bottom-bar"
      aria-label="Case workspace navigation"
    >
      <ul className="flex items-stretch">
        {MOBILE_ITEMS.map((item) => {
          const isActive = activeKey === item.key;
          const href = item.segment ? `${basePath}/${item.segment}` : basePath;
          const badge = badges[item.key];
          const Icon = item.icon;

          if (item.disabled) {
            return (
              <li key={item.key} className="flex-1">
                <span className="flex flex-col items-center gap-0.5 px-1 py-2 text-text-tertiary/40 cursor-default">
                  <Icon className="h-5 w-5" />
                  <span className="text-[10px] leading-tight">{item.label}</span>
                </span>
              </li>
            );
          }

          return (
            <li key={item.key} className="flex-1">
              <Link
                href={href}
                className={`relative flex flex-col items-center gap-0.5 px-1 py-2 transition-colors ${
                  isActive
                    ? "text-accent"
                    : "text-text-secondary active:text-accent"
                }`}
                aria-current={isActive ? "page" : undefined}
              >
                <span className="relative">
                  <Icon className="h-5 w-5" />
                  {badge != null && badge > 0 && (
                    <span className="absolute -top-1 -right-2 min-w-[16px] rounded-full bg-accent px-1 text-center text-[9px] font-bold leading-[16px] text-white">
                      {badge > 99 ? "99+" : badge}
                    </span>
                  )}
                </span>
                <span className="text-[10px] font-medium leading-tight">{item.label}</span>
                {isActive && (
                  <span className="absolute top-0 left-1/4 right-1/4 h-0.5 rounded-full bg-accent" />
                )}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
