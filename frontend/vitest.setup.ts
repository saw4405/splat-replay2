import '@testing-library/jest-dom/vitest';

if (typeof window !== 'undefined' && !Element.prototype.animate) {
  Element.prototype.animate = function () {
    return {
      cancel: () => {},
      finish: () => {},
      play: () => {},
      pause: () => {},
      reverse: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
      onfinish: null,
      oncancel: null,
      onremove: null,
      currentTime: 0,
      effect: null,
      finished: Promise.resolve(undefined) as unknown as Promise<Animation>,
      id: '',
      pending: false,
      playState: 'idle',
      playbackRate: 1,
      ready: Promise.resolve(undefined) as unknown as Promise<Animation>,
      startTime: null,
      timeline: null,
    } as unknown as Animation;
  };
}
