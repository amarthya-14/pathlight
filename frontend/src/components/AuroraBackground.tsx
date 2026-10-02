// Fixed, decorative background layer: drifting blurred color fields + a faint grid and
// film grain. Pure CSS (globals.css .aurora*), GPU-friendly, disabled by reduced-motion.
export function AuroraBackground() {
  return (
    <div className="aurora" aria-hidden>
      <div className="aurora__blob aurora__blob--1" />
      <div className="aurora__blob aurora__blob--2" />
      <div className="aurora__blob aurora__blob--3" />
      <div className="aurora__grid" />
      <div className="aurora__noise" />
    </div>
  );
}
