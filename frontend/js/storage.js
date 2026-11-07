// Azure Storage Dashboard + Blob Explorer (admin only; every call goes through the backend with the login token)
let current = null;
const fmtB = n => n > 1048576 ? (n / 1048576).toFixed(1) + " MB" : n > 1024 ? (n / 1024).toFixed(1) + " KB" : n + " B";
const bpath = (c, n) => `/storage/blob/${c}/${n.split("/").map(encodeURIComponent).join("/")}`;
const rawBlob = async (c, n, q = "") => { const r = await fetch(API + bpath(c, n) + q, {headers: {Authorization: "Bearer " + Auth.token}}); if (!r.ok) throw new Error("HTTP " + r.status); return r.blob(); };
async function loadInfo() {
  const i = await api("/storage/info");
  const cards = [["Storage account", i.account], ["Blob endpoint", i.endpoint], ["Authentication", i.auth + (i.token.ok ? " - token OK" : " - FAILED " + i.token.error)], ["Containers", i.containers.join(", ")],
    ["Total products", i.total_products], ["Total images", i.total_images], ["Total orders", i.total_orders], ["Audit events", i.total_audit_events], ["Last upload", i.last_upload ? new Date(i.last_upload).toLocaleString() : "-"],
    ["Last successful operation", i.last_success_op || "-"], ["Blob upload status", i.upload_status], ["Served by VMSS instance", i.served_by]];
  $("#stats").innerHTML = cards.map(([k, v]) => `<div class="col-md-4 col-sm-6"><div class="stat h-100"><div class="small text-muted">${k}</div><div class="v fs-6 text-break">${esc(v)}</div></div></div>`).join("");
}
async function loadContainers() {
  const cs = await api("/storage/containers");
  $("#clist").innerHTML = cs.map(c => `<button class="list-group-item list-group-item-action ${c === current ? "active" : ""}" onclick="selectContainer('${c}')"><i class="bi bi-box"></i> ${c}</button>`).join("");
  $("#upc").innerHTML = cs.map(c => `<option>${c}</option>`).join("");
}
async function selectContainer(c) {
  current = c; await loadContainers(); const bl = await api(`/storage/containers/${c}/blobs`);
  $("#btitle").textContent = `${c} (${bl.length} blobs)`;
  $("#btable").innerHTML = bl.map(b => `<tr><td class="mono text-break">${esc(b.name)}</td><td>${esc(b.content_type)}</td><td>${fmtB(b.size)}</td><td>${new Date(b.last_modified).toLocaleString()}</td><td class="text-nowrap">
    <button class="btn btn-sm btn-outline-primary" onclick="viewBlob('${c}','${encodeURIComponent(b.name)}','${b.content_type}')">View</button>
    <button class="btn btn-sm btn-outline-secondary" onclick="dl('${c}','${encodeURIComponent(b.name)}')">Download</button>
    <button class="btn btn-sm btn-outline-danger" onclick="delBlob('${c}','${encodeURIComponent(b.name)}')">Delete</button></td></tr>`).join("") || `<tr><td colspan="5" class="text-muted text-center">Empty container</td></tr>`;
}
async function viewBlob(c, enc, type) {
  const n = decodeURIComponent(enc);
  try { const b = await rawBlob(c, n);
    if (type.startsWith("image/")) $("#viewer").innerHTML = `<img src="${URL.createObjectURL(b)}" class="img-fluid rounded">`;
    else { const t = await b.text(); let o = t; try { o = JSON.stringify(JSON.parse(t), null, 2); } catch (e) {} $("#viewer").innerHTML = `<pre class="blob mono">${esc(o)}</pre>`; } } catch (e) { fail(e); }
}
async function dl(c, enc) { const n = decodeURIComponent(enc); try { const a = document.createElement("a"); a.href = URL.createObjectURL(await rawBlob(c, n, "?download=1")); a.download = n.split("/").pop(); a.click(); } catch (e) { fail(e); } }
async function delBlob(c, enc) { const n = decodeURIComponent(enc); if (!confirm(`Delete ${c}/${n}?`)) return; try { await api(bpath(c, n), {method: "DELETE"}); toast("Deleted " + n); selectContainer(c); loadInfo(); } catch (e) { fail(e); } }
async function upload(e) { e.preventDefault(); const fd = new FormData(e.target); try { const r = await api("/storage/upload", {method: "POST", body: fd}); toast("Uploaded " + r.uploaded); e.target.reset(); selectContainer(fd.get("container")); loadInfo(); } catch (err) { fail(err); } }
document.addEventListener("DOMContentLoaded", async () => {
  renderNav("storage-dashboard.html"); if (!requireRole("admin")) return;
  $("#upform").addEventListener("submit", upload);
  try { await loadInfo(); await loadContainers(); } catch (e) { fail(e); $("#stats").innerHTML = `<div class="alert alert-danger">${esc(e.message)}</div>`; }
});
