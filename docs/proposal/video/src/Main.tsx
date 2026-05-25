import { AbsoluteFill, Sequence } from 'remotion';
import { Cover } from './scenes/Cover';
import { KPI } from './scenes/KPI';
import { Leads } from './scenes/Leads';
import { Studio } from './scenes/Studio';
import { Analytics } from './scenes/Analytics';
import { CTA } from './scenes/CTA';

export const FPS = 30;
export const WIDTH = 1920;
export const HEIGHT = 1080;

// 30 секунд = 900 кадров. Разбивка по сценам:
const COVER = 110;     // 0:00 – 0:03.6   (3.6s)
const KPI_S = 150;     // 0:03.6 – 0:08.6 (5.0s)
const LEADS = 150;     // 0:08.6 – 0:13.6 (5.0s)
const STUDIO = 150;    // 0:13.6 – 0:18.6 (5.0s)
const ANALYTICS = 180; // 0:18.6 – 0:24.6 (6.0s)
const CTA_S = 160;     // 0:24.6 – 0:30.0 (5.4s)

export const DURATION_IN_FRAMES = COVER + KPI_S + LEADS + STUDIO + ANALYTICS + CTA_S;

const FRAMES = {
  cover: { from: 0, dur: COVER },
  kpi:   { from: COVER, dur: KPI_S },
  leads: { from: COVER + KPI_S, dur: LEADS },
  studio:{ from: COVER + KPI_S + LEADS, dur: STUDIO },
  ana:   { from: COVER + KPI_S + LEADS + STUDIO, dur: ANALYTICS },
  cta:   { from: COVER + KPI_S + LEADS + STUDIO + ANALYTICS, dur: CTA_S },
};

export const Main: React.FC = () => {
  return (
    <AbsoluteFill style={{ backgroundColor: '#050314' }}>
      {/* Стабильный фон — градиент-блобы */}
      <AbsoluteFill style={{
        background:
          'radial-gradient(circle at 20% 25%, #2a2566 0%, #0f0a2e 55%, #050314 100%)',
      }} />

      <Sequence from={FRAMES.cover.from} durationInFrames={FRAMES.cover.dur}>
        <Cover />
      </Sequence>
      <Sequence from={FRAMES.kpi.from} durationInFrames={FRAMES.kpi.dur}>
        <KPI />
      </Sequence>
      <Sequence from={FRAMES.leads.from} durationInFrames={FRAMES.leads.dur}>
        <Leads />
      </Sequence>
      <Sequence from={FRAMES.studio.from} durationInFrames={FRAMES.studio.dur}>
        <Studio />
      </Sequence>
      <Sequence from={FRAMES.ana.from} durationInFrames={FRAMES.ana.dur}>
        <Analytics />
      </Sequence>
      <Sequence from={FRAMES.cta.from} durationInFrames={FRAMES.cta.dur}>
        <CTA />
      </Sequence>
    </AbsoluteFill>
  );
};
