import { ImageResponse } from 'next/og';

export const alt = 'Grammy — Telegram bot admin';
export const size = { width: 1200, height: 630 };
export const contentType = 'image/png';

export default function OpengraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'flex-start',
          padding: '0 96px',
          gap: 72,
          background:
            'radial-gradient(circle at 18% 30%, #2a2566 0%, #0f0a2e 55%, #050314 100%)',
          position: 'relative',
        }}
      >
        <div
          style={{
            position: 'absolute',
            top: -120,
            right: -120,
            width: 480,
            height: 480,
            borderRadius: '50%',
            background: 'radial-gradient(circle, rgba(244,63,94,0.35) 0%, rgba(244,63,94,0) 70%)',
          }}
        />
        <div
          style={{
            position: 'absolute',
            bottom: -160,
            left: 280,
            width: 520,
            height: 520,
            borderRadius: '50%',
            background: 'radial-gradient(circle, rgba(99,102,241,0.30) 0%, rgba(99,102,241,0) 70%)',
          }}
        />

        <div
          style={{
            position: 'relative',
            width: 360,
            height: 360,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
          }}
        >
          <div
            style={{
              position: 'absolute',
              inset: 0,
              borderRadius: '50%',
              background:
                'radial-gradient(circle at 36% 30%, #2a2566 0%, #14102e 70%, #050314 100%)',
              boxShadow: '0 20px 60px rgba(0,0,0,0.55)',
            }}
          />
          {[28, 56, 84, 112].map((inset) => (
            <div
              key={inset}
              style={{
                position: 'absolute',
                inset,
                borderRadius: '50%',
                border: '1px solid rgba(255,255,255,0.08)',
              }}
            />
          ))}
          <div
            style={{
              width: 132,
              height: 132,
              borderRadius: '50%',
              background:
                'linear-gradient(135deg, #818cf8 0%, #6366f1 55%, #f43f5e 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 0 0 2px rgba(255,255,255,0.25)',
            }}
          >
            <div
              style={{
                width: 14,
                height: 14,
                borderRadius: '50%',
                background: '#050314',
              }}
            />
          </div>
        </div>

        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: 24,
            position: 'relative',
          }}
        >
          <div
            style={{
              fontSize: 144,
              fontWeight: 800,
              letterSpacing: -6,
              lineHeight: 1,
              background:
                'linear-gradient(135deg, #ffffff 0%, #c7d2fe 60%, #fda4af 100%)',
              backgroundClip: 'text',
              color: 'transparent',
            }}
          >
            Grammy
          </div>
          <div
            style={{
              fontSize: 32,
              fontWeight: 500,
              color: '#c7d2fe',
              letterSpacing: -0.5,
              maxWidth: 560,
              lineHeight: 1.25,
            }}
          >
            Telegram bot admin console
          </div>
          <div
            style={{
              marginTop: 16,
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              fontSize: 22,
              color: '#a5b4fc',
              fontWeight: 500,
            }}
          >
            <div
              style={{
                width: 8,
                height: 8,
                borderRadius: '50%',
                background: '#22c55e',
                boxShadow: '0 0 12px #22c55e',
              }}
            />
            live ops · analytics · funnels
          </div>
        </div>
      </div>
    ),
    { ...size },
  );
}
