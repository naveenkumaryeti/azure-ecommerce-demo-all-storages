const HOME = {seller: "seller.html", admin: "admin.html", customer: "index.html"};
async function submit(path, body) {
  try {
    const d = await api(path, jsonOpts("POST", body)); Auth.set(d.token, d.user);
    const next = new URLSearchParams(location.search).get("next");
    location.href = next && !next.startsWith("login") ? next : HOME[d.user.role];
  } catch (e) { fail(e); }
}
document.addEventListener("DOMContentLoaded", () => {
  renderNav();
  $("#lf").addEventListener("submit", e => { e.preventDefault(); submit("/auth/login", {email: e.target.email.value, password: e.target.password.value}); });
  $("#rf").addEventListener("submit", e => { e.preventDefault(); submit("/auth/register", {name: e.target.name.value, email: e.target.email.value, password: e.target.password.value}); });
});
