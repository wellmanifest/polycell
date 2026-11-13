// Kompiluje niezmienny kontrakt transportowy polycell.v1.CellHost (protoc dołączony jako crate).
fn main() -> Result<(), Box<dyn std::error::Error>> {
    std::env::set_var("PROTOC", protoc_bin_vendored::protoc_bin_path()?);
    let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
    tonic_build::configure()
        .build_client(false)
        .compile_protos(&[root.join("proto/polycell/v1/cellhost.proto")], &[root.join("proto")])?;
    println!("cargo:rerun-if-changed=../../proto");
    println!("cargo:rerun-if-changed=../../gen/rust");
    println!("cargo:rerun-if-changed=../../cells/rust");
    Ok(())
}
