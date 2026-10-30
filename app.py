#!/usr/bin/env python3
"""Простой GUI: список живых обоев Wallpaper Engine и кнопка «Применить»."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
import time
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("XApp", "1.0")
from gi.repository import GdkPixbuf, GLib, Gtk, XApp  # noqa: E402

WORKSHOP_DIR = Path.home() / ".steam/steam/steamapps/workshop/content/431960"
SCRIPT_DIR = Path(__file__).resolve().parent
LIVE_WALL = SCRIPT_DIR / "live_wall.sh"
STATE_FILE = SCRIPT_DIR / "last.json"
THUMB_SIZE = 48
DEFAULT_FPS = 30
DEFAULT_VOLUME = 10


def find_preview(folder: Path) -> Path | None:
    gif = folder / "preview.gif"
    jpg = folder / "preview.jpg"
    if gif.is_file():
        return gif
    if jpg.is_file():
        return jpg
    return None


def load_pixbuf(path: Path, size: int) -> GdkPixbuf.Pixbuf | None:
    try:
        return GdkPixbuf.Pixbuf.new_from_file_at_scale(str(path), size, size, True)
    except GLib.Error:
        return None


def load_wallpapers() -> list[tuple[str, str, Path | None]]:
    items: list[tuple[str, str, Path | None]] = []
    if not WORKSHOP_DIR.is_dir():
        return items

    for folder in WORKSHOP_DIR.iterdir():
        if not folder.is_dir():
            continue
        project = folder / "project.json"
        if not project.is_file():
            continue
        try:
            data = json.loads(project.read_text(encoding="utf-8", errors="replace"))
        except json.JSONDecodeError:
            continue
        title = str(data.get("title") or "").strip() or folder.name
        items.append((title, folder.name, find_preview(folder)))

    items.sort(key=lambda pair: pair[0].casefold())
    return items


def load_state() -> dict:
    if not STATE_FILE.is_file():
        return {}
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_state(wall_id: str, fps: int, volume: int) -> None:
    payload = {"wall_id": wall_id, "fps": fps, "volume": volume}
    STATE_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class App(Gtk.Window):
    def __init__(self) -> None:
        super().__init__(title="Cinnamon Live Wallpaper")
        self.set_default_size(520, 560)
        self.set_border_width(12)
        self.connect("delete-event", self._on_delete)

        self.wallpapers: list[tuple[str, str, Path | None]] = []
        self._busy = False
        self._empty_thumb = GdkPixbuf.Pixbuf.new(
            GdkPixbuf.Colorspace.RGB, True, 8, THUMB_SIZE, THUMB_SIZE
        )
        self._empty_thumb.fill(0x00000000)

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.add(root)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        title = Gtk.Label(label="Обои Wallpaper Engine", xalign=0)
        title.set_hexpand(True)
        refresh_btn = Gtk.Button(label="Обновить")
        refresh_btn.connect("clicked", lambda _b: self.refresh())
        header.pack_start(title, True, True, 0)
        header.pack_start(refresh_btn, False, False, 0)
        root.pack_start(header, False, False, 0)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)

        self.store = Gtk.ListStore(GdkPixbuf.Pixbuf, str, str)  # thumb, title, id
        self.tree = Gtk.TreeView(model=self.store)
        self.tree.set_headers_visible(False)
        column = Gtk.TreeViewColumn("Обои")
        thumb_cell = Gtk.CellRendererPixbuf()
        text_cell = Gtk.CellRendererText()
        text_cell.set_property("xpad", 8)
        column.pack_start(thumb_cell, False)
        column.pack_start(text_cell, True)
        column.add_attribute(thumb_cell, "pixbuf", 0)
        column.add_attribute(text_cell, "text", 1)
        self.tree.append_column(column)
        selection = self.tree.get_selection()
        selection.set_mode(Gtk.SelectionMode.SINGLE)
        selection.connect("changed", self._on_select)
        self.tree.connect("row-activated", lambda *_a: self.apply())
        scrolled.add(self.tree)
        root.pack_start(scrolled, True, True, 0)

        self.status = Gtk.Label(label="", xalign=0)
        self.status.set_line_wrap(True)
        root.pack_start(self.status, False, False, 0)

        controls = Gtk.Grid()
        controls.set_column_spacing(8)
        controls.set_row_spacing(8)
        controls.set_column_homogeneous(False)

        fps_label = Gtk.Label(label="FPS", xalign=0)
        self.fps_entry = Gtk.Entry()
        self.fps_entry.set_text(str(DEFAULT_FPS))
        self.fps_entry.set_width_chars(6)
        self.fps_entry.set_input_purpose(Gtk.InputPurpose.DIGITS)

        vol_label = Gtk.Label(label="Громкость", xalign=0)
        self.volume_value = Gtk.Label(label=str(DEFAULT_VOLUME), xalign=1)
        self.volume_value.set_width_chars(3)
        self.volume_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self.volume_scale.set_value(DEFAULT_VOLUME)
        self.volume_scale.set_draw_value(False)
        self.volume_scale.set_hexpand(True)
        self.volume_scale.connect("value-changed", self._on_volume_changed)

        controls.attach(fps_label, 0, 0, 1, 1)
        controls.attach(self.fps_entry, 1, 0, 1, 1)
        controls.attach(vol_label, 0, 1, 1, 1)
        vol_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        vol_row.pack_start(self.volume_scale, True, True, 0)
        vol_row.pack_start(self.volume_value, False, False, 0)
        controls.attach(vol_row, 1, 1, 1, 1)
        root.pack_start(controls, False, False, 0)

        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        buttons.set_halign(Gtk.Align.END)
        fix_btn = Gtk.Button(label="Исправить иконки")
        fix_btn.connect("clicked", lambda _b: self.fix_icons_express())
        self.apply_btn = Gtk.Button(label="Применить")
        self.apply_btn.connect("clicked", lambda _b: self.apply())
        buttons.pack_start(fix_btn, False, False, 0)
        buttons.pack_start(self.apply_btn, False, False, 0)
        root.pack_start(buttons, False, False, 0)

        self._setup_tray()

        self.refresh()
        if self._restore_state():
            GLib.idle_add(self.apply)

    def refresh(self) -> None:
        current_id = None
        selected = self._selected()
        if selected:
            current_id = selected[1]

        self.wallpapers = load_wallpapers()
        self.store.clear()
        for title, wall_id, preview in self.wallpapers:
            thumb = load_pixbuf(preview, THUMB_SIZE) if preview else None
            self.store.append([thumb or self._empty_thumb, title, wall_id])

        if not WORKSHOP_DIR.is_dir():
            self.status.set_text(f"Папка не найдена: {WORKSHOP_DIR}")
        elif not self.wallpapers:
            self.status.set_text("Обои не найдены (нет project.json)")
        else:
            self.status.set_text(f"Найдено: {len(self.wallpapers)}")

        if current_id:
            self._select_id(current_id)

    def _selected(self) -> tuple[str, str] | None:
        model, tree_iter = self.tree.get_selection().get_selected()
        if tree_iter is None:
            return None
        title, wall_id = model[tree_iter][1], model[tree_iter][2]
        return title, wall_id

    def _select_id(self, wall_id: str) -> bool:
        tree_iter = self.store.get_iter_first()
        while tree_iter is not None:
            if self.store[tree_iter][2] == wall_id:
                path = self.store.get_path(tree_iter)
                self.tree.get_selection().select_iter(tree_iter)
                self.tree.scroll_to_cell(path, None, True, 0.3, 0.0)
                return True
            tree_iter = self.store.iter_next(tree_iter)
        return False

    def _restore_state(self) -> bool:
        state = load_state()
        fps = state.get("fps", DEFAULT_FPS)
        volume = state.get("volume", DEFAULT_VOLUME)
        wall_id = str(state.get("wall_id") or "")

        if isinstance(fps, int) and fps > 0:
            self.fps_entry.set_text(str(fps))
        if isinstance(volume, (int, float)):
            volume = max(0, min(100, int(round(volume))))
            self.volume_scale.set_value(volume)
            self.volume_value.set_text(str(volume))

        return bool(wall_id) and self._select_id(wall_id)

    def _on_select(self, _selection: Gtk.TreeSelection) -> None:
        item = self._selected()
        if item:
            title, wall_id = item
            self.status.set_text(f"{title}  ·  ID {wall_id}")

    def _on_volume_changed(self, scale: Gtk.Scale) -> None:
        self.volume_value.set_text(str(int(round(scale.get_value()))))

    def _fps(self) -> int | None:
        raw = self.fps_entry.get_text().strip()
        if not raw.isdigit() or int(raw) <= 0:
            return None
        return int(raw)

    def apply(self) -> None:
        item = self._selected()
        if not item:
            self._alert("Выбери обои в списке.")
            return
        fps = self._fps()
        if fps is None:
            self._alert("FPS должен быть целым числом больше 0.")
            return
        _title, wall_id = item
        volume = int(round(self.volume_scale.get_value()))
        save_state(wall_id, fps, volume)
        self._run_script(wall_id, fps, volume)

    def fix_icons(self) -> None:
        self._run_script("--fix-icons", 0, 0)

    def fix_icons_express(self) -> None:
        self._run_script("--fix-icons-express", 0, 0)

    def _run_script(self, wall_id: str, fps: int, volume: int) -> None:
        if self._busy:
            return
        if not LIVE_WALL.is_file():
            self._alert(f"Не найден скрипт: {LIVE_WALL}")
            return
        if fps!=0:
            os.system("pkill -x linux-wallpaper")
        self._busy = True
        self.apply_btn.set_sensitive(False)
        self.status.set_text(f"Запуск live_wall.sh {wall_id}…")

        def worker() -> None:
            os.chdir(SCRIPT_DIR)
            # Скрипт ждёт linux-wallpaperengine, поэтому запускаем в фоне,
            # чтобы GUI не зависал до остановки обоев.
            os.system(f"./live_wall.sh {wall_id} {fps} {volume} &")
            GLib.idle_add(self._done, wall_id)

        threading.Thread(target=worker, daemon=True).start()

    def _done(self, wall_id: str) -> bool:
        self._busy = False
        self.apply_btn.set_sensitive(True)
        self.status.set_text(f"Скрипт запущен: {wall_id}")
        return False

    def _setup_tray(self) -> None:
        menu = Gtk.Menu()
        show_item = Gtk.MenuItem(label="Показать")
        show_item.connect("activate", self._show_window)
        quit_item = Gtk.MenuItem(label="Выйти")
        quit_item.connect("activate", self._quit_app)
        menu.append(show_item)
        menu.append(quit_item)
        menu.show_all()

        self.tray = XApp.StatusIcon()
        self.tray.set_name("cinnamon-live-wallpaper")
        self.tray.set_icon_name("preferences-desktop-wallpaper")
        self.tray.set_tooltip_text("Cinnamon Live Wallpaper")
        self.tray.set_primary_menu(menu)
        self.tray.set_secondary_menu(menu)

    def _on_delete(self, *_args) -> bool:
        self.hide()
        return True

    def _show_window(self, *_args) -> None:
        self.show_all()
        self.present()

    def _quit_app(self, *_args) -> None:
        os.system("pkill -x linux-wallpaper")
        Gtk.main_quit()

    def _alert(self, text: str) -> None:
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text=text,
        )
        dialog.run()
        dialog.destroy()


def main() -> None:
    GLib.set_prgname("cinnamon-live-wallpaper")
    GLib.set_application_name("Cinnamon Live Wallpaper")
    app = App()
    app.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()
