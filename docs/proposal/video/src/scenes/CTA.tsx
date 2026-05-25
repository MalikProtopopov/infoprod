import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion';
import { Vinyl } from './Vinyl';

export const CTA: React.FC = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();

  const headlineOpacity = interpolate(f, [0, 25], [0, 1], { extrapolateRight: 'clamp' });
  const headlineY = interpolate(f, [0, 25], [40, 0], { extrapolateRight: 'clamp' });

  const priceScale = spring({ frame: f - 25, fps, config: { damping: 14, stiffness: 110 } });
  const priceOpacity = interpolate(f, [25, 50], [0, 1], { extrapolateRight: 'clamp' });

  const ctaOpacity = interpolate(f, [70, 95], [0, 1], { extrapolateRight: 'clamp' });
  const ctaY = interpolate(f, [70, 95], [25, 0], { extrapolateRight: 'clamp' });

  const logoSpin = interpolate(f, [0, 160], [0, 100]);

  return (
    <AbsoluteFill style={{
      padding: '100px 100px',
      fontFamily: 'Inter, -apple-system, sans-serif',
      display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center',
    }}>
      <div style={{
        opacity: headlineOpacity,
        transform: `translateY(${headlineY}px)`,
        textAlign: 'center',
      }}>
        <div style={{
          fontSize: 22, color: '#a5b4fc', textTransform: 'uppercase', letterSpacing: 4, fontWeight: 600,
          marginBottom: 16,
        }}>
          Готовый Telegram-бот под ключ
        </div>
        <div style={{
          fontSize: 100,
          fontWeight: 800,
          letterSpacing: -3,
          background: 'linear-gradient(135deg, #fff 0%, #c7d2fe 100%)',
          WebkitBackgroundClip: 'text',
          backgroundClip: 'text',
          color: 'transparent',
          lineHeight: 1.05,
        }}>
          Запуск за 2 недели
        </div>
      </div>

      {/* Цена */}
      <div style={{
        marginTop: 50,
        transform: `scale(${priceScale})`,
        opacity: priceOpacity,
        background: 'linear-gradient(135deg, #6366f1 0%, #f43f5e 100%)',
        borderRadius: 40,
        padding: '40px 80px',
        textAlign: 'center',
        boxShadow: '0 40px 100px -20px rgba(99,102,241,0.7)',
      }}>
        <div style={{ fontSize: 24, color: '#fce7f3', fontWeight: 600, letterSpacing: 2, textTransform: 'uppercase', marginBottom: 12 }}>
          Фиксированная цена
        </div>
        <div style={{ fontSize: 160, fontWeight: 900, color: '#fff', letterSpacing: -6, lineHeight: 1, fontVariantNumeric: 'tabular-nums' }}>
          140 000 ₽
        </div>
        <div style={{ fontSize: 24, color: '#fce7f3', fontWeight: 500, marginTop: 14 }}>
          или 98 000 ₽ при участии в кейсе
        </div>
      </div>

      {/* Footer */}
      <div style={{
        marginTop: 60,
        opacity: ctaOpacity,
        transform: `translateY(${ctaY}px)`,
        display: 'flex', alignItems: 'center', gap: 20,
      }}>
        <div style={{ width: 70, height: 70 }}>
          <Vinyl size={70} spin={logoSpin} />
        </div>
        <div>
          <div style={{ fontSize: 36, fontWeight: 800, color: '#fff', letterSpacing: -0.5 }}>Grammy · mediann.dev</div>
          <div style={{ fontSize: 18, color: '#a5b4fc', marginTop: 4 }}>Связаться · обсудить детали · подписать договор</div>
        </div>
      </div>
    </AbsoluteFill>
  );
};
