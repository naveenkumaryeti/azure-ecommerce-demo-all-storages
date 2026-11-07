// Seller portal: product management
let PRODUCTS = [], modal;
async function load() {
  PRODUCTS = await api("/seller/products");
  $("#ptable").innerHTML = PRODUCTS.map(p => `<tr><td><img class="thumb" src="${imgUrl(p)}"></td><td class="mono">${p.product_id}</td><td>${esc(p.product_name)}<br><small class="text-muted">${esc(p.colour)}</small></td>
    <td>${money(p.price)}</td><td>${p.available_quantity}</td><td>${badge(p.publication_status)}</td><td class="text-end text-nowrap">
    <button class="btn btn-sm btn-outline-primary" onclick="openForm('${p.product_id}')">Edit</button>
    ${p.publication_status === "Published" ? `<button class="btn btn-sm btn-outline-warning" onclick="act('${p.product_id}','unpublish')">Unpublish</button>` : `<button class="btn btn-sm btn-success" onclick="act('${p.product_id}','publish')">Publish</button>`}
    <button class="btn btn-sm btn-outline-danger" onclick="del('${p.product_id}')"><i class="bi bi-trash"></i></button></td></tr>`).join("") || `<tr><td colspan="7" class="text-center text-muted py-4">No products yet.</td></tr>`;
}
function openForm(id) {
  const f = $("#pform"); f.reset(); const p = PRODUCTS.find(x => x.product_id === id);
  $("#mtitle").textContent = p ? "Edit product" : "Add New Product"; f.pid.value = p ? p.product_id : ""; f.etag.value = p ? p.etag : "";
  if (p) for (const k of ["product_name", "colour", "product_status", "available_quantity", "price", "category", "description"]) f[k].value = p[k] ?? "";
  $("#preview").src = p ? imgUrl(p) : NOIMG; (modal = modal || new bootstrap.Modal($("#pmodal"))).show();
}
function demoValues() { const f = $("#pform"); f.product_name.value = "iPhone 8"; f.colour.value = "Burgundy (Monochrome)"; f.product_status.value = "Recently Launched"; f.available_quantity.value = 10; f.category.value = "Smartphones"; f.description.value = "iPhone 8 in Burgundy (Monochrome). Set your own selling price before publishing."; }
async function save(e) {
  e.preventDefault(); const f = e.target, b = $("#saveBtn"); b.disabled = true;
  const fd = new FormData(); for (const k of ["product_name", "colour", "product_status", "available_quantity", "price", "category", "description"]) fd.append(k, f[k].value);
  if (f.image.files[0]) fd.append("image", f.image.files[0]);
  try {
    const p = f.pid.value ? await api("/seller/products/" + f.pid.value, {method: "PUT", body: fd, headers: {"If-Match": f.etag.value}}) : await api("/seller/products", {method: "POST", body: fd});
    modal.hide(); toast(`Saved as ${p.publication_status}: products/${p.product_id}.json`); await load();
  } catch (err) { fail(err); } finally { b.disabled = false; }
}
async function act(id, a) { try { await api(`/seller/products/${id}/${a}`, {method: "POST"}); toast(a === "publish" ? "Published - now on the home page" : "Unpublished"); await load(); } catch (e) { fail(e); } }
async function del(id) { if (!confirm("Delete " + id + "?")) return; try { await api("/seller/products/" + id, {method: "DELETE"}); toast("Deleted"); await load(); } catch (e) { fail(e); } }
document.addEventListener("DOMContentLoaded", async () => {
  renderNav("seller.html"); if (!requireRole("seller", "admin")) return;
  $("#pform").addEventListener("submit", save);
  $("#pform").image.addEventListener("change", ev => { const f = ev.target.files[0]; if (f) $("#preview").src = URL.createObjectURL(f); });
  try { await load(); } catch (e) { fail(e); }
});
