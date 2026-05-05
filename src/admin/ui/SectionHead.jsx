// Page-head primitive matching the public site's `.section-head` motif
// (HomeA.jsx). Reuses the same CSS class so admin and public look the
// same. The number `n` is rendered in accent color, the optional
// `count` is right-aligned and dim.
//
// Usage:
//   <SectionHead n="02" title="文章" count="42 entries" />
//   <SectionHead n="01" title="仪表盘" lead="本月活动" />
//
// `lead` is rendered as a small paragraph below the rule for pages
// that previously used <h1> + <p style={lead}>.

export default function SectionHead({ n, title, count, lead, id, style }) {
  return (
    <>
      <div
        className="section-head"
        id={id}
        style={style}
        data-testid={`section-head-${n}`}
      >
        <span className="label">
          {n && <span className="n">{n} /</span>}
          {n ? ' ' : null}
          {title}
        </span>
        {count != null && <span className="count">{count}</span>}
      </div>
      {lead && <div className="section-lead">{lead}</div>}
    </>
  );
}
