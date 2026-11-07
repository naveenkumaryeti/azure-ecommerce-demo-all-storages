// Customer pages: home, product details, cart, checkout, my orders
const page = document.body.dataset.page, qs = new URLSearchParams(location.search);
async function addToCart(pid, qty = 1, go) {
  const u = Auth.user;
  if (!u) return (location.href = "login.html?next=" + encodeURIComponent(location.pathname.split("/").pop() + location.search));
  if (u.role !== "customer") return toast("Log in as a customer to shop", "warning");
  try { await api("/cart", jsonOpts("POST", {product_id: pid, quantity: qty})); toast("Added to cart"); if (go) location.href = "cart.html"; } catch (e) { fail(e); }
}
async function home() {
  const render = async () => {
    const list = await api("/products?q=" + encodeURIComponent($("#q").value || ""));
    $("#grid").innerHTML = list.length ? list.map(p => `<div class="col-6 col-md-4 col-lg-3"><div class="card pcard"><img src="${imgUrl(p)}" alt="${esc(p.product_name)}" loading="lazy">
      <div class="card-body d-flex flex-column">${p.product_status ? `<span class="badge badge-launch align-self-start mb-1">${esc(p.product_status)}</span>` : ""}
      <h6 class="card-title">${esc(p.product_name)}</h6><div class="small text-muted">${esc(p.colour)}</div>
      <div class="d-flex justify-content-between align-items-center my-2"><span class="price">${money(p.price)}</span><small class="text-success">${p.available_quantity} in stock</small></div>
      <a class="btn btn-outline-primary btn-sm" href="products.html?id=${p.product_id}">View Product</a>
      <button class="btn btn-primary btn-sm mt-1" onclick="addToCart('${p.product_id}')"><i class="bi bi-cart-plus"></i> Add to Cart</button></div></div></div>`).join("")
      : `<p class="text-center text-muted py-5">No published products yet.</p>`;
  };
  $("#q").addEventListener("input", render); await render();
}
async function details() {
  const p = await api("/products/" + qs.get("id"));
  $("#detail").innerHTML = `<div class="row g-4"><div class="col-md-5"><img class="img-fluid rounded shadow-sm" src="${imgUrl(p)}"></div><div class="col-md-7">
    ${p.product_status ? `<span class="badge badge-launch">${esc(p.product_status)}</span>` : ""}<h2 class="mt-2">${esc(p.product_name)}</h2>
    <p class="text-muted">Colour: <b>${esc(p.colour)}</b> &middot; Category: ${esc(p.category)}</p><p>${esc(p.description)}</p>
    <div class="price fs-3 mb-2">${money(p.price)}</div><p class="text-success">${p.available_quantity} unit(s) available</p>
    <div class="input-group mb-3" style="max-width:200px"><span class="input-group-text">Qty</span><input id="qty" type="number" class="form-control" min="1" max="${p.available_quantity}" value="1"></div>
    <button class="btn btn-primary" onclick="addToCart('${p.product_id}',+$('#qty').value)"><i class="bi bi-cart-plus"></i> Add to Cart</button>
    <button class="btn btn-success" onclick="addToCart('${p.product_id}',+$('#qty').value,true)">Buy now</button></div></div>`;
}
async function cart() {
  const c = await api("/cart");
  $("#lines").innerHTML = c.items.map(i => `<tr><td><img class="thumb" src="${imgUrl(i)}"></td><td>${esc(i.product_name)}<br><small class="text-muted">${esc(i.colour)}</small>${i.available ? "" : ' <span class="badge bg-danger">unavailable</span>'}</td>
    <td>${money(i.price)}</td><td><input type="number" class="form-control form-control-sm" style="width:80px" min="1" max="${i.available_quantity}" value="${i.quantity}" onchange="setQty('${i.product_id}',this.value)"></td>
    <td>${money(i.subtotal)}</td><td class="text-end"><a class="btn btn-success btn-sm ${i.available ? "" : "disabled"}" href="checkout.html?product=${i.product_id}&qty=${i.quantity}">Checkout</a>
    <button class="btn btn-outline-danger btn-sm" onclick="rm('${i.product_id}')"><i class="bi bi-trash"></i></button></td></tr>`).join("") || `<tr><td colspan="6" class="text-center text-muted py-4">Your cart is empty.</td></tr>`;
}
async function setQty(id, q) { try { await api("/cart/" + id, jsonOpts("PUT", {quantity: +q})); } catch (e) { fail(e); } cart(); }
async function rm(id) { try { await api("/cart/" + id, {method: "DELETE"}); } catch (e) { fail(e); } cart(); }
async function checkout() {
  const pid = qs.get("product"), qty = +qs.get("qty") || 1, p = await api("/products/" + pid);
  const key = sessionStorage.getItem(`idem-${pid}-${qty}`) || (crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random());
  sessionStorage.setItem(`idem-${pid}-${qty}`, key);       // same key on refresh/double-click -> backend creates only ONE order
  $("#summary").innerHTML = `<div class="d-flex gap-3"><img class="thumb-lg rounded" style="width:140px;height:140px" src="${imgUrl(p)}"><div><h5>${esc(p.product_name)}</h5>
    <div>Colour: ${esc(p.colour)}</div><div>Unit price: ${money(p.price)}</div><div>Quantity: ${qty}</div><div class="price mt-1">Total: ${money(p.price * qty)}</div>
    <div class="small text-muted">(final amount is recalculated by the server)</div></div></div>`;
  $("#cf").addEventListener("submit", async e => {
    e.preventDefault(); const b = $("#confirm"); b.disabled = true;
    try {
      const o = await api("/orders", jsonOpts("POST", {product_id: pid, quantity: qty, payment_method: "COD", delivery_address: e.target.address.value}, {"Idempotency-Key": key}));
      sessionStorage.removeItem(`idem-${pid}-${qty}`);
      $("#checkout").innerHTML = `<div class="alert alert-success"><h4>${esc(o.message)}</h4></div><table class="table"><tr><th>Order ID</th><td class="mono">${o.order_id}</td></tr>
        <tr><th>Order date</th><td>${new Date(o.created_at).toLocaleString()}</td></tr><tr><th>Product</th><td>${esc(o.product_name)} (${esc(o.colour)})</td></tr><tr><th>Quantity</th><td>${o.quantity}</td></tr>
        <tr><th>Total amount</th><td>${money(o.total_amount)}</td></tr><tr><th>Payment method</th><td>Cash on Delivery</td></tr><tr><th>Order status</th><td>${badge(o.order_status)}</td></tr></table><a class="btn btn-primary" href="orders.html">View my orders</a>`;
    } catch (err) { fail(err); b.disabled = false; }
  });
}
async function orders() {
  const rows = await api("/customer/orders");
  $("#otable").innerHTML = rows.map(r => `<tr><td class="mono">${r.OrderID}</td><td>${new Date(r.CreatedAt).toLocaleString()}</td><td>${esc(r.ProductName)} &times; ${r.Quantity}</td><td>${money(r.TotalAmount)}</td>
    <td>${esc(r.PaymentMethod)} ${badge(r.PaymentStatus)}</td><td>${badge(r.OrderStatus)}</td><td>${badge(r.DeliveryStatus)}</td></tr>`).join("") || `<tr><td colspan="7" class="text-center text-muted py-4">No orders yet.</td></tr>`;
}
document.addEventListener("DOMContentLoaded", async () => {
  renderNav({home: "index.html", cart: "cart.html", orders: "orders.html"}[page]);
  try {
    if (page === "home") await home(); else if (page === "details") await details();
    else if (!requireRole("customer")) return; else if (page === "cart") await cart(); else if (page === "checkout") await checkout(); else if (page === "orders") await orders();
  } catch (e) { fail(e); }
});
