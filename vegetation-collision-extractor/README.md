# Vegetation Collision Extractor

This tool extracts the low-poly vegetation mesh marked `COLLISION` inside World of Tanks SpeedTree `.srt` files.

## Usage

```bash
python3 tools/vegetation-collision-extractor/extract.py \
  --packages ./packages \
  --object vegetation/Broadleaves/Poplar/Poplar_12m \
  --out ./out/vegetation-collisions/Poplar_12m.obj
```

Use a `.json` output suffix to write vertices and triangle indices as JSON instead of OBJ.
When `packages/scripts/destructibles.xml` has a matching vegetation entry, the extractor also prints and writes its raw `destructibles_density`. It also resolves `packages/vegetation/bushes.xml` and `packages/vegetation/grassBushes.xml` to report whether the object appears to affect camouflage.

```bash
python3 tools/vegetation-collision-extractor/verify_known.py \
  --packages ./packages \
  --out-dir ./out/vegetation-collisions/known
```

## Findings

Collision data for the camouflage vegetation examples is stored inside the `.srt` file itself. It is not stored in an adjacent `.model`, `.visual`, `.primitive`, or `.havok` file.

The SRT string table contains material/resource names such as `COLLISION`, `SOLID`, `NOCOLLIDE`, and `Atlas`. SRT geometry draw calls reference render-state records. In the observed SRT 06.0.0 layout, render-state offsets `664` and `672` are string references for the draw call name/kind. A draw call whose name or kind resolves to `COLLISION` contains the low-poly camouflage collision mesh.

For the known objects:

| Object | Vertices | Triangles | Camouflage | Camouflage Density | Source |
| --- | ---: | ---: | --- | ---: | --- |
| `vegetation/Broadleaves/Chestnut/Chestnut_10m` | 89 | 32 | `true` | `0.5` | `packages/vegetation/Broadleaves/Chestnut/Chestnut_10m.srt` |
| `vegetation/Broadleaves/Poplar/Poplar_12m` | 126 | 48 | `true` | `0.5` | `packages/vegetation/Broadleaves/Poplar/Poplar_12m.srt` |
| `vegetation/Broadleaves/Poplar/Poplar_21m` | 108 | 48 | `true` | `0.5` | `packages/vegetation/Broadleaves/Poplar/Poplar_21m.srt` |
| `vegetation/Broadleaves/Shrubs/Bush_Wild/Bush_Wild_5m` | 17 | 24 | `true` | `0.5` | `packages/vegetation/Broadleaves/Shrubs/Bush_Wild/Bush_Wild_5m.srt` |
| `vegetation/Broadleaves/DryTree/DryTree_Bush_var2` | 24 | 12 | `false` | `0` | `packages/vegetation/Broadleaves/DryTree/DryTree_Bush_var2.srt` |
| `vegetation/Conifers/Pine_Young/Pine_Young_almoust_2m` | 32 | 14 | `false` | `0` | `packages/vegetation/Conifers/Pine_Young/Pine_Young_almoust_2m.srt` |
| `vegetation/Broadleaves/Shrubs/Hawthorn/Hawthorn_03` | 24 | 12 | `false` | `0` | `packages/vegetation/Broadleaves/Shrubs/Hawthorn/Hawthorn_03.srt` |
| `vegetation/Broadleaves/Shrubs/Bush_Wild_Autumn/Bush_Wild_Autumn_5m` | 24 | 12 | `true` | `0.5` | `packages/vegetation/Broadleaves/Shrubs/Bush_Wild_Autumn/Bush_Wild_Autumn_5m.srt` |
| `vegetation/Broadleaves/Oak_dry/Oak_dry_25m` | 27 | 32 | `true` | `0.25` | `packages/vegetation/Broadleaves/Oak_dry/Oak_dry_25m.srt` |
| `vegetation/Broadleaves/Shrubs/Bush_Wild/Bush_Wild_2m` | 24 | 12 | `true` | `0.5` | `packages/vegetation/Broadleaves/Shrubs/Bush_Wild/Bush_Wild_2m.srt` |

Across `packages/vegetation`, all 964 `.srt` files parsed successfully. 376 contain a `COLLISION` string and 376 contain at least one draw call using that `COLLISION` render state. 213 contain a `SOLID` draw call, usually a trunk or rigid-object style mesh rather than the foliage/camouflage mesh.

`SOLID` is not used as a camouflage-positive or camouflage-negative signal. In this dataset, 190 SRTs have both `SOLID` and `COLLISION`; they are classified through the `COLLISION` mesh and metadata rules below. Another 23 SRTs have `SOLID` but no `COLLISION`; those are not treated as camouflage meshes by the extractor. The `--include-solid` option is only for inspection/exporting extra rigid/trunk geometry.

`packages/scripts/destructibles.xml` has 428 vegetation entries with a `density` value. The distribution is 324 entries at `0.5`/`0.50` and 104 entries at `0.25`. Density is not enough by itself: some `grassBushes.xml` objects have both `COLLISION` meshes and destructibles density, but do not affect camouflage.

Current camouflage classification rule:

- If the SRT stem is listed in `packages/vegetation/grassBushes.xml`, treat it as non-camouflage (`camouflage_affects = false`, effective `camouflage_density = 0`).
- If the SRT stem is listed in `packages/vegetation/bushes.xml`, has a `COLLISION` mesh, and has destructibles density, treat it as camouflage-affecting with that density.
- If it is not in either list, has a `COLLISION` mesh, and has destructibles density, treat it as a tree/unlisted camouflage object with that density.
- If it has a `COLLISION` mesh but no destructibles density and is not in either list, report camouflage as unknown.

By this rule, among 376 SRTs with `COLLISION` meshes: 342 are camouflage-affecting, 33 are explicitly non-camouflage because they are listed in `grassBushes.xml`, and 1 is unknown.

## Linkage

The vegetation object path is the resource path of the SRT:

```text
vegetation/Broadleaves/Poplar/Poplar_12m
-> packages/vegetation/Broadleaves/Poplar/Poplar_12m.srt
```

Map `space.bin` files reference these SRT resource paths in their vegetation asset table, matching the existing `parsers/spaceBinUnpacker.py` parser. `packages/scripts/destructibles.xml` references the same SRT paths and stores health, `density`, physics parameters, and destruction effects. `packages/scripts/environment_effects.xml` references the same SRT paths for sound/effect offsets. `packages/vegetation/bushes.xml` is a bush-name list and does not point to separate collision geometry.

## Tested Hypotheses

`SRT collision_objects` block: not the target mesh. The known objects have `speedtree_collision_object_count == 0`. A few other SRTs have 1 to 3 fixed-size SpeedTree collision objects, but those records are 36-byte primitive records, not indexed triangle meshes.

Havok: not used for the known vegetation camouflage meshes. `packages/vegetation` contains zero `.havok`, `.hkx`, or `.hkt` files. Package-wide Havok files use the expected `TAG0` and `SDKV20200200` signatures and are common under normal content/building paths, but known vegetation object names were not found in Havok files.

Adjacent BigWorld model resources: not used for these vegetation meshes. The vegetation directory contains `.srt`, texture `.dds`, and two XML files, with no adjacent `.model`, `.visual_processed`, or `.primitives_processed` resources for the known objects.

## Trees, Bushes, And No-Collision Objects

Trees such as Poplar and Chestnut usually have multiple draw calls: a narrow `SOLID` low-poly trunk, a wider `COLLISION` low-poly foliage/camouflage mesh, render foliage named `Atlas`, and bark render geometry marked `NOCOLLIDE`.

Bushes such as `Bush_Wild_5m` usually have a `COLLISION` low-poly mesh and an `Atlas` render mesh. The collision mesh is much smaller than the render mesh.

Objects without collision, for example `vegetation/Grass/Moss/Moss_lod0`, have render meshes but no `COLLISION` draw call. The extractor reports this with exit code `2`.
