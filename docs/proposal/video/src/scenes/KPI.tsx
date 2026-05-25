import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion';

const KPIS = [
  { label: 'Пользователи', value: 1247, suffix: '', color: '#818cf8' },
  { label: 'Активные подписки', value: 89, suffix: '', color: '#22d3ee' },
  { label: 'Выручка / 30 дней', value: 458, suffix: ' тыс ₽', color: '#fbbf24' },
  { label: 'Конверсия', value: 16.8, suffix: ' %', decimals: 1, color: '#f472b6' },
];

const Card: React.FC<{
  kpi: typeof KPIS[number]; index: number; frame: number; fps: number;
}> = ({ kpi, index, frame, fps }) => {
  const appear = spring({
    frame: frame - index * 8,
    fps,
    config: { damping: 16, stiffness: 110 },
    durationInFrames: 30,
  });
  const counter = interpolate(frame, [index * 8 + 10, index * 8 + 60], [0, kpi.value], {
    extrapolateRight: 'clamp',
    extrapolateLeft: 'clamp',
  });
  const display = (kpi as any).decimals ? counter.toFixed(1) : Math.round(counter).toLocaleString('ru-RU');

  return (
    <div style={{
      flex: 1,
      background: 'rgba(255,255,255,0.06)',
      backdropFilter: 'blur(20px)',
      border: '1px solid rgba(255,255,255,0.10)',
      borderRadius: 28,
      padding: '40px 32px',
      transform: `translateY(${(1 - appear) * 50}px)`,
      opacity: appear,
    }}>
      <div style={{
        fontSize: 18,
        color: '#a5b4fc',
        textTransform: 'uppercase',
        letterSpacing: 2.5,
        fontWeight: 600,
        marginBottom: 14,
      }}>
        {kpi.label}
      </div>
      <div style={{
        fontSize: 96,
        fontWeight: 800,
        color: kpi.color,
        letterSpacing: -3,
        lineHeight: 1,
        fontVariantNumeric: 'tabular-nums',
      }}>
        {display}<span style={{ fontSize: 48, color: '#c7d2fe' }}>{kpi.suffix}</span>
      </div>
    </div>
  );
};

export const KPI: React.FC = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const headlineY = interpolate(f, [0, 25], [40, 0], { extrapolateRight: 'clamp' });
  const headlineOpacity = interpolate(f, [0, 25], [0, 1], { extrapolateRight: 'clamp' });

  return (
    <AbsoluteFill style={{
      padding: '120px 100px',
      fontFamily: 'Inter, -apple-system, sans-serif',
      display: 'flex', flexDirection: 'column', justifyContent: 'center',
    }}>
      <div style={{
        fontSize: 24,
        color: '#a5b4fc',
        textTransform: 'uppercase',
        letterSpacing: 4,
        fontWeight: 600,
        opacity: headlineOpacity,
        transform: `translateY(${headlineY}px)`,
      }}>
        Что показывает Grammy уже на старте
      </div>
      <div style={{
        fontSize: 90,
        fontWeight: 800,
        color: '#fff',
        letterSpacing: -3,
        marginTop: 12,
        marginBottom: 80,
        opacity: headlineOpacity,
        transform: `translateY(${headlineY}px)`,
        background: 'linear-gradient(135deg, #fff 0%, #c7d2fe 100%)',
        WebkitBackgroundClip: 'text',
        backgroundClip: 'text',
        color: 'transparent',
      }}>
        Цифры на дашборде
      </div>

      <div style={{ display: 'flex', gap: 22 }}>
        {KPIS.map((k, i) => (
          <Card key={k.label} kpi={k} index={i} frame={f} fps={fps} />
        ))}
      </div>
    </AbsoluteFill>
  );
};
