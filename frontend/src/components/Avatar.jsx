// No photos: a coloured circle with initials (RK, or R if no last name).
const COLORS = ["#2563eb", "#7c3aed", "#db2777", "#ea580c", "#059669", "#0891b2", "#4f46e5", "#be123c"];

export default function Avatar({ initials, seed = "", size = 40 }) {
  let h = 0;
  for (const ch of seed) h = (h * 31 + ch.charCodeAt(0)) % COLORS.length;
  return (
    <div
      className="avatar"
      style={{ width: size, height: size, background: COLORS[h], fontSize: size * 0.4 }}
      aria-hidden="true"
    >
      {initials}
    </div>
  );
}
