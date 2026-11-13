// Admin/Seller dashboard: orders, queue monitoring, TableQueue, TableService, Blob listing
const NEXT = {Confirmed: "Processing", Processing: "Out for Delivery", "Out for Delivery": "Delivered"};
const card = (k, v) => `<div class="col-6 col-md-2"><div class="stat"><div class="small text-muted">${k}</div><div class="v">${v}</div></div></div>`;
async function loadAll() {
  const isAdmin = Auth.user.role === "admin";
  const o = await api("/admin/orders");
  $("#ocards").innerHTML = [["Total", o.total], ["Confirmed", o.confirmed], ["Processing", o.processing], ["Out for Delivery", o.out_for_delivery], ["Delivered", o.delivered], ["Pending COD", o.pending_cod_payments]].map(([k, v]) => card(k, v)).join("");
  $("#tsvc").innerHTML = o.orders.map(r => `<tr><td class="mono">${r.OrderID}</td><td>${r.CustomerID}</td><td>${esc(r.ProductName)}</td><td>${r.Quantity}</td><td>${money(r.TotalAmount)}</td><td>${esc(r.PaymentMethod)} ${badge(r.PaymentStatus)}</td><td>${badge(r.OrderStatus)}</td><td>${badge(r.DeliveryStatus)}</td>
    ${isAdmin ? `<td class="text-nowrap">${NEXT[r.OrderStatus] ? `<button class="btn btn-sm btn-primary" onclick="setStatus('${r.OrderID}','${NEXT[r.OrderStatus]}')">&rarr; ${NEXT[r.OrderStatus]}</button>` : ""}
    ${r.PaymentStatus === "Pending" && ["Out for Delivery", "Delivered"].includes(r.OrderStatus) ? `<button class="btn btn-sm btn-outline-success" onclick="cash('${r.OrderID}')">Cash collected</button>` : ""}</td>` : "<td></td>"}</tr>`).join("") || `<tr><td colspan="9" class="text-muted text-center">No orders</td></tr>`;
  if (!isAdmin) return;
  const [q, tq, st] = await Promise.all([api("/admin/queue"), api("/admin/table-queue"), api("/admin/storage/orders")]);
  $("#qcards").innerHTML = [["Queued msgs", q.approximate_messages], ["Pending", q.stats.pending], ["Processed", q.stats.processed], ["Failed", q.stats.failed], ["Retries", q.stats.retries], ["Poison queue", q.poison_messages]].map(([k, v]) => card(k, v)).join("");
  $("#qmsgs").innerHTML = q.messages.map(m => `<tr><td class="mono">${m.content.order_id}</td><td>${m.content.product_id}</td><td>${m.content.customer_id}</td><td>${m.content.quantity}</td><td>${m.dequeue_count}</td><td class="small">${esc(m.inserted_on)}</td></tr>`).join("") || `<tr><td colspan="6" class="text-muted text-center">Queue is empty</td></tr>`;
  $("#tq").innerHTML = tq.map(r => `<tr><td class="mono">${r.OrderID}</td><td>${r.ProductID}</td><td>${r.CustomerID}</td><td>${badge(r.QueueStatus)}</td><td>${r.DequeueCount ?? 0}</td><td class="small">${esc(r.CreatedAt)}</td><td class="small">${esc(r.ProcessedAt || "-")}</td></tr>`).join("") || `<tr><td colspan="7" class="text-muted text-center">No rows</td></tr>`;
  $("#blobs").innerHTML = [...st.orders.map(b => ["orders", b]), ...st["audit-logs"].slice(-8).map(b => ["audit-logs", b])].map(([c, b]) => `<tr><td>${c}</td><td class="mono small">${esc(b.name)}</td><td>${b.size} B</td><td class="small">${new Date(b.last_modified).toLocaleString()}</td></tr>`).join("");
}
async function setStatus(id, s) { try { await api(`/admin/orders/${id}/delivery-status`, jsonOpts("PUT", {status: s})); toast(`${id} -> ${s}`); loadAll(); } catch (e) { fail(e); } }
async function cash(id) { try { await api(`/admin/orders/${id}/confirm-cash`, {method: "POST"}); toast("Cash collection recorded: payment Paid"); loadAll(); } catch (e) { fail(e); } }
async function runConsumer(fail_) { try { const r = await api("/admin/queue/run" + (fail_ ? "?fail=1" : ""), {method: "POST"}); $("#runout").textContent = JSON.stringify(r.results, null, 2) || "[]"; loadAll(); } catch (e) { fail(e); } }
async function reconcile() { try { const r = await api("/admin/reconcile", {method: "POST"}); $("#runout").textContent = "reconcile: " + JSON.stringify(r.fixed); loadAll(); } catch (e) { fail(e); } }
document.addEventListener("DOMContentLoaded", async () => {
  renderNav("admin.html"); if (!requireRole("admin", "seller")) return;
  $("#refresh").onclick = loadAll;
  if (Auth.user.role === "admin") { $("#run").onclick = () => runConsumer(false); $("#runfail").onclick = () => runConsumer(true); $("#rec").onclick = reconcile; }
  else document.querySelectorAll(".admin-only").forEach(e => e.remove());   // seller sees only the order table
  try { await loadAll(); } catch (e) { fail(e); }
});