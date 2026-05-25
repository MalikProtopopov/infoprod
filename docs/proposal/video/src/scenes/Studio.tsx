import { AbsoluteFill, Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig } from 'remotion';

export const Studio: React.FC = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const shotScale = spring({ frame: f, fps, config: { damping: 18, stiffness: 80 } });
  const titleOpacity = interpolate(f, [10, 30], [0, 1], { extrapolateRight: 'clamp' });
  const bulletsOpacity = interpolate(f, [40, 70], [0, 1], { extrapolateRight: 'clamp' });
  const bulletsY = interpolate(f, [40, 70], [30, 0], { extrapolateRight: 'clamp' });

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
      }}>Студия воронок</div>
      <div style={{
        fontSize: 76,
        fontWeight: 800,
        background: 'linear-gradient(135deg, #fff 0%, #c7d2fe 100%)',
        WebkitBackgroundClip: 'text',
        backgroundClip: 'text',
        color: 'transparent',
        letterSpacing: -2,
        marginTop: 10,
        marginBottom: 36,
        opacity: titleOpacity,
      }}>
        Прогрев на автопилоте
      </div>

      <div style={{
        flex: 1,
        display: 'grid',
        gridTemplateColumns: '1fr 0.85fr',
        gap: 60,
        alignItems: 'center',
      }}>
        <div style={{
          borderRadius: 20,
          overflow: 'hidden',
          boxShadow: '0 60px 100px -30px rgba(0,0,0,0.5)',
          transform: `scale(${shotScale})`,
          transformOrigin: 'center',
        }}>
          <Img src={staticFile('shots/17_funnel_studio.png')} style={{ width: '100%', display: 'block' }} />
        </div>

        <div style={{
          display: 'flex', flexDirection: 'column', gap: 28,
          opacity: bulletsOpacity,
          transform: `translateY(${bulletsY}px)`,
        }}>
          {[
            ['Конструктор шагов', 'Drag-n-drop, шаблоны, превью «как в Telegram»'],
            ['Rich-text для бота', 'Жирный, моноширинный, цитаты, спойлеры, ссылки'],
            ['Защита аудитории', 'Warning при правке активной воронки с 250 подписчиками'],
            ['Авто-отмена при оплате', 'Купил — воронка сама останавливается'],
          ].map(([h, p]) => (
            <div key={h} style={{ display: 'flex', gap: 20, alignItems: 'flex-start' }}>
              <div style={{
                width: 14, height: 14, borderRadius: 7, marginTop: 14,
                background: 'linear-gradient(135deg, #6366f1, #f43f5e)',
                flexShrink: 0,
              }} />
              <div>
                <div style={{ fontSize: 32, fontWeight: 700, color: '#fff', lineHeight: 1.2 }}>{h}</div>
                <div style={{ fontSize: 22, color: '#a5b4fc', marginTop: 6, lineHeight: 1.4 }}>{p}</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </AbsoluteFill>
  );
};
