import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame } from 'remotion';

export const Analytics: React.FC = () => {
  const f = useCurrentFrame();
  const shotY = interpolate(f, [0, 28], [60, 0], { extrapolateRight: 'clamp' });
  const shotOpacity = interpolate(f, [0, 28], [0, 1], { extrapolateRight: 'clamp' });
  const titleOpacity = interpolate(f, [8, 30], [0, 1], { extrapolateRight: 'clamp' });

  // Цифры справа появляются с задержкой
  const stats = [
    { delay: 40, label: 'Лидов', value: '362', sub: '+18%', color: '#818cf8' },
    { delay: 60, label: 'Оплат', value: '61', sub: '+24%', color: '#22d3ee' },
    { delay: 80, label: 'Выручка', value: '553K', sub: '+27%', color: '#fbbf24' },
    { delay: 100, label: 'Конверсия', value: '16.8%', sub: '+1.2 пп', color: '#f472b6' },
  ];

  return (
    <AbsoluteFill style={{
      padding: '70px 90px',
      fontFamily: 'Inter, -apple-system, sans-serif',
      display: 'flex', flexDirection: 'column',
    }}>
      <div style={{
        fontSize: 22,
        color: '#a5b4fc',
        textTransform: 'uppercase',
        letterSpacing: 4,
        fontWeight: 600,
        opacity: titleOpacity,
      }}>Аналитика</div>
      <div style={{
        fontSize: 76,
        fontWeight: 800,
        background: 'linear-gradient(135deg, #fff 0%, #c7d2fe 100%)',
        WebkitBackgroundClip: 'text',
        backgroundClip: 'text',
        color: 'transparent',
        letterSpacing: -2,
        marginTop: 10,
        marginBottom: 28,
        opacity: titleOpacity,
      }}>
        Видно, что окупается
      </div>

      <div style={{
        flex: 1,
        display: 'grid',
        gridTemplateColumns: '1fr 0.4fr',
        gap: 40,
        alignItems: 'center',
      }}>
        <div style={{
          borderRadius: 20,
          overflow: 'hidden',
          boxShadow: '0 60px 100px -30px rgba(0,0,0,0.5)',
          transform: `translateY(${shotY}px)`,
          opacity: shotOpacity,
        }}>
          <Img src={staticFile('shots/13_analytics.png')} style={{ width: '100%', display: 'block' }} />
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
          {stats.map((s) => {
            const op = interpolate(f, [s.delay, s.delay + 18], [0, 1], { extrapolateRight: 'clamp', extrapolateLeft: 'clamp' });
            const y = interpolate(f, [s.delay, s.delay + 18], [25, 0], { extrapolateRight: 'clamp', extrapolateLeft: 'clamp' });
            return (
              <div key={s.label} style={{
                background: 'rgba(255,255,255,0.06)',
                border: '1px solid rgba(255,255,255,0.10)',
                borderRadius: 16,
                padding: '20px 24px',
                opacity: op,
                transform: `translateY(${y}px)`,
              }}>
                <div style={{ fontSize: 16, color: '#a5b4fc', textTransform: 'uppercase', letterSpacing: 2, fontWeight: 600 }}>
                  {s.label}
                </div>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 14, marginTop: 4 }}>
                  <div style={{ fontSize: 56, fontWeight: 800, color: s.color, lineHeight: 1, fontVariantNumeric: 'tabular-nums' }}>
                    {s.value}
                  </div>
                  <div style={{
                    fontSize: 18, color: '#10b981', fontWeight: 700,
                    background: 'rgba(16,185,129,0.15)', padding: '4px 10px', borderRadius: 999,
                  }}>
                    ▲ {s.sub}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </AbsoluteFill>
  );
};
