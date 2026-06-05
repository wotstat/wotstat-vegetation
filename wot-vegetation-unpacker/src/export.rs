use crate::sections::{bwst, sptr};
use crate::space_bin::SpaceBin;
use anyhow::Result;
use serde::Serialize;
use std::collections::HashMap;

#[derive(Debug, Serialize)]
pub struct VegetationInstance {
    pub asset_name: String,
    pub matrix: [[f32; 4]; 4],
}

pub fn vegetation_export(space: &SpaceBin) -> Result<Vec<VegetationInstance>> {
    let assets = bwst::parse_assets_by_key(space.section_data(b"BWST")?)?;
    let records = sptr::parse(space.section_data(b"SpTr")?)?;

    Ok(link_records(&assets, &records))
}

pub fn vegetation_to_json(vegetation: &[VegetationInstance]) -> Result<String> {
    let mut json = String::from("[\n");

    for (index, item) in vegetation.iter().enumerate() {
        if index > 0 {
            json.push_str(",\n");
        }

        json.push_str("  {\n");
        json.push_str("    \"asset\": ");
        json.push_str(&serde_json::to_string(&item.asset_name)?);
        json.push_str(",\n");
        json.push_str("    \"matrix\": ");
        json.push_str(&serde_json::to_string(&item.matrix)?);
        json.push_str("\n  }");
    }

    json.push_str("\n]\n");
    Ok(json)
}

fn link_records(
    assets: &HashMap<u32, String>,
    records: &[sptr::SptrRecord],
) -> Vec<VegetationInstance> {
    records
        .iter()
        .filter_map(|record| {
            let asset_name = assets.get(&record.asset_key)?;

            Some(VegetationInstance {
                asset_name: asset_name.clone(),
                matrix: record.matrix,
            })
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::space_bin::SpaceBin;

    const ASSET_KEY: u32 = 0x1234_5678;
    const ASSET_NAME: &str = "flora/tree.srt";

    #[test]
    fn vegetation_export_contains_only_asset_name_and_matrix() -> Result<()> {
        let space = SpaceBin::from_bytes(space_bin_fixture())?;
        let vegetation = vegetation_export(&space)?;
        let json = serde_json::to_value(&vegetation)?;

        assert_eq!(vegetation.len(), 1);
        assert_eq!(vegetation[0].asset_name, ASSET_NAME);
        assert_eq!(vegetation[0].matrix[3], [10.0, 20.0, 30.0, 1.0]);
        assert_eq!(json[0].as_object().unwrap().len(), 2);

        let rendered = vegetation_to_json(&vegetation)?;
        let rendered_json: serde_json::Value = serde_json::from_str(&rendered)?;
        let matrix_line = rendered
            .lines()
            .find(|line| line.contains("\"matrix\""))
            .unwrap();

        assert_eq!(rendered_json, json);
        assert!(matrix_line.contains("[["));
        assert!(matrix_line.contains("],["));

        Ok(())
    }

    fn space_bin_fixture() -> Vec<u8> {
        let bwst = bwst_fixture();
        let sptr = sptr_fixture();
        let table_len = 24 + 2 * 24;
        let bwst_offset = table_len;
        let sptr_offset = bwst_offset + bwst.len();

        let mut data = vec![0; table_len];
        write_section_meta(&mut data, 0, b"BWTB", 0, table_len, 2);
        write_section_meta(&mut data, 24, b"BWST", bwst_offset, bwst.len(), 1);
        write_section_meta(&mut data, 48, b"SpTr", sptr_offset, sptr.len(), 1);

        data.extend(bwst);
        data.extend(sptr);
        data
    }

    fn bwst_fixture() -> Vec<u8> {
        let asset_name = format!("{ASSET_NAME}\0");
        let mut data = Vec::new();

        push_u32(&mut data, 12);
        push_u32(&mut data, 1);
        push_u32(&mut data, ASSET_KEY);
        push_u32(&mut data, 0);
        push_u32(&mut data, asset_name.len() as u32);
        push_u32(&mut data, asset_name.len() as u32);
        data.extend(asset_name.as_bytes());

        data
    }

    fn sptr_fixture() -> Vec<u8> {
        let matrix = [
            1.0f32, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 10.0, 20.0, 30.0, 1.0,
        ];
        let mut data = Vec::new();

        push_u32(&mut data, 80);
        push_u32(&mut data, 1);

        for value in matrix {
            data.extend(value.to_le_bytes());
        }

        push_u32(&mut data, ASSET_KEY);
        push_u32(&mut data, 1);
        push_u32(&mut data, 2);
        push_u32(&mut data, 3);

        data
    }

    fn write_section_meta(
        data: &mut [u8],
        offset: usize,
        id: &[u8; 4],
        section_offset: usize,
        length: usize,
        rows_count: usize,
    ) {
        data[offset..offset + 4].copy_from_slice(id);
        write_u32(data, offset + 8, section_offset as u32);
        write_u32(data, offset + 16, length as u32);
        write_u32(data, offset + 20, rows_count as u32);
    }

    fn write_u32(data: &mut [u8], offset: usize, value: u32) {
        data[offset..offset + 4].copy_from_slice(&value.to_le_bytes());
    }

    fn push_u32(data: &mut Vec<u8>, value: u32) {
        data.extend(value.to_le_bytes());
    }
}
