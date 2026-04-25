export default function Konami({ on }) {
  if (!on) return null;
  return (
    <div className="konami">
      <div className="card">
        <h2>GODMODE</h2>
        <p>◈ ◈ ◈  welcome, fellow traveler  ◈ ◈ ◈</p>
      </div>
    </div>
  );
}
