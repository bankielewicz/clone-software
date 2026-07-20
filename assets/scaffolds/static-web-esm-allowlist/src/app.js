export function statusMessage(productName) {
  const name = String(productName).trim();
  if (name.length === 0) {
    throw new TypeError("productName must not be empty");
  }
  return `${name} is ready.`;
}

if (typeof document !== "undefined") {
  const status = document.querySelector("#status");
  if (status) {
    status.textContent = statusMessage("{{PRODUCT_NAME}}");
  }
}
