mod binary;
mod export;
mod sections;
mod space_bin;

use anyhow::{Context, Result};
use clap::Parser;
use space_bin::SpaceBin;
use std::fs;
use std::path::PathBuf;

#[derive(Parser)]
#[command(name = "wot-map-unpacker")]
#[command(about = "Export WoT space.bin vegetation as JSON")]
struct Cli {
    space_bin: PathBuf,

    #[arg(short, long)]
    output: Option<PathBuf>,
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let space = SpaceBin::read(&cli.space_bin)?;
    let vegetation = export::vegetation_export(&space)?;
    let json = export::vegetation_to_json(&vegetation)?;

    write_output(&json, cli.output)
}

fn write_output(json: &str, output: Option<PathBuf>) -> Result<()> {
    if let Some(output) = output {
        fs::write(&output, json)
            .with_context(|| format!("failed to write {}", output.display()))?;
        eprintln!("wrote {}", output.display());
    } else {
        print!("{json}");
    }

    Ok(())
}
