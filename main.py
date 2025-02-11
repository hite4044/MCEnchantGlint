from dataclasses import dataclass
from enum import Enum
from os import listdir, mkdir
from os.path import isfile, basename, join, isdir
from threading import Thread
from time import perf_counter
from typing import Callable

import wx
from PIL import Image, ImageFilter, ImageEnhance

from widget import CenteredStaticText, ft, LabelTextCtrl, LabelSpinCtrl, LabelChoice, FormatedText

DEBUG = True


@dataclass
class AssetItem:
    file_path: str
    icon: wx.Bitmap


class OutputWay(Enum):
    ONEFILE_GIF = 0
    ONEFILE_APNG = 1
    ONEFILE_WEBP = 2
    FRAMES_PNG = 3
    FRAMES_JPG = 4


end_fix_trans_map = {
    OutputWay.ONEFILE_GIF: "gif",
    OutputWay.ONEFILE_APNG: "png",
    OutputWay.ONEFILE_WEBP: "webp",
    OutputWay.FRAMES_PNG: "png",
    OutputWay.FRAMES_JPG: "jpg"
}


class FileDropTarget(wx.FileDropTarget):
    def __init__(self, window: wx.Window, on_pick_cbk: Callable[[list[str]], None]):
        wx.FileDropTarget.__init__(self)
        self.window = window
        self.cbk = on_pick_cbk

    def OnDropFiles(self, x, y, filenames):
        self.cbk(filenames)
        return True


def load_glint(scale: int):
    # (164, 84, 255) to (26, 8, 48) (79, 37, 129)
    def convert_as_alpha(point: tuple[int, int, int, int]):
        return point[0], point[1], point[2], 255 - int(
            ((112 - point[0]) / 138 + (68 - point[1]) / 76 + (159 - point[2]) / 207) * 85)

    glint_cover = Image.open(join("enchanted_glint_item.png")).convert("RGBA")
    # noinspection PyTypeChecker
    [[glint_cover.putpixel((x, y), convert_as_alpha(glint_cover.getpixel((x, y)))) for x in range(glint_cover.width)]
     for y in range(glint_cover.height)]
    glint_cover = glint_cover.resize(tuple(map(lambda x: x * scale, glint_cover.size)))
    glint_cover = glint_cover.filter(ImageFilter.GaussianBlur(3))
    glint_cover = ImageEnhance.Brightness(glint_cover).enhance(1.2)
    glint_cover = Image.merge("RGBA", [*glint_cover.split()[:3], glint_cover.getchannel("A").point(lambda x: x // 2)])
    return glint_cover


def crop_and_paste(raw_image: Image.Image, glint: Image.Image, crop_start_x: int, crop_start_y: int, crop_stop_x: int,
                   crop_stop_y: int, paste_x: int, paste_y: int):
    cropped_glint: Image.Image = glint.crop((crop_start_x, crop_start_y, crop_stop_x, crop_stop_y)).convert("RGBA")
    mask: Image.Image = Image.new("L", cropped_glint.size)
    mask.paste(cropped_glint.getchannel("A"), (0, 0), raw_image.crop(
        (paste_x, paste_y, paste_x + cropped_glint.width, paste_y + cropped_glint.height)).getchannel("A"))
    raw_image.paste(cropped_glint, (paste_x, paste_y), mask)


def process_an_file(filename: str, glint: Image.Image, frame_count: int, scale: int, cbk: Callable[[int], None]) -> \
        list[Image]:
    raw_image = Image.open(filename).convert("RGBA")
    raw_image = raw_image.resize(tuple(map(lambda x: x * scale, raw_image.size)), resample=Image.Resampling.BOX)
    frames = []
    x_offset = 0
    y_offset = 0
    width, height = glint.size
    for i in range(0, frame_count):
        cbk(i + 1)
        enchanted = raw_image.copy()
        crop_start_x, crop_start_y = x_offset % width, y_offset % height
        crop_stop_x, crop_stop_y = crop_start_x + enchanted.width, crop_start_y + enchanted.height

        if frame_count == 1:
            enchanted.show()
        crop_and_paste(enchanted, glint, crop_start_x, crop_start_y, min(crop_stop_x, width), min(crop_stop_y, height),
                       0, 0)
        if crop_start_x + enchanted.width > width and crop_start_y + enchanted.height > height:
            crop_and_paste(enchanted, glint, 0, 0, crop_stop_x - width, crop_stop_y - height,
                           enchanted.width - (crop_stop_x - width), enchanted.height - (crop_stop_y - height))
        if crop_start_x + enchanted.width > width:
            crop_and_paste(enchanted, glint, 0, crop_start_y, crop_stop_x - width, min(crop_stop_y, height),
                           enchanted.width - (crop_stop_x - width), 0)
        if crop_start_y + enchanted.height > height:
            crop_and_paste(enchanted, glint, crop_start_x, 0, min(crop_stop_x, width), crop_stop_y - height,
                           0, enchanted.height - (crop_stop_y - height))
        frames.append(enchanted)
        x_offset += -2
        y_offset += 2
    return frames


def output_frames(filename: str, output_dir: str, frames: list[Image.Image], output_way: OutputWay,
                  cbk: Callable[[int], None]):
    if output_way in [OutputWay.ONEFILE_GIF, OutputWay.ONEFILE_APNG, OutputWay.ONEFILE_WEBP]:
        end_fix: str = end_fix_trans_map[output_way]
        frames[0].save(join(output_dir, basename(filename).split(".")[0] + "." + end_fix), end_fix.upper(),
                       save_all=True, append_images=frames, duration=1000 / 20, loop=0)
    elif output_way in [OutputWay.FRAMES_PNG, OutputWay.FRAMES_JPG]:
        end_fix: str = end_fix_trans_map[output_way]
        if isdir(join(output_dir, filename)):
            counter = 1
            while True:
                if not isdir(join(output_dir, filename + f" ({counter})")):
                    dir_name = join(output_dir, filename + f" ({counter})")
                    break
        else:
            dir_name = join(output_dir, filename)
        mkdir(dir_name)
        for i, frame in enumerate(frames):
            cbk(i + 1)
            frame.save(join(dir_name, f"{basename(filename).split('.')[0]}_{i}.{end_fix}"), end_fix.upper())
    else:
        raise ValueError("Invalid output way")


class GUI(wx.Frame):
    def __init__(self, parent=None):
        wx.Frame.__init__(self, parent, title="MC附魔光效叠加器", size=(800, 700))
        self.last_progress_upt = perf_counter()
        self.out_panel = wx.Panel(self)
        self.chs_panel = wx.Panel(self.out_panel)
        self.file_dropper = CenteredStaticText(self.chs_panel, label="拖放文件到这里")
        self.file_dropper.SetDropTarget(FileDropTarget(self.file_dropper, self.add_files_to_list))
        self.file_chooser = wx.FilePickerCtrl(self.chs_panel,
                                              message="选择要处理的文件",
                                              wildcard="*.*",
                                              style=wx.FLP_USE_TEXTCTRL | wx.FLP_FILE_MUST_EXIST)
        self.add_btn = wx.Button(self.chs_panel, label="添加")
        self.ready_assets: list[str] = []
        self.ready_assets_icons: list[wx.Bitmap] = []
        self.ready_assets_images = wx.ImageList(64, 64)
        self.ready_assets_lc = wx.ListCtrl(self.chs_panel, style=wx.LC_ICON)
        self.ready_assets_lc.AssignImageList(self.ready_assets_images, wx.IMAGE_LIST_NORMAL)

        self.proc_panel = wx.Panel(self.out_panel)
        self.out_dir_chs_btn = wx.DirPickerCtrl(self.proc_panel,
                                                message="选择输出文件夹",
                                                style=wx.DD_NEW_DIR_BUTTON | wx.DD_DIR_MUST_EXIST)
        self.out_dir_tc = LabelTextCtrl(self.proc_panel, "输出到: ", "")
        self.out_way_chooser = LabelChoice(self.proc_panel, "输出方式: ")
        self.out_way_chooser.Append("输出GIF动图 (掉san)")
        self.out_way_chooser.Append("输出PNG动图 (无损)")
        self.out_way_chooser.Append("输出WEBP动图 (微损)")
        self.out_way_chooser.Append("输出每一帧 (png)")
        self.out_way_chooser.Append("输出每一帧 (jpg)")
        self.frames_chs = LabelSpinCtrl(self.proc_panel, value="1650", label="输出总帧数 (20帧/s): ", min_=1,
                                        max_=114514)
        self.glint_scale = LabelSpinCtrl(self.proc_panel, value="4", label="光效缩放: ", min_=2, max_=8)
        self.input_scale = LabelSpinCtrl(self.proc_panel, value="10", label="输入缩放: ", min_=1, max_=20)
        self.start_process_btn = wx.Button(self.proc_panel, label="开始处理")
        self.out_shower = AniPhotosViewer(self.proc_panel)

        self.progress_panel = wx.Panel(self)
        self.tip_text = FormatedText(self.progress_panel)
        self.progress_bar_file = wx.Gauge(self.progress_panel, range=100)
        self.progress_bar_frame = wx.Gauge(self.progress_panel, range=100)

        chs_sizer = wx.BoxSizer(wx.VERTICAL)
        chs_sizer.Add(self.file_dropper, 1, wx.EXPAND)
        chs_sizer.Add(self.file_chooser, 0, wx.EXPAND)
        chs_sizer.Add(self.add_btn, 0, wx.EXPAND)
        chs_sizer.AddSpacer(10)
        chs_sizer.Add(wx.StaticLine(self.chs_panel), 0, wx.EXPAND)
        chs_sizer.AddSpacer(7)
        chs_sizer.Add(CenteredStaticText(self.chs_panel, label="已选文件", font=ft(12), y_center=False), 0, wx.EXPAND)
        chs_sizer.Add(self.ready_assets_lc, 1, wx.EXPAND)
        self.chs_panel.SetSizer(chs_sizer)
        proc_sizer = wx.BoxSizer(wx.VERTICAL)
        proc_sizer.Add(CenteredStaticText(self.proc_panel, label="处理文件", font=ft(12), y_center=False), 0, wx.EXPAND)
        proc_sizer.AddSpacer(3)
        proc_sizer.Add(self.out_dir_chs_btn, 0, wx.EXPAND)
        proc_sizer.AddSpacer(1)
        proc_sizer.Add(self.out_dir_tc, 0, wx.EXPAND)
        proc_sizer.AddSpacer(2)
        proc_sizer.Add(self.out_way_chooser, 0, wx.EXPAND)
        proc_sizer.AddSpacer(2)
        proc_sizer.Add(self.frames_chs, 0, wx.EXPAND)
        proc_sizer.AddSpacer(1)
        proc_sizer.Add(self.glint_scale, 0, wx.EXPAND)
        proc_sizer.AddSpacer(1)
        proc_sizer.Add(self.input_scale, 0, wx.EXPAND)
        proc_sizer.AddSpacer(2)
        proc_sizer.Add(self.start_process_btn, 0, wx.EXPAND)
        proc_sizer.AddSpacer(2)
        proc_sizer.Add(self.out_shower, 1, wx.EXPAND)
        self.proc_panel.SetSizer(proc_sizer)
        out_sizer = wx.BoxSizer(wx.HORIZONTAL)
        out_sizer.Add(self.chs_panel, proportion=1, flag=wx.EXPAND)
        out_sizer.Add(wx.StaticLine(self.out_panel, style=wx.LI_VERTICAL), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 5)
        out_sizer.Add(self.proc_panel, proportion=1, flag=wx.EXPAND)
        self.out_panel.SetSizer(out_sizer)
        progress_sizer = wx.BoxSizer(wx.VERTICAL)
        progress_sizer.Add(self.tip_text, 0, wx.EXPAND)
        progress_sizer.AddSpacer(5)
        progress_sizer.Add(self.progress_bar_file, 0, wx.EXPAND)
        progress_sizer.AddSpacer(5)
        progress_sizer.Add(self.progress_bar_frame, 0, wx.EXPAND)
        self.progress_panel.SetSizer(progress_sizer)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.out_panel, proportion=1, flag=wx.EXPAND | wx.ALL, border=5)
        sizer.Add(self.progress_panel, proportion=0, flag=wx.EXPAND | wx.ALL, border=5)
        self.SetSizer(sizer)

        self.file_dropper.SetMaxSize((-1, 200))
        self.file_dropper.SetFont(ft(32))
        self.start_process_btn.SetFont(ft(16))
        self.start_process_btn.Bind(wx.EVT_BUTTON, self.start_process)
        self.ready_assets_lc.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, self.on_ready_item_menu)
        self.add_btn.Bind(wx.EVT_BUTTON, lambda _: self.add_files_to_list([self.file_chooser.GetPath()]))
        self.out_dir_chs_btn.Bind(wx.EVT_DIRPICKER_CHANGED,
                                  lambda _: self.out_dir_tc.SetValue(self.out_dir_chs_btn.GetPath()))
        self.SetBackgroundColour(self.file_dropper.GetBackgroundColour())
        if DEBUG:
            self.out_dir_tc.SetValue(r"D:\Desktop\114514")
            self.out_way_chooser.text.SetSelection(2)
            self.frames_chs.SetValue("300")

    def start_process(self, _):
        Thread(target=self.process_frames, args=(), daemon=True).start()

    def process_frames(self):
        output_dir = self.out_dir_tc.GetValue()
        if self.out_way_chooser.GetSelection() == -1:
            wx.MessageBox("请选择输出方式", "错误", wx.ICON_ERROR)
            return
        output_way = OutputWay(self.out_way_chooser.GetSelection())
        if not isdir(output_dir):
            wx.MessageBox("输出文件夹不存在", "错误", wx.ICON_ERROR)
            return
        frame_count = self.frames_chs.GetValue()
        glint_scale = self.glint_scale.GetValue()
        input_scale = self.input_scale.GetValue()

        glint = load_glint(glint_scale)
        files_count = len(self.ready_assets)
        for i, filename in enumerate(self.ready_assets):
            file_basename = basename(filename)
            print("正在处理: " + filename)
            self.update_progress(file_basename, i, files_count, True, 0, frame_count, True)
            frames = process_an_file(filename, glint, frame_count, input_scale,
                                     lambda x: self.update_progress(file_basename, i, files_count, True, x,
                                                                    frame_count))
            print("正在保存: " + basename(filename))
            self.update_progress(file_basename, i, files_count, False, 0, -1, True)
            output_frames(basename(filename), output_dir, frames, output_way,
                          lambda x: self.update_progress(file_basename, i, files_count, False, x, frame_count))
        self.finish_progress("无", files_count, frame_count)
        self.out_shower.load_dir(output_dir)
        wx.MessageBox("处理完成", "处理完成", wx.ICON_INFORMATION)
        wx.CallAfter(self.ready_assets_lc.ClearAll)
        wx.CallAfter(self.ready_assets.clear)
        wx.CallAfter(self.ready_assets_icons.clear)

    def update_progress(self, filename: str, file_count: int, total_file: int, gen_or_save: bool, value: int,
                        total: int, now: bool = False):
        if not perf_counter() - self.last_progress_upt > 0.1:
            if not now:
                return
        self.last_progress_upt = perf_counter()
        self.tip_text.format(filename, file_count, total_file, gen_or_save, value, total)
        if self.progress_bar_file.GetValue() != file_count:
            self.progress_bar_file.SetRange(total_file)
            self.progress_bar_file.SetValue(file_count)
        self.progress_bar_frame.SetRange(total)
        self.progress_bar_frame.SetValue(value)

    def finish_progress(self, filename: str, total_file: int, total: int):
        self.tip_text.finish(filename, total_file, total)
        self.progress_bar_file.SetValue(self.progress_bar_file.GetRange())
        self.progress_bar_frame.SetValue(self.progress_bar_frame.GetRange())

    def add_files_to_list(self, filenames: list[str]):
        for filename in filenames:
            if isfile(filename):
                icon_pil = Image.open(filename)
                icon = wx.Bitmap(64, 64)
                icon_pil = icon_pil.resize((64, 64), resample=Image.Resampling.BOX).convert("RGBA")
                icon.CopyFromBuffer(icon_pil.tobytes(), wx.BitmapBufferFormat_RGBA)
                line = self.ready_assets_lc.GetItemCount()
                self.ready_assets_lc.InsertItem(line, basename(filename), self.ready_assets_images.Add(icon))
                self.ready_assets.append(filename)
                self.ready_assets_icons.append(icon)

    def on_ready_item_menu(self, event: wx.ListEvent):
        menu = wx.Menu()
        menu.Append(wx.ID_ANY, "删除")
        menu.Bind(wx.EVT_MENU, lambda _: self.remove_item(event.GetIndex()))
        self.PopupMenu(menu)

    def remove_item(self, index: int):
        self.ready_assets_lc.Freeze()
        for i in range(0, len(self.ready_assets_icons)):
            self.ready_assets_images.Remove(i)
        self.ready_assets.pop(index)
        self.ready_assets_icons.pop(index)
        self.ready_assets_lc.ClearAll()
        for i, filename in enumerate(self.ready_assets):
            icon = self.ready_assets_icons[i]
            self.ready_assets_lc.InsertItem(i, basename(filename), self.ready_assets_images.Add(icon))
        self.ready_assets_lc.Thaw()
        self.ready_assets_lc.Refresh()


class AniPhotosViewer(wx.Panel):
    def __init__(self, parent: wx.Window):
        wx.Panel.__init__(self, parent)
        self.active_dir: str | None = None
        self.photo_lc = wx.ListCtrl(self, style=wx.LC_REPORT)
        self.photo_lc.InsertColumn(0, "文件名", width=150)
        self.viewer = AniPhotoShower(self)
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(self.photo_lc, 3, wx.EXPAND)
        sizer.Add(self.viewer, 7, wx.EXPAND)
        self.SetSizer(sizer)
        self.photo_lc.Bind(wx.EVT_LIST_ITEM_SELECTED, self.on_item_selected)
        self.load_dir("D:\儿子文件\编程\python\PyCharm项目\MCEnchantGlint\output_test")

    def load_dir(self, dir_path: str):
        self.active_dir = dir_path
        self.photo_lc.DeleteAllItems()
        for filename in listdir(dir_path):
            self.photo_lc.InsertItem(self.photo_lc.GetItemCount(), filename)

    def on_item_selected(self, event: wx.ListEvent):
        index = event.GetIndex()
        file_or_dir_path = join(self.active_dir, self.photo_lc.GetItemText(index))
        way = None
        if isdir(file_or_dir_path):
            if file_or_dir_path.endswith(".png"):
                way = OutputWay.FRAMES_PNG
            elif file_or_dir_path.endswith(".jpg"):
                way = OutputWay.FRAMES_JPG
        elif isfile(file_or_dir_path):
            if file_or_dir_path.endswith(".gif"):
                way = OutputWay.ONEFILE_GIF
            elif file_or_dir_path.endswith(".webp"):
                way = OutputWay.ONEFILE_WEBP
            elif file_or_dir_path.endswith(".png"):
                way = OutputWay.ONEFILE_APNG
        if way is None:
            return
        self.viewer.load_ani_photo(self.active_dir, self.photo_lc.GetItemText(index), way)


class AniPhotoShower(wx.Control):
    def __init__(self, parent: wx.Window):
        super().__init__(parent)
        self.correct_frame_index = 0
        self.start_play = perf_counter()
        self.frames_count = 0
        self.correct_bitmap = None
        self.fps = 20
        self.frames: list[Image.Image] = []
        self.upt_call = None
        self.Bind(wx.EVT_PAINT, self.on_paint)
        self.Bind(wx.EVT_SIZING, self.on_size)
        self.SetDoubleBuffered(True)

    def load_ani_photo(self, dir_path: str, filename: str, output_way: OutputWay):
        if self.upt_call:
            self.upt_call.Stop()
        self.frames.clear()
        if output_way in [OutputWay.ONEFILE_GIF, OutputWay.ONEFILE_WEBP, OutputWay.ONEFILE_APNG]:
            image = Image.open(join(dir_path, filename))
            for i in range(getattr(image, "n_frames")):
                image.seek(i)
                self.frames.append(image.copy())
        elif output_way in [OutputWay.FRAMES_PNG, OutputWay.FRAMES_JPG]:
            filename2 = ""
            for filename2 in listdir(join(dir_path, filename)):
                break
            index = 0
            start, end = filename2[0: filename2.rindex("_") + 1], filename2[filename2.rindex("."):]
            while True:
                photo_fp = join(dir_path, filename, start + str(index) + end)
                if isfile(photo_fp):
                    image = Image.open(photo_fp)
                    self.frames.append(image)
                    index += 1
                else:
                    break
        self.start_play = perf_counter()
        self.correct_frame_index = 0
        self.frames_count = len(self.frames)
        self.upt_call = wx.CallAfter(self.update_photo)

    def update_photo(self):
        during = perf_counter() - self.start_play
        now_frame_index = int(during / (1 / self.fps))
        try:
            if now_frame_index >= len(self.frames):
                self.correct_frame_index = 0
                self.start_play = perf_counter()
                self.load_bitmap()
                self.Refresh()
            elif now_frame_index != self.correct_frame_index:
                self.correct_frame_index = now_frame_index
                self.load_bitmap()
                self.Refresh()
            self.upt_call = wx.CallLater(int(1000 / self.fps), self.update_photo)
        except RuntimeError:
            pass

    def load_bitmap(self):
        image: Image.Image = self.frames[self.correct_frame_index]
        wx_image = wx.Image(image.width, image.height)
        wx_image.SetData(image.convert("RGB").tobytes())
        try:
            wx_image.SetAlpha(image.getchannel("A").tobytes())
        except ValueError:
            pass

        if self.correct_bitmap:
            self.correct_bitmap.Destroy()
        self.correct_bitmap = wx_image.ConvertToBitmap()

    def on_paint(self, _):
        dc = wx.PaintDC(self)
        dc.Clear()
        if self.correct_bitmap:
            center = (int((self.GetSize()[0] - self.correct_bitmap.GetWidth()) / 2),
                      int((self.GetSize()[1] - self.correct_bitmap.GetHeight()) / 2))
            dc.DrawBitmap(self.correct_bitmap, *center, useMask=True)
            dc.SetPen(wx.Pen(wx.Colour(6, 176, 37)))
            dc.SetBrush(wx.Brush(wx.Colour(6, 176, 37)))
            dc.DrawRectangle(0, 0, int(self.GetSize()[0] * (self.correct_frame_index / self.frames_count)), 20)
            tip = f"{self.correct_frame_index}/{self.frames_count} ({self.fps}FPS)"
            dc.DrawText(tip, self.GetSize()[0] - dc.GetTextExtent(tip)[0] - 5, 20)

    def on_size(self, event: wx.SizeEvent):
        self.Refresh()
        event.Skip()


def test():
    glint = load_glint(4)
    frames = process_an_file(r"D:\Desktop\textures\item\acacia_boat.png", glint, 1650, 1, lambda x: None)
    print("Writing frames...")
    frames[0].save("acacia_boat.webp", "WEBP", save_all=True, append_images=frames, duration=1000 / 20, loop=0)


if __name__ == "__main__":
    app = wx.App()
    control_panel = GUI(None)
    control_panel.Show()
    app.MainLoop()
