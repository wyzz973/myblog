/**
 * 12×12 pixel-art face. Uses currentColor so the parent container's text
 * color drives the foreground; transparent gaps show whatever background
 * the parent applies (solid green for the logo, gradient for the reader
 * author block, etc.).
 *
 *  Grid layout (1 = filled, 0 = transparent):
 *    . . . . 1 1 1 1 . . . .
 *    . . 1 1 1 1 1 1 1 1 . .
 *    . 1 1 1 1 1 1 1 1 1 1 .
 *    1 1 1 1 1 1 1 1 1 1 1 1
 *    1 1 . . 1 1 1 1 . . 1 1   ← eyes (transparent gaps)
 *    1 1 . . 1 1 1 1 . . 1 1
 *    1 1 1 1 1 1 1 1 1 1 1 1
 *    1 1 1 . 1 1 1 1 . 1 1 1
 *    1 1 1 1 . . . . 1 1 1 1   ← mouth
 *    . 1 1 1 1 1 1 1 1 1 1 .
 *    . . 1 1 1 1 1 1 1 1 . .
 *    . . . . 1 1 1 1 . . . .
 */
export default function PixelAvatar({ size = '100%', ...props }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 12 12"
      width={size}
      height={size}
      shapeRendering="crispEdges"
      aria-hidden="true"
      {...props}
    >
      {/* top crown */}
      <rect x="4" y="0" width="4" height="1" fill="currentColor" />
      <rect x="2" y="1" width="8" height="1" fill="currentColor" />
      <rect x="1" y="2" width="10" height="1" fill="currentColor" />
      {/* full-width band above eyes */}
      <rect x="0" y="3" width="12" height="1" fill="currentColor" />
      {/* eye row: gap at cols 2-3 and 8-9, height 2 */}
      <rect x="0" y="4" width="2" height="2" fill="currentColor" />
      <rect x="4" y="4" width="4" height="2" fill="currentColor" />
      <rect x="10" y="4" width="2" height="2" fill="currentColor" />
      {/* full-width band below eyes */}
      <rect x="0" y="6" width="12" height="1" fill="currentColor" />
      {/* cheek row: small gaps at 3 and 8 */}
      <rect x="0" y="7" width="3" height="1" fill="currentColor" />
      <rect x="4" y="7" width="4" height="1" fill="currentColor" />
      <rect x="9" y="7" width="3" height="1" fill="currentColor" />
      {/* mouth row: 4-wide gap centered */}
      <rect x="0" y="8" width="4" height="1" fill="currentColor" />
      <rect x="8" y="8" width="4" height="1" fill="currentColor" />
      {/* bottom arc */}
      <rect x="1" y="9" width="10" height="1" fill="currentColor" />
      <rect x="2" y="10" width="8" height="1" fill="currentColor" />
      <rect x="4" y="11" width="4" height="1" fill="currentColor" />
    </svg>
  );
}
