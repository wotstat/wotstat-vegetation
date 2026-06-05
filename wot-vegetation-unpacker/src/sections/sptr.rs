use crate::binary::{read_matrix, read_u32};
use anyhow::{anyhow, bail, Result};

const RECORD_SIZE: usize = 80;

#[derive(Debug, Clone)]
pub struct SptrRecord {
    pub asset_key: u32,
    pub matrix: [[f32; 4]; 4],
}

pub fn parse(section: &[u8]) -> Result<Vec<SptrRecord>> {
    let record_size = read_u32(section, 0)? as usize;
    let record_count = read_u32(section, 4)? as usize;

    if record_size != RECORD_SIZE {
        bail!("unsupported SpTr record size: {}", record_size);
    }

    let records_start = 8usize;
    let records_end = records_start
        .checked_add(
            record_count
                .checked_mul(record_size)
                .ok_or_else(|| anyhow!("SpTr records size overflow"))?,
        )
        .ok_or_else(|| anyhow!("SpTr records end overflow"))?;

    if records_end > section.len() {
        bail!(
            "SpTr records out of bounds: start={} count={} size={} section_len={}",
            records_start,
            record_count,
            record_size,
            section.len()
        );
    }

    let mut records = Vec::with_capacity(record_count);

    for index in 0..record_count {
        let offset = records_start + index * record_size;

        records.push(SptrRecord {
            matrix: read_matrix(section, offset)?,
            asset_key: read_u32(section, offset + 64)?,
        });
    }

    Ok(records)
}
