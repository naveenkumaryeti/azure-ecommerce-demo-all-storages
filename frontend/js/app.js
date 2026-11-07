// Shared: API wrapper (adds the signed login token), auth, toasts, nav. Browser only talks to /api (same origin via nginx).
const API = "/api";
const $ = (s, r = document) => r.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const money = n => n == null ? "-" : "₹" + Number(n).toLocaleString("en-IN");
const NOIMG = "data:image/svg+xml;utf8," + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300"><rect width="100%" height="100%" fill="#e9ecef"/><text x="50%" y="50%" fill="#6c757d" font-family="sans-serif" text-anchor="middle">No image</text></svg>');
const imgUrl = p => p.image_blob_name ? `${API}/images/${encodeURIComponent(p.image_blob_name)}?v=${encodeURIComponent(p.updated_at || "")}` : NOIMG;
const Auth = {
  get token() { return localStorage.getItem("qk_token"); },
  get user() { try { return JSON.parse(localStorage.getItem("qk_user") || "null"); } catch (e) { return null; } },
  set(t, u) { localStorage.setItem("qk_token", t); localStorage.setItem("qk_user", JSON.stringify(u)); },
  clear() { localStorage.removeItem("qk_token"); localStorage.removeItem("qk_user"); }
};
function requireRole(...roles) {
  const u = Auth.user;
  if (!u || (roles.length && !roles.includes(u.role))) { location.href = "login.html?next=" + encodeURIComponent(location.pathname.split("/").pop() + location.search); return false; }
  return true;
}
async function api(path, opts = {}) {
  opts.headers = {...(opts.headers || {})};
  if (Auth.token) opts.headers.Authorization = "Bearer " + Auth.token;
  const r = await fetch(API + path, opts);
  let d = null; try { d = await r.json(); } catch (e) {}
  if (r.status === 401 && Auth.token) { Auth.clear(); location.href = "login.html"; }
  if (!r.ok) throw new Error((d && (d.message || d.error)) || `HTTP ${r.status}`);
  return d;
}
const jsonOpts = (method, body, headers = {}) => ({method, headers: {"Content-Type": "application/json", ...headers}, body: JSON.stringify(body)});
function toast(msg, type = "success") {
  const el = document.createElement("div");
  el.className = `toast align-items-center text-bg-${type} border-0`;
  el.innerHTML = `<div class="d-flex"><div class="toast-body">${esc(msg)}</div><button class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button></div>`;
  $("#toasts").append(el); new bootstrap.Toast(el, {delay: 5000}).show();
  el.addEventListener("hidden.bs.toast", () => el.remove());
}
const fail = e => toast(e.message || String(e), "danger");
const COLORS = {Published: "success", Draft: "secondary", Unpublished: "warning", "Out of Stock": "danger", Confirmed: "primary", Processing: "info", "Out for Delivery": "warning", Delivered: "success", Pending: "warning", Paid: "success", Queued: "info", Processed: "success", Failed: "danger"};
const badge = s => `<span class="badge bg-${COLORS[s] || "secondary"}">${esc(s)}</span>`;
function renderNav(active) {
  const u = Auth.user, L = [["index.html", "Home"]];
  if (u && u.role === "customer") L.push(["cart.html", "Cart"], ["orders.html", "My Orders"]);
  if (u && u.role === "seller") L.push(["seller.html", "Seller Portal"], ["admin.html", "Orders & Queue"]);
  if (u && u.role === "admin") L.push(["admin.html", "Admin Dashboard"], ["storage-dashboard.html", "Azure Storage"], ["seller.html", "Products"]);
  $("#nav").innerHTML = `<nav class="navbar navbar-expand-lg navbar-dark" style="background:var(--az-dark)"><div class="container">
    <a class="navbar-brand fw-bold" href="index.html"><i class="bi bi-lightning-charge-fill"></i> QuickKart</a>
    <button class="navbar-toggler" data-bs-toggle="collapse" data-bs-target="#nv"><span class="navbar-toggler-icon"></span></button>
    <div id="nv" class="collapse navbar-collapse"><ul class="navbar-nav me-auto">${L.map(([h, t]) => `<li class="nav-item"><a class="nav-link ${h === active ? "active" : ""}" href="${h}">${t}</a></li>`).join("")}</ul>
    ${u ? `<span class="navbar-text me-3"><i class="bi bi-person-circle"></i> ${esc(u.name)} <span class="badge bg-light text-dark">${u.role}</span></span><button class="btn btn-outline-light btn-sm" id="logout">Logout</button>` : `<a class="btn btn-outline-light btn-sm" href="login.html">Login</a>`}</div></div></nav>`;
  const lo = $("#logout"); if (lo) lo.onclick = () => { Auth.clear(); location.href = "index.html"; };
}
