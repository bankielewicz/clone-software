#[test]
fn emits_the_exact_neutral_readiness_message() {
    assert_eq!(
        clone_app::status_message("Example"),
        Ok("Example is ready.".to_owned())
    );
}
