use anyhow::{bail, Result};

pub fn read_u32(data: &[u8], offset: usize) -> Result<u32> {
    if offset + 4 > data.len() {
        bail!("read_u32 out of bounds at offset {}", offset);
    }

    Ok(u32::from_le_bytes([
        data[offset],
        data[offset + 1],
        data[offset + 2],
        data[offset + 3],
    ]))
}

pub fn read_f32(data: &[u8], offset: usize) -> Result<f32> {
    if offset + 4 > data.len() {
        bail!("read_f32 out of bounds at offset {}", offset);
    }

    Ok(f32::from_le_bytes([
        data[offset],
        data[offset + 1],
        data[offset + 2],
        data[offset + 3],
    ]))
}

pub fn read_matrix(data: &[u8], offset: usize) -> Result<[[f32; 4]; 4]> {
    Ok([
        [
            read_f32(data, offset)?,
            read_f32(data, offset + 4)?,
            read_f32(data, offset + 8)?,
            read_f32(data, offset + 12)?,
        ],
        [
            read_f32(data, offset + 16)?,
            read_f32(data, offset + 20)?,
            read_f32(data, offset + 24)?,
            read_f32(data, offset + 28)?,
        ],
        [
            read_f32(data, offset + 32)?,
            read_f32(data, offset + 36)?,
            read_f32(data, offset + 40)?,
            read_f32(data, offset + 44)?,
        ],
        [
            read_f32(data, offset + 48)?,
            read_f32(data, offset + 52)?,
            read_f32(data, offset + 56)?,
            read_f32(data, offset + 60)?,
        ],
    ])
}
