# wotstat-vegetation


## Как добавить свои карты

### Подготовка коллайдера для растения
1. Распакуйте `.pkg` архив с нужными растениями
2. Добавьте в `Blender` два аддона из папки `blender`: `io_srt_loader` и `io_export_wot`
3. Импортируйте `.srt` файл с нужным растением в `Blender`
4. Постройте вокруг него коробку или `Convex Hull` и экспортируйте её в `.model` формате (с помощью аддона `io_export_wot`). Путь экспорта должен быть `res_mods/mods/wotstat-vegetation/colliders/исходный_путь_к_растению.model`, например `/mods/wotstat-vegetation/colliders/vegetation/Broadleaves/Chestnut/Chestnut_10m.model`
