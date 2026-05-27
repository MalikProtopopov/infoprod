export /** Сегмент-переключатель типа шага. */
function StepKindSelector({
  kind, onChange, allowQuiz = true, allowForm = true,
}: {
  kind: 'message' | 'quiz' | 'form';
  onChange: (next: 'message' | 'quiz' | 'form') => void;
  allowQuiz?: boolean;
  allowForm?: boolean;
}) {
  const items: { value: 'message' | 'quiz' | 'form'; label: string; emoji: string }[] = [
    { value: 'message', label: 'Сообщение', emoji: '💬' },
    // Квиз/форма как тип шага — только если фича включена. Если на легаси-шаге
    // уже выбран выключенный тип, оставляем его видимым, чтобы не «потерять».
    ...(allowQuiz || kind === 'quiz' ? [{ value: 'quiz' as const, label: 'Квиз', emoji: '🧠' }] : []),
    ...(allowForm || kind === 'form' ? [{ value: 'form' as const, label: 'Форма', emoji: '📋' }] : []),
  ];
  return (
    <div className="inline-flex rounded-xl bg-zinc-100/80 p-1 text-sm">
      {items.map((it) => {
        const active = it.value === kind;
        return (
          <button
            key={it.value}
            type="button"
            onClick={() => onChange(it.value)}
            className={
              'px-3 h-8 rounded-lg transition flex items-center gap-1.5 ' +
              (active
                ? 'bg-white shadow-soft text-ink font-medium'
                : 'text-zinc-500 hover:text-ink')
            }
          >
            <span>{it.emoji}</span>
            <span>{it.label}</span>
          </button>
        );
      })}
    </div>
  );
}
