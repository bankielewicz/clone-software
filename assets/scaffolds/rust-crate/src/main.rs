fn main() {
    let message = clone_app::status_message("{{PRODUCT_NAME}}")
        .expect("the rendered product name must not be empty");
    println!("{message}");
}
