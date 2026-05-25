import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion';
import { Vinyl } from './Vinyl';

export const Cover: React.FC = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();

  const logoScale = spring({ frame: f, fps, config: { damping: 14, stiffness: 110 } });
  const logoSpin = interpolate(f, [0, 110], [0, 60]);
  const titleY = interpolate(f, [15, 35], [40, 0], { extrapolateRight: 'clamp' });
  const titleOpacity = interpolate(f, [15, 35], [0, 1], { extrapolateRight: 'clamp' });
  const taglineOpacity = interpolate(f, [40, 60], [0, 1], { extrapolateRight: 'clamp' });
  const taglineY = interpolate(f, [40, 60], [20, 0], { extrapolateRight: 'clamp' });

  // Декоративные блобы дрейфуют
  const blob1 = interpolate(f, [0, 110], [0, 40]);
  const blob2 = interpolate(f, [0, 110], [0, -30]);

  return (
    <AbsoluteFill style={{
      display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column',
      fontFamily: 'Inter, -apple-system, sans-serif',
    }}>
      {/* Blobs */}
      <AbsoluteFill style={{ pointerEvents: 'none' }}>
        <div style={{
          position: 'absolute', top: -100, right: -200 + blob1,
          width: 600, height: 600, borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(244,63,94,0.4) 0%, rgba(244,63,94,0) 70%)',
          filter: 'blur(40px)',
        }} />
        <div style={{
          position: 'absolute', bottom: -150, left: -100 + blob2,
          width: 700, height: 700, borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(99,102,241,0.4) 0%, rgba(99,102,241,0) 70%)',
          filter: 'blur(40px)',
        }} />
      </AbsoluteFill>

      <div style={{
        transform: `scale(${logoScale})`,
        marginBottom: 50,
      }}>
        <Vinyl size={280} spin={logoSpin} />
      </div>

      <div style={{
        fontSize: 180,
        fontWeight: 900,
        letterSpacing: -8,
        lineHeight: 1,
        background: 'linear-gradient(135deg, #fff 0%, #c7d2fe 60%, #fda4af 100%)',
        WebkitBackgroundClip: 'text',
        backgroundClip: 'text',
        color: 'transparent',
        transform: `translateY(${titleY}px)`,
        opacity: titleOpacity,
      }}>
        Grammy
      </div>

      <div style={{
        fontSize: 36,
        color: '#c7d2fe',
        fontWeight: 400,
        marginTop: 20,
        textAlign: 'center',
        maxWidth: 1400,
        lineHeight: 1.3,
        transform: `translateY(${taglineY}px)`,
        opacity: taglineOpacity,
      }}>
        Telegram-бот, который продаёт доступ в закрытые каналы
      </div>
    </AbsoluteFill>
  );
};
