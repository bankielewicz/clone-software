export function statusMessage(productName: string): string {
  const name = productName.trim();
  if (name.length === 0) {
    throw new TypeError("productName must not be empty");
  }
  return `${name} is ready.`;
}

console.log(statusMessage("{{PRODUCT_NAME}}"));
