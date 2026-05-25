import { Composition } from 'remotion';
import { Main, FPS, DURATION_IN_FRAMES, WIDTH, HEIGHT } from './Main';

export const Root: React.FC = () => {
  return (
    <Composition
      id="Grammy"
      component={Main}
      durationInFrames={DURATION_IN_FRAMES}
      fps={FPS}
      width={WIDTH}
      height={HEIGHT}
    />
  );
};
