use std::{env, fs};

use mar_application::PlanCompiler;
use mar_compiler::OpenspecCompiler;

fn main() {
    let mut args = env::args().skip(1);
    match (args.next().as_deref(), args.next()) {
        (Some("compile"), Some(input)) => {
            let source = fs::read_to_string(&input)
                .unwrap_or_else(|error| panic!("failed to read {input}: {error}"));
            let compiler = OpenspecCompiler::default();
            let output = compiler
                .compile(&source, &input)
                .unwrap_or_else(|diagnostics| panic!("compile failed: {diagnostics:?}"));
            println!(
                "{}",
                serde_json::to_string_pretty(&output.plan).expect("plan should serialize")
            );
        }
        _ => {
            eprintln!("usage: mar compile <feature-file>");
            std::process::exit(2);
        }
    }
}
