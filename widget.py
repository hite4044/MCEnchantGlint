"""
widget.py
在此项目中用到的:
实用小部件&实用函数
"""
import wx

font_cache: dict[int, wx.Font] = {}


def ft(size: int):
    if size not in font_cache:
        font_cache[size] = wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT)
        font_cache[size].SetPointSize(size)
    return font_cache[size]


class CenteredStaticText(wx.StaticText):
    """使得绘制的文字始终保持在控件中央"""

    def __init__(
            self,
            parent,
            id_=wx.ID_ANY,
            label=wx.EmptyString,
            pos=wx.DefaultPosition,
            size=wx.DefaultSize,
            style=0,
            name=wx.StaticTextNameStr,
            font=None,
            x_center=True,
            y_center=True,
    ):
        super().__init__(parent, id_, label, pos, size, style, name)
        if font is not None:
            self.SetFont(font)
        self.Bind(wx.EVT_PAINT, self.on_paint)
        self.x_center = x_center
        self.y_center = y_center

    def on_paint(self, _):
        dc = wx.PaintDC(self)
        label = self.GetLabel()
        dc.SetFont(self.GetFont())
        text_size = dc.GetTextExtent(label)
        size = self.GetSize()

        dc.DrawText(
            label,
            ((size[0] - text_size[0]) // 2) * int(self.x_center),
            ((size[1] - text_size[1]) // 2) * int(self.y_center),
        )


class LabelTextCtrl(wx.Panel):
    def __init__(self, parent, label, value, size=wx.DefaultSize, style=0, name=wx.StaticTextNameStr):
        super().__init__(parent, style=style, size=size, name=name)
        self.label = CenteredStaticText(self, label=label, size=(-1, 25))
        self.text = wx.TextCtrl(self, value=value)
        self.sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.sizer.Add(self.label, 0, wx.ALIGN_CENTER_VERTICAL)
        self.sizer.Add(self.text, 1, wx.EXPAND)
        self.SetSizer(self.sizer)

    def SetValue(self, value):
        self.text.SetValue(value)

    def GetValue(self):
        return self.text.GetValue()

    def SetLabel(self, label):
        self.label.SetLabel(label)

    def GetLabel(self):
        return self.label.GetLabel()


class LabelSpinCtrl(wx.Panel):
    def __init__(self, parent, label, value, min_=0, max_=100, size=wx.DefaultSize, style=0, name=wx.StaticTextNameStr):
        super().__init__(parent, style=style, size=size, name=name)
        self.label = CenteredStaticText(self, label=label, size=(-1, 25))
        self.text = wx.SpinCtrl(self, value=value, min=min_, max=max_)
        self.sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.sizer.Add(self.label, 0, wx.ALIGN_CENTER_VERTICAL)
        self.sizer.Add(self.text, 1, wx.EXPAND)
        self.SetSizer(self.sizer)

    def SetValue(self, value):
        self.text.SetValue(value)

    def GetValue(self):
        return self.text.GetValue()


class LabelChoice(wx.Panel):
    def __init__(self, parent, label, choices=None, size=wx.DefaultSize, style=0, name=wx.StaticTextNameStr):
        super().__init__(parent, style=style, size=size, name=name)
        if choices is None:
            choices = []
        self.label = CenteredStaticText(self, label=label, size=(-1, 25))
        self.text = wx.Choice(self, choices=choices)
        self.sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.sizer.Add(self.label, 0, wx.ALIGN_CENTER_VERTICAL)
        self.sizer.Add(self.text, 1, wx.EXPAND)
        self.SetSizer(self.sizer)

    def Append(self, choice: str):
        self.text.Append(choice)

    def GetSelection(self):
        return self.text.GetSelection()


class FormatedText(wx.StaticText):
    def __init__(self, parent: wx.Window):
        super().__init__(parent, label="当前文件: None (0/0)\n处理过程: None (0.00%) (0/0)")

    def format(self, filename: str, file_count: int, total_file: int, gen_or_save: bool, value: int, total: int):
        if gen_or_save:
            keyword = "生成帧"
        else:
            keyword = "保存文件"
        self.SetLabel(f"当前文件: {filename} ({file_count}/{total_file})\n"
                      f"处理过程: {keyword} ({100 * (value / total):.2f}%) ({value}/{total})")

    def finish(self, filename: str, total_file: int, total: int):
        self.SetLabel(f"当前文件: {filename} ({total_file}/{total_file})\n"
                      f"处理过程: 完成 (100%) ({total}/{total})")