use crate::binary::read_u32;
use anyhow::{anyhow, bail, Result};
use std::collections::HashMap;

pub fn parse_assets_by_key(section: &[u8]) -> Result<HashMap<u32, String>> {
    let entry_size = read_u32(section, 0)? as usize;
    let entry_count = read_u32(section, 4)? as usize;

    if entry_size < 12 {
        bail!("unsupported BWST entry size: {}", entry_size);
    }

    let entries_start = 8usize;
    let entries_bytes = entry_size
        .checked_mul(entry_count)
        .ok_or_else(|| anyhow!("BWST entries size overflow"))?;
    let strings_len_offset = entries_start + entries_bytes;

    if strings_len_offset + 4 > section.len() {
        bail!("BWST entries out of bounds");
    }

    let strings_len = read_u32(section, strings_len_offset)? as usize;
    let strings_start = strings_len_offset + 4;
    let strings_end = strings_start
        .checked_add(strings_len)
        .ok_or_else(|| anyhow!("BWST strings size overflow"))?;

    if strings_end > section.len() {
        bail!("BWST strings out of bounds");
    }

    let mut assets = HashMap::new();

    for index in 0..entry_count {
        let entry_offset = entries_start + index * entry_size;
        let stored_key = read_u32(section, entry_offset)?;
        let string_rel_offset = read_u32(section, entry_offset + 4)? as usize;
        let string_len = read_u32(section, entry_offset + 8)? as usize;
        let string_start = strings_start
            .checked_add(string_rel_offset)
            .ok_or_else(|| anyhow!("BWST string offset overflow"))?;
        let string_end = string_start
            .checked_add(string_len)
            .ok_or_else(|| anyhow!("BWST string length overflow"))?;

        if string_end > strings_end {
            bail!(
                "BWST string out of bounds: index={} rel_offset={} length={} strings_len={}",
                index,
                string_rel_offset,
                string_len,
                strings_len
            );
        }

        let raw = &section[string_start..string_end];
        let raw = raw.strip_suffix(&[0]).unwrap_or(raw);
        let asset_name = String::from_utf8_lossy(raw).to_string();

        if asset_name.to_ascii_lowercase().ends_with(".srt") {
            assets.entry(stored_key).or_insert(asset_name);
        }
    }

    Ok(assets)
}
