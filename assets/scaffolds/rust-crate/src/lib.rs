/// Return a deterministic neutral readiness message.
pub fn status_message(product_name: &str) -> Result<String, &'static str> {
    let name = product_name.trim();
    if name.is_empty() {
        return Err("product_name must not be empty");
    }
    Ok(format!("{name} is ready."))
}

#[cfg(test)]
mod tests {
    use super::status_message;

    #[test]
    fn rejects_empty_product_name() {
        assert_eq!(status_message("  "), Err("product_name must not be empty"));
    }
}
