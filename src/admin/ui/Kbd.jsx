// Inline keycap primitive matching `.palette .phint kbd` in styles.css.
// One class for typography + border. Compose multiples with a thin
// separator: <Kbd>g</Kbd> <Kbd>p</Kbd>.
export default function Kbd({ children, ...rest }) {
  return (
    <kbd className="admin-kbd" {...rest}>
      {children}
    </kbd>
  );
}
