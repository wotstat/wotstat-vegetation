# wotstat-vegetation


## Как добавить свои карты

### Экспорт координат растительности
Из архива с картой `.pkg` достаньте файл `space.bin` и распакуйте его с помощью `wot-vegetation-unpacker`

Например, для карты `Himmelsdorf` это будет выглядеть так:
```
cargo run --  ./spaces/04_himmelsdorf/space.bin -o 04_himmelsdorf.json
```

На выходе вы получите файл `04_himmelsdorf.json` с координатами растительности на карте `Himmelsdorf`. Разместите его в папке `res_mods/mods/wotstat-vegetation/maps/04_himmelsdorf.json`

### Подготовка коллайдера для растения
1. Распакуйте `.pkg` архив с нужными растениями
2. Добавьте в `Blender` два аддона из папки `blender`: `io_srt_loader` и `io_export_wot`
3. Импортируйте `.srt` файл с нужным растением в `Blender`
4. Постройте вокруг него коробку или `Convex Hull` и экспортируйте её в `.model` формате (с помощью аддона `io_export_wot`). Путь экспорта должен быть `res_mods/mods/wotstat-vegetation/colliders/исходный_путь_к_растению.model`, например `/mods/wotstat-vegetation/colliders/vegetation/Broadleaves/Chestnut/Chestnut_10m.model`
