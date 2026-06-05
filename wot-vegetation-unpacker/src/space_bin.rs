use crate::binary::read_u32;
use anyhow::{anyhow, bail, Context, Result};
use std::fs;
use std::path::Path;

const SECTION_META_SIZE: usize = 24;

#[derive(Debug, Clone)]
pub struct SpaceBin {
    data: Vec<u8>,
    sections: Vec<SectionMeta>,
}

#[derive(Debug, Clone)]
struct SectionMeta {
    id: [u8; 4],
    offset: usize,
    length: usize,
    rows_count: usize,
}

impl SpaceBin {
    pub fn read(path: impl AsRef<Path>) -> Result<Self> {
        let path = path.as_ref();
        let data = fs::read(path).with_context(|| format!("failed to read {}", path.display()))?;
        Self::from_data(data)
    }

    fn from_data(data: Vec<u8>) -> Result<Self> {
        let sections = parse_section_table(&data)?;
        Ok(Self { data, sections })
    }

    pub fn section_data(&self, id: &[u8; 4]) -> Result<&[u8]> {
        let section = self
            .sections
            .iter()
            .find(|section| &section.id == id)
            .ok_or_else(|| anyhow!("section {} not found", section_id_to_string(id)))?;

        let end = section
            .offset
            .checked_add(section.length)
            .ok_or_else(|| anyhow!("section size overflow"))?;

        if end > self.data.len() {
            bail!(
                "section {} out of bounds: offset={} length={} file_len={}",
                section_id_to_string(&section.id),
                section.offset,
                section.length,
                self.data.len()
            );
        }

        Ok(&self.data[section.offset..end])
    }

    #[cfg(test)]
    pub(crate) fn from_bytes(data: Vec<u8>) -> Result<Self> {
        Self::from_data(data)
    }
}

fn parse_section_table(data: &[u8]) -> Result<Vec<SectionMeta>> {
    let root = read_section_meta(data, 0)?;

    if root.id != *b"BWTB" {
        bail!(
            "invalid root section: expected BWTB, got {}",
            section_id_to_string(&root.id)
        );
    }

    let mut sections = Vec::with_capacity(root.rows_count);

    for index in 0..root.rows_count {
        let offset = SECTION_META_SIZE + index * SECTION_META_SIZE;
        sections.push(read_section_meta(data, offset)?);
    }

    Ok(sections)
}

fn read_section_meta(data: &[u8], offset: usize) -> Result<SectionMeta> {
    if offset + SECTION_META_SIZE > data.len() {
        bail!("section metadata out of bounds at offset {}", offset);
    }

    Ok(SectionMeta {
        id: [
            data[offset],
            data[offset + 1],
            data[offset + 2],
            data[offset + 3],
        ],
        offset: read_u32(data, offset + 8)? as usize,
        length: read_u32(data, offset + 16)? as usize,
        rows_count: read_u32(data, offset + 20)? as usize,
    })
}

fn section_id_to_string(id: &[u8; 4]) -> String {
    String::from_utf8_lossy(id).to_string()
}
