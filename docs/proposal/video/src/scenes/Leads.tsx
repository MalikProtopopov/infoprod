import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame } from 'remotion';

export const Leads: React.FC = () => {
  const f = useCurrentFrame();
  const shotY = interpolate(f, [0, 25], [80, 0], { extrapolateRight: 'clamp' });
  const shotOpacity = interpolate(f, [0, 25], [0, 1], { extrapolateRight: 'clamp' });
  const titleOpacity = interpolate(f, [10, 30], [0, 1], { extrapolateRight: 'clamp' });
  const calloutOpacity = interpolate(f, [50, 75], [0, 1], { extrapolateRight: 'clamp' });
  const calloutY = interpolate(f, [50, 75], [20, 0], { extrapolateRight: 'clamp' });

  return (
    <AbsoluteFill style={{
      padding: '80px 100px',
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
      }}>Заявки от клиентов</div>
      <div style={{
        fontSize: 76,
        fontWeight: 800,
        color: '#fff',
        letterSpacing: -2,
        marginTop: 10,
        marginBottom: 40,
        opacity: titleOpacity,
        background: 'linear-gradient(135deg, #fff 0%, #c7d2fe 100%)',
        WebkitBackgroundClip: 'text',
        backgroundClip: 'text',
        color: 'transparent',
      }}>
        Каждая заявка — в одном месте
      </div>

      <div style={{
        flex: 1,
        display: 'grid',
        gridTemplateColumns: '1.45fr 0.55fr',
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
          <Img src={staticFile('shots/06_leads.png')} style={{ width: '100%', display: 'block' }} />
        </div>

        <div style={{
          opacity: calloutOpacity,
          transform: `translateY(${calloutY}px)`,
          display: 'flex', flexDirection: 'column', gap: 30,
        }}>
          {[
            { num: '12', label: 'новых заявок\nза день' },
            { num: '24', label: 'связались\nза неделю' },
            { num: '71', label: 'оплатили\nза месяц' },
          ].map((c) => (
            <div key={c.num} style={{
              background: 'rgba(255,255,255,0.06)',
              border: '1px solid rgba(255,255,255,0.10)',
              borderRadius: 18,
              padding: '24px 28px',
            }}>
              <div style={{
                fontSize: 80, fontWeight: 800, letterSpacing: -2,
                background: 'linear-gradient(135deg, #818cf8 0%, #f472b6 100%)',
                WebkitBackgroundClip: 'text',
                backgroundClip: 'text',
                color: 'transparent',
                lineHeight: 1,
              }}>{c.num}</div>
              <div style={{
                fontSize: 22, color: '#cbd5e1', marginTop: 8,
                whiteSpace: 'pre-line', lineHeight: 1.3,
              }}>{c.label}</div>
            </div>
          ))}
        </div>
      </div>
    </AbsoluteFill>
  );
};
