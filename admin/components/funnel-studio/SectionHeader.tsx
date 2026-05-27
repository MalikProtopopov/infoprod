export function SectionHeader({
  n, title, subtitle, status, onCollapse, collapsed,
}: {
  n: number;
  title: string;
  subtitle?: string;
  status: 'ok' | 'warn' | 'todo' | 'off';
  onCollapse?: () => void;
  collapsed?: boolean;
}) {
  const icon = { ok: '✅', warn: '❗', todo: '⚪', off: '🔘' }[status];
  return (
    <div className="flex items-start justify-between gap-3 mb-3">
      <div className="flex items-center gap-2 min-w-0">
        <span className="size-7 rounded-lg gradient-primary text-white text-xs font-bold flex items-center justify-center shrink-0">
          §{n}
        </span>
        <div>
          <h3 className="font-semibold text-base flex items-center gap-2">
            <span>{title}</span>
            <span className="text-sm">{icon}</span>
          </h3>
          {subtitle && <div className="text-xs text-zinc-500 mt-0.5">{subtitle}</div>}
        </div>
      </div>
      {onCollapse && (
        <button type="button" onClick={onCollapse} className="text-xs text-zinc-500 hover:text-ink">
          {collapsed ? '⌄ Раскрыть' : '⌃ Свернуть'}
        </button>
      )}
    </div>
  );
}
