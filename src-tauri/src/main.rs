fn main() {
    // Set before Tauri starts threads: SurrealKV must sync every committed write.
    std::env::set_var("SURREAL_SYNC_DATA", "true");
    messenger_lib::run();
}
