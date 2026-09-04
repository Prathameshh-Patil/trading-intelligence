const nav = [...document.querySelectorAll("nav a")];
const spy = new IntersectionObserver((entries) => {
  for (const e of entries) {
    if (!e.isIntersecting) continue;
    for (const a of nav) a.classList.toggle("on", a.hash === "#" + e.target.id);
  }
}, { rootMargin: "-10% 0px -75% 0px" });
for (const s of document.querySelectorAll("section")) spy.observe(s);

const CAP = 250;
const q = document.getElementById("q");
const cat = document.getElementById("cat");
const rows = document.getElementById("rows");
const count = document.getElementById("count");

function render() {
  const needle = q.value.trim().toLowerCase();
  const want = cat.value;
  const out = [];
  let hits = 0;
  for (const r of CATALOG) {
    if (want && r[0] !== want) continue;
    if (needle && !r[1].toLowerCase().includes(needle) && !r[2].toLowerCase().includes(needle)) continue;
    hits++;
    if (out.length < CAP) out.push(r);
  }
  rows.innerHTML = out.map((r) =>
    `<tr><td class="k">${r[1]}</td><td>${r[2] || "&mdash;"}</td><td>${LABEL[r[0]]}</td></tr>`
  ).join("");
  count.textContent = hits > CAP
    ? `${hits.toLocaleString()} match — showing first ${CAP}`
    : `${hits.toLocaleString()} match`;
}
q.addEventListener("input", render);
cat.addEventListener("change", render);
render();
