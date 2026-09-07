import { Composition } from "remotion";

import { DURATION, FPS, HEIGHT, Mascot, WIDTH } from "./Mascot";

export const MyComposition = () => {
  return (
    <Composition
      id="Mascot"
      component={Mascot}
      durationInFrames={DURATION}
      fps={FPS}
      width={WIDTH}
      height={HEIGHT}
    />
  );
};
