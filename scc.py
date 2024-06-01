import matplotlib.pyplot as plt
from matplotlib import transforms
import matplotlib.font_manager as font_manager
from collections import defaultdict
import numpy as np
import pandas as pd


class Chart:
    def __init__(self, date_format, start_date, width, major_grid_on, minor_grid_on, floor_grid_on, y_label, style_color='#5a93cc', custom_grid_color='#71B8FF'):
        self.date_format = date_format
        self.start_date = start_date
        self.width = width
        self.major_grid_on = major_grid_on
        self.minor_grid_on = minor_grid_on
        self.floor_grid_on = floor_grid_on
        self.y_label = y_label
        self.style_color = style_color
        self.custom_grid_color = custom_grid_color
        self.minor_grid_width = 0.3
        self.major_grid_width = 0.1555 * width
        self.x_tick_length = width * 0.666
        self.style_color = style_color
        self.font = self.select_font()
        self.general_fontsize = width * 1.33
        self.credit_fontsize = width * 0.88
        self.right_y_axis_fontsize = width
        self.top_x_label_pad = width * 1

        self.major_grid_line_objects = []
        self.floor_grid_line_objects = []

        if self.start_date is None:
            self.start_date = pd.to_datetime('today')
        else:
            if isinstance(self.start_date, str):
                if date_format:
                    self.start_date = pd.to_datetime(self.start_date, format=self.date_format)
                else:
                    self.start_date = pd.to_datetime(self.start_date)

    def select_font(self):
        desired_fonts = ["Liberation Sans", "Arial", "Helvetica", "sans-serif"]
        available_fonts = set(f.name for f in font_manager.fontManager.ttflist)

        for font in desired_fonts:
            if font in available_fonts:
                return font
        return "sans-serif"

    def major_grid_lines(self, grid_on):
        for line in self.major_grid_line_objects:
            line.set_visible(grid_on)

    def minor_grid_lines(self, grid_on):
        if grid_on:
            self.ax.grid(which="both", visible=grid_on, color=self.custom_grid_color, linewidth=0.3)
        else:
            self.ax.grid(which="both", visible=grid_on)

    def floor_grid_lines(self, grid_on):
        for floor_line in self.floor_grid_line_objects:
            floor_line.set_visible(grid_on)

    def get_figure(self):
        return self.fig, self.ax

    def count_month_clusters(self, dates):
        clusters = []
        current_month = None
        current_count = 0

        for date in dates:
            month_abbr = date.strftime('%b')

            if month_abbr == current_month:
                current_count += 1
            else:
                if current_month is not None:
                    clusters.append((current_month, current_count))
                current_month = month_abbr
                current_count = 1

        if current_month is not None:
            clusters.append((current_month, current_count))

        return [seq[0] for seq in clusters], [seq[1] for seq in clusters]


class DailyTemplate(Chart):
    def __init__(self, date_format, start_date, width, major_grid_on, minor_grid_on, floor_grid_on, y_label, a, b, c, ymin, ymax, style_color='#5a93cc', custom_grid_color='#71B8FF'):
        super().__init__(date_format, start_date, width, major_grid_on, minor_grid_on, floor_grid_on, y_label, style_color, custom_grid_color)
        self.a = a
        self.b = b
        self.c = c
        self.angle = 34
        self.xmin = 0
        self.xmax = 140
        self.ymin = ymin
        self.ymax = ymax
        self.x = np.arange(self.xmin, self.xmax)
        self.y = self.a * pow(self.b, self.x / self.c)
        self.space_top = 0.86
        self.space_left = 0.1
        self.space_right = 0.9
        self.space_bottom = 0.21
        self.relative_width = self.space_right - self.space_left
        self.relative_height = self.space_top - self.space_bottom
        self.image_ratio = self.relative_width / self.relative_height
        self.height = self.image_ratio * self.width * np.tan(self.angle / 180 * np.pi) * np.log10(self.ymax / self.ymin) / (self.xmax - self.xmin) * self.c / np.log10(self.b)

        self.vert_pos_scaling_dict = {5: 1.10,
                                      6: 1.091,
                                      7: 1.087,
                                      8: 1.081,
                                      9: 1.08,
                                      10: 1.08,
                                      11: 1.075,
                                      12: 1.075}

        self.credit_vert_pos = -0.22
        self.vert_pos = self.vert_pos_scaling_dict[width]
        self.underline = self.vert_pos - 0.0067
        self.top_x_label_pad = width * 3.77

        self.top_x_ticks = np.arange(0, 141, 28)
        self.bottom_x_ticks = np.arange(0, 141, 1)

    def _setup_axes(self):
        self.fig, self.ax = plt.subplots(figsize=(self.width, self.height))
        self.ax.yaxis.set_label_coords(-0.09, 0.5)
        plt.subplots_adjust(left=self.space_left, right=self.space_right, bottom=self.space_bottom, top=self.space_top)

        self.first_sunday = self.start_date - pd.Timedelta(self.start_date.dayofweek + 1, unit="D")
        self.dates = pd.date_range(self.first_sunday, periods=21, freq="W").strftime("%d-%b-%y")
        self.month_dates = [self.dates[i] for i in range(0, len(self.dates), 4)]
        self.dates = [str(i) for i in range(0, len(self.dates), 4)]
        self.all_dates = pd.date_range(self.first_sunday, periods=141, freq="D", normalize=True)

        self.date_to_pos = {self.all_dates[i]: i for i in range(len(self.all_dates))}

        self.ax2 = plt.twiny()
        self.ax2.set_xticks(self.top_x_ticks)
        self.ax2.set_xticklabels(self.dates, fontsize=self.general_fontsize, fontname=self.font, color=self.style_color)
        self.ax2.tick_params(axis='both', which='both', color=self.style_color)
        self.ax2.set_xlabel("SUCCESSIVE                       CALENDAR                        WEEKS", fontname=self.font, fontsize=self.general_fontsize, color=self.style_color, weight="bold", labelpad=self.top_x_label_pad)

        self.trans = transforms.blended_transform_factory(self.ax.transData, self.ax.transAxes)
        for tick, date in zip(self.top_x_ticks, self.month_dates):
            self.ax.text(tick, self.vert_pos, date, transform=self.trans, fontname=self.font, fontsize=self.general_fontsize, color=self.style_color, ha="center")
            self.ax.text(tick, self.underline, len(date) * "_", transform=self.trans, fontname=self.font, fontsize=self.general_fontsize, color=self.style_color, ha="center")

        self.ax.spines["bottom"].set_position(("axes", -0.03))
        self.ax2.spines["bottom"].set_visible(False)

        self.ax.set_yscale("log")
        self.ax.set_ylim(self.ymin, self.ymax)
        self.ax.tick_params(axis='both', which='minor', length=0)
        self.ax.set_xlim(self.xmin, self.xmax)
        self.ax.set_xticks(self.bottom_x_ticks)
        bottom_x_tick_labels = [str(tick) if tick % 14 == 0 else '' for tick in self.bottom_x_ticks]
        self.ax.set_xticklabels(bottom_x_tick_labels, fontsize=self.general_fontsize, fontname=self.font, color=self.style_color)
        self.ax.set_yticks(self.left_y_ticks)
        self.ax.set_yticklabels(self.left_y_labels, fontsize=self.general_fontsize, fontname=self.font, color=self.style_color)
        self.ax.tick_params(axis="both", colors=self.style_color)

        if self.major_grid_on:
            for sun in [i for i in range(7, 140, 7)]:
                g1 = self.ax.axvline(sun, color=self.custom_grid_color, linewidth=self.major_grid_width, visible=True)
                self.major_grid_line_objects.append(g1)
            for power in [0.001, 0.01, 0.1, 1, 10, 100, 1000, 10000, 100000, 1000000]:
                g2 = self.ax.axhline(power, color=self.custom_grid_color, linewidth=self.major_grid_width, visible=True)
                self.major_grid_line_objects.append(g2)
            for power in [0.005, 0.05, 0.5, 5, 50, 500, 5000, 50000, 500000]:
                g3 = self.ax.axhline(power, color=self.custom_grid_color, linewidth=self.major_grid_width * 0.5, visible=True)
                self.major_grid_line_objects.append(g3)

        if self.minor_grid_on:
            self.ax.grid(which="both", visible=self.minor_grid_on, color=self.custom_grid_color, linewidth=self.minor_grid_width)

        for position in self.ax.spines.keys():
            self.ax.spines[position].set_color(self.custom_grid_color)
            self.ax2.spines[position].set_color(self.custom_grid_color)
            self.ax.spines[position].set_linewidth(self.major_grid_width)

        self.ax.set_ylabel(self.y_label, fontname=self.font, fontsize=self.general_fontsize, color=self.style_color, weight="bold")
        self.ax.set_xlabel("SUCCESSIVE CALENDAR DAYS", fontname=self.font, fontsize=self.general_fontsize, color=self.style_color, weight="bold")

        for label in self.ax.get_yticklabels():
            if '5' in label.get_text():
                label.set_fontsize(self.general_fontsize * 0.8)
            else:
                label.set_fontsize(self.general_fontsize)

        self.ax.tick_params(axis='both', color=self.custom_grid_color)
        for tick in self.ax.yaxis.get_major_ticks():
            ytick = tick.label1.get_text()
            if '5' in ytick:
                tick.tick1line.set_markeredgewidth(self.major_grid_width * 0.5)
            else:
                tick.tick1line.set_markeredgewidth(self.major_grid_width)

        self.ax2.tick_params(axis='x', which='major', width=self.major_grid_width, length=self.x_tick_length, color=self.custom_grid_color)
        for tick in self.ax2.xaxis.get_major_ticks():
            tick.tick1line.set_markeredgewidth(self.major_grid_width)
            tick.tick2line.set_markeredgewidth(self.major_grid_width)

        self.ax.xaxis.set_tick_params(which='both', direction='inout', color=self.custom_grid_color)
        for tick in self.ax.xaxis.get_major_ticks():
            xtick = tick.label1.get_text()
            if xtick and xtick.isdigit() and int(xtick) % 14 == 0:
                tick.tick1line.set_markeredgewidth(self.major_grid_width)
                tick.tick1line.set_markersize(self.x_tick_length)
            else:
                tick.tick1line.set_markersize(0)


class Daily(DailyTemplate):
    def __init__(self, date_format=None, start_date=None, width=9, major_grid_on=True, minor_grid_on=True, floor_grid_on=False, y_label="COUNT PER DAY", style_color='#5a93cc', custom_grid_color='#71B8FF'):
        self.left_y_ticks = [10 ** e for e in [np.log10(i) for i in [1, 5, 10, 50, 100, 500, 1000, 5000, 10000, 50000, 100000, 500000, 1000000]]]
        self.left_y_labels = [f"{tick:,}" for tick in [1, 5, 10, 50, 100, 500, 1000, 5000, 10000, 50000, 100000, 500000, 1000000]]
        super().__init__(date_format, start_date, width, major_grid_on, minor_grid_on, floor_grid_on, y_label,
                         a=1,
                         b=2,
                         c=7,
                         ymin=1 * 0.69,
                         ymax=1000000,
                         style_color=style_color,
                         custom_grid_color=custom_grid_color)
        self._setup_axes()


class DailyMinute(DailyTemplate):
    def __init__(self, date_format=None, start_date=None, width=9, major_grid_on=True, minor_grid_on=True, floor_grid_on=False, y_label="COUNT PER MINUTE", style_color='#5a93cc', custom_grid_color='#71B8FF'):
        self.left_y_ticks = [10 ** e for e in [np.log10(i) for i in [0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1, 5, 10, 50, 100, 500, 1000]]]
        self.left_y_labels = ["0.001", "0.005", "0.01", "0.05", "0.1", "0.5", "1", "5", "10", "50", "100", "500", "1000"]
        self.right_y_ticks = [1 / m for m in [10 / 60, 15 / 60, 20 / 60, 30 / 60, 1, 2, 5, 10, 20, 60, 60 * 2, 60 * 4, 60 * 8, 60 * 16]]
        self.right_y_labels = ['10" sec', '15"', '20"', '30"', "1' min", "2'", "5'", "10'", "20'", "1 - h", "2 - h", "4 - h", "8 - h", "16 - h"]
        super().__init__(date_format, start_date, width, major_grid_on, minor_grid_on, floor_grid_on, y_label,
                         a=0.001,
                         b=2,
                         c=7,
                         ymin=0.001 * 0.69,
                         ymax=1000,
                         style_color=style_color,
                         custom_grid_color=custom_grid_color)

        self._setup_axes()
        self.setup_right_y_axis()

    def setup_right_y_axis(self):
        self.ax3 = plt.twinx()
        self.ax3.set_ylim(self.ymin, self.ymax)
        self.ax3.set_yscale("log")
        self.ax3.set_yticks(self.right_y_ticks)
        self.ax3.set_yticklabels(self.right_y_labels, fontsize=self.right_y_axis_fontsize, fontname=self.font, color=self.style_color)
        self.ax3.tick_params(axis='both', which='minor', length=0)
        self.ax3.tick_params(axis="both", colors=self.style_color)
        self.ax3.spines["top"].set_color(self.custom_grid_color)
        self.ax3.spines["left"].set_color(self.custom_grid_color)
        self.ax3.spines["right"].set_color(self.custom_grid_color)
        self.ax3.spines["bottom"].set_visible(False)

        self.ax3.tick_params(color=self.custom_grid_color)
        for tick in self.ax3.yaxis.get_major_ticks():
            tick_value = tick.label1.get_text()
            tick.label1.set_color('red')
            if tick_value in ["1' min", "10'"]:
                tick.tick1line.set_markeredgewidth(self.major_grid_width)
                tick.tick2line.set_markeredgewidth(self.major_grid_width)
            elif tick_value in ["20'"]:
                tick.tick1line.set_markeredgewidth(self.major_grid_width * 0.5)
                tick.tick2line.set_markeredgewidth(self.major_grid_width * 0.5)


class WeeklyTemplate(Chart):
    def __init__(self, date_format, start_date, width, major_grid_on, minor_grid_on, floor_grid_on, y_label, a, b, c, ymin, ymax, style_color='#5a93cc', custom_grid_color='#71B8FF'):
        super().__init__(date_format, start_date, width, major_grid_on, minor_grid_on, floor_grid_on, y_label, style_color, custom_grid_color)
        self.a = a
        self.b = b
        self.c = c
        self.angle = 34
        self.xmin = 0
        self.xmax = 100
        self.ymin = ymin
        self.ymax = ymax
        self.x = np.arange(self.xmin, self.xmax)
        self.y = self.a * pow(self.b, self.x / self.c)
        self.space_top = 0.86
        self.space_left = 0.12
        self.space_right = 0.9
        self.space_bottom = 0.25
        self.relative_width = self.space_right - self.space_left
        self.relative_height = self.space_top - self.space_bottom
        self.image_ratio = self.relative_width / self.relative_height
        self.height = self.image_ratio * self.width * np.tan(self.angle / 180 * np.pi) * np.log10(self.ymax / self.ymin) / (self.xmax - self.xmin) * self.c / np.log10(self.b)

        # Positioning
        self.credit_vert_pos = - 0.28

        # Scaling
        self.month_label_size = width
        self.top_x_tick_length = 2.222 * width

    def _setup_axes(self):
        self.fig, self.ax = plt.subplots(figsize=(self.width, self.height))
        self.ax.yaxis.set_label_coords(-0.11, 0.5)
        plt.subplots_adjust(left=self.space_left, right=self.space_right, bottom=self.space_bottom, top=self.space_top)

        self.weekday_of_previous_month = (self.start_date.replace(day=1) - pd.Timedelta(days=1)).replace(day=1)
        self.all_dates = pd.date_range(self.weekday_of_previous_month, periods=self.xmax, freq="W", normalize=True)

        self.month_name_labels, self.month_tick_nums = self.count_month_clusters(self.all_dates)
        self.month_tick_nums = [0] + self.month_tick_nums
        self.date_to_pos = {self.all_dates[i]: i for i in range(len(self.all_dates))}

        self.top_x_ticks = np.cumsum(self.month_tick_nums)
        self.top_x_ticks = self.top_x_ticks[self.top_x_ticks != 99]  # Hacky thing I need to fix
        self.month_count_labels = [str(i) if i % 4 == 0 and i < 24 else "" for i in range(0, len(self.top_x_ticks))]

        self.ax2 = plt.twiny()
        self.ax2.set_xticks(self.top_x_ticks)
        self.ax2.set_xticklabels(self.month_count_labels, fontsize=self.general_fontsize, fontname=self.font, color=self.style_color, weight='bold')
        self.ax2.tick_params(axis='both', which='both', color=self.custom_grid_color, length=self.top_x_tick_length, width=self.major_grid_width)

        self.ax2.set_xlabel("SUCCESSIVE                       CALENDAR                        MONTHS",
                            fontname=self.font, fontsize=self.general_fontsize, color=self.style_color, weight="bold", labelpad=self.top_x_label_pad)

        self.trans = transforms.blended_transform_factory(self.ax.transData, self.ax.transAxes)
        for tick, date, month_width in zip(self.top_x_ticks, self.month_name_labels, self.month_tick_nums[1:]):
            if month_width > 3:
                horizontal_off_set = month_width / 2
                self.ax.text(tick + horizontal_off_set, self.vert_pos, date, transform=self.trans, fontname=self.font, fontsize=self.month_label_size, color=self.style_color, ha="center")

        self.ax.spines["bottom"].set_position(("axes", -0.03))
        self.ax2.spines["bottom"].set_visible(False)

        self.ax.set_yscale("log")
        self.ax.set_ylim(self.ymin, self.ymax)
        self.ax.set_xlim(self.xmin, self.xmax)

        self.ax.set_xticks(self.bottom_x_ticks)
        self.bottom_x_tick_labels = self.top_x_ticks[::2]
        self.bottom_x_tick_labels = np.append(self.bottom_x_tick_labels, 100)
        self.ax.set_xticklabels([str(tick) if tick in self.bottom_x_tick_labels else '' for tick in self.bottom_x_ticks], fontsize=self.general_fontsize, fontname=self.font, color=self.style_color)
        self.ax.set_yticks(self.left_y_ticks)
        self.ax.set_yticklabels(self.left_y_labels, fontsize=self.general_fontsize, fontname=self.font, color=self.style_color)

        self.ax.tick_params(axis='y', which='both', length=5, color=self.custom_grid_color, width=self.minor_grid_width)
        self.ax.tick_params(axis="y", width=self.major_grid_width)
        self.ax.tick_params(axis='x', which='both', length=5, color=self.custom_grid_color, width=self.minor_grid_width)

        if self.major_grid_on:
            for month in self.top_x_ticks:
                g1 = self.ax.axvline(month, color=self.custom_grid_color, linewidth=self.major_grid_width, visible=True)
                self.major_grid_line_objects.append(g1)
            for power in [0.001, 0.01, 0.1, 1, 10, 100, 1000, 10000, 100000, 1000000]:
                g2 = self.ax.axhline(power, color=self.custom_grid_color, linewidth=self.major_grid_width, visible=True)
                self.major_grid_line_objects.append(g2)
            for power in [0.005, 0.05, 0.5, 5, 50, 500, 5000, 50000, 500000]:
                g3 = self.ax.axhline(power, color=self.custom_grid_color, linewidth=self.major_grid_width * 0.5, visible=True)
                self.major_grid_line_objects.append(g3)

        if self.minor_grid_on:
            self.ax.grid(which="both", visible=self.minor_grid_on, color=self.custom_grid_color, linewidth=self.minor_grid_width)

        for position in self.ax.spines.keys():
            self.ax.spines[position].set_color(self.custom_grid_color)
            self.ax.spines[position].set_linewidth(self.major_grid_width)
            self.ax2.spines[position].set_color(self.custom_grid_color)

        self.ax.set_ylabel(self.y_label, fontname=self.font, fontsize=self.general_fontsize, color=self.style_color, weight="bold")
        self.ax.set_xlabel("SUCCESSIVE CALENDAR WEEKS", fontname=self.font, fontsize=self.general_fontsize, color=self.style_color, weight="bold")

        for label in self.ax.get_yticklabels():
            if '5' in label.get_text():
                label.set_fontsize(self.general_fontsize * 0.8)
            else:
                label.set_fontsize(self.general_fontsize)

        for tick in self.ax.yaxis.get_major_ticks():
            ytick = tick.label1.get_text()
            if '5' in ytick:
                tick.tick1line.set_markeredgewidth(self.major_grid_width * 0.5)

        self.ax.xaxis.set_tick_params(which='both', direction='inout')
        for tick in self.ax.xaxis.get_major_ticks():
            xtick = tick.label1.get_text()
            if xtick and xtick.isdigit() and int(xtick) in self.bottom_x_tick_labels:
                tick.tick1line.set_markeredgewidth(self.major_grid_width)
                tick.tick1line.set_markersize(self.x_tick_length)
            else:
                tick.tick1line.set_markersize(0)


class Weekly(WeeklyTemplate):
    def __init__(self, date_format=None, start_date=None, width=9, major_grid_on=True, minor_grid_on=True, floor_grid_on=False, y_label="COUNT PER WEEK", style_color='#5a93cc', custom_grid_color='#71B8FF'):
        self.vert_pos = 1.03
        self.bottom_x_ticks = np.arange(0, 101, 1)
        self.left_y_ticks = [10 ** e for e in [np.log10(i) for i in [1, 5, 10, 50, 100, 500, 1000, 5000, 10000, 50000, 100000, 500000, 1000000]]]
        self.left_y_labels = [f"{tick:,}" for tick in [1, 5, 10, 50, 100, 500, 1000, 5000, 10000, 50000, 100000, 500000, 1000000]]
        super().__init__(
            date_format=date_format,
            start_date=start_date,
            width=width,
            major_grid_on=major_grid_on,
            minor_grid_on=minor_grid_on,
            floor_grid_on=floor_grid_on,
            y_label=y_label,
            a=1,
            b=2,
            c=4,
            ymin=1 * 0.69,
            ymax=1000000,
            style_color=style_color,
            custom_grid_color=custom_grid_color
        )
        self._setup_axes()


class WeeklyMinute(WeeklyTemplate):
    def __init__(self, date_format=None, start_date=None, width=9, major_grid_on=True, minor_grid_on=True, floor_grid_on=False, y_label="COUNT PER MINUTE", style_color='#5a93cc', custom_grid_color='#71B8FF'):
        self.vert_pos = 1.03
        self.bottom_x_ticks = np.arange(0, 101, 1)
        self.right_y_ticks = [1 / m for m in [10 / 60, 15 / 60, 20 / 60, 30 / 60, 1, 2, 5, 10, 20, 60, 60 * 2, 60 * 4, 60 * 8, 60 * 16]]
        self.right_y_labels = ['10" sec', '15"', '20"', '30"', "1' min", "2'", "5'", "10'", "20'", "1 - h", "2 - h", "4 - h", "8 - h", "16 - h"]
        self.left_y_ticks = [10 ** e for e in [np.log10(i) for i in [0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1, 5, 10, 50, 100, 500, 1000]]]
        self.left_y_labels = ["0.001", "0.005", "0.01", "0.05", "0.1", "0.5", "1", "5", "10", "50", "100", "500", "1000"]
        super().__init__(
            date_format=date_format,
            start_date=start_date,
            width=width,
            major_grid_on=major_grid_on,
            minor_grid_on=minor_grid_on,
            floor_grid_on=floor_grid_on,
            y_label=y_label,
            a=0.001,
            b=2,
            c=4,
            ymin=0.001 * 0.69,
            ymax=1000,
            style_color=style_color,
            custom_grid_color=custom_grid_color
        )
        self._setup_axes()
        self.setup_right_y_axis()

    def setup_right_y_axis(self):
        self.ax3 = plt.twinx()
        self.ax3.set_ylim(self.ymin, self.ymax)
        self.ax3.set_yscale("log")
        self.ax3.set_yticks(self.right_y_ticks)
        self.ax3.set_yticklabels(self.right_y_labels, fontsize=self.right_y_axis_fontsize, fontname=self.font, color=self.style_color)
        self.ax3.tick_params(axis='both', which='minor', length=0)
        self.ax3.tick_params(axis="both", colors=self.style_color)
        self.ax3.spines["top"].set_color(self.custom_grid_color)
        self.ax3.spines["left"].set_color(self.custom_grid_color)
        self.ax3.spines["right"].set_color(self.custom_grid_color)
        self.ax3.spines["bottom"].set_visible(False)

        self.ax3.tick_params(color=self.custom_grid_color)
        for tick in self.ax3.yaxis.get_major_ticks():
            tick_value = tick.label1.get_text()
            tick.label1.set_color('red')
            if tick_value in ["1' min", "10'"]:
                tick.tick1line.set_markeredgewidth(self.major_grid_width)
                tick.tick2line.set_markeredgewidth(self.major_grid_width)
            elif tick_value in ["20'"]:
                tick.tick1line.set_markeredgewidth(self.major_grid_width * 0.5)
                tick.tick2line.set_markeredgewidth(self.major_grid_width * 0.5)


class MonthlyTemplate(Chart):
    def __init__(self, date_format, start_date, width, major_grid_on, minor_grid_on, floor_grid_on, y_label, a, b, c, ymin, ymax, style_color='#5a93cc', custom_grid_color='#71B8FF'):
        super().__init__(date_format, start_date, width, major_grid_on, minor_grid_on, floor_grid_on, y_label, style_color, custom_grid_color)
        self.a = a
        self.b = b
        self.c = c
        self.angle = 34
        self.xmin = 0
        self.xmax = 120
        self.ymin = ymin
        self.ymax = ymax
        self.x = np.arange(self.xmin, self.xmax)
        self.y = self.a * pow(self.b, self.x / self.c)
        self.space_top = 0.86
        self.space_left = 0.12
        self.space_right = 0.9
        self.space_bottom = 0.25
        self.relative_width = self.space_right - self.space_left
        self.relative_height = self.space_top - self.space_bottom
        self.image_ratio = self.relative_width / self.relative_height
        self.height = self.image_ratio * self.width * np.tan(self.angle / 180 * np.pi) * np.log10(self.ymax / self.ymin) / (self.xmax - self.xmin) * self.c / np.log10(self.b)

        # Positioning
        self.credit_vert_pos = - 0.28
        self.year_vert_pos = 1.025

        # Scaling
        self.year_font_size = 1.333 * width
        self.top_x_tick_length = 2.222 * width

    def _setup_axes(self):
        self.fig, self.ax = plt.subplots(figsize=(self.width, self.height))
        plt.subplots_adjust(left=self.space_left, right=self.space_right, bottom=self.space_bottom, top=self.space_top)

        # Bottom x-axis ticks
        self.bottom_x_ticks = np.arange(0, 121, 1)
        self.bottom_x_tick_labels = self.bottom_x_ticks[::12]

        # Top x-axis ticks
        self.top_x_ticks = np.arange(0, 121, 12)
        self.top_x_tick_labels = [str(i) for i in range(len(self.top_x_ticks))]

        # Set up primary axis
        self.ax.yaxis.set_label_coords(-0.11, 0.5)
        self.ax.spines["bottom"].set_position(("axes", -0.03))
        self.ax.set_yscale("log")
        self.ax.set_ylim(self.ymin, self.ymax)
        self.ax.set_xlim(self.xmin, self.xmax)
        self.ax.set_xticks(self.bottom_x_ticks)
        self.ax.set_xticklabels([str(tick) if tick in self.bottom_x_tick_labels else '' for tick in self.bottom_x_ticks], fontsize=self.general_fontsize, fontname=self.font, color=self.style_color)
        self.ax.set_yticks(self.left_y_ticks)
        self.ax.set_yticklabels(self.left_y_labels, fontsize=self.general_fontsize, fontname=self.font, color=self.style_color)
        self.ax.tick_params(axis='y', which='both', length=5, color=self.custom_grid_color, width=self.minor_grid_width)
        self.ax.tick_params(axis="y", width=self.major_grid_width)
        self.ax.tick_params(axis='x', which='both', length=5, color=self.custom_grid_color, width=self.minor_grid_width)

        # Create date reference
        self.start_date_of_previous_year = self.start_date.replace(year=self.start_date.year - 1, month=1, day=1).normalize()
        self.all_dates = pd.date_range(self.start_date_of_previous_year, periods=self.xmax + 1, freq="ME", normalize=True)
        self.date_to_pos = {self.all_dates[i]: i for i in range(len(self.all_dates))}

        # Top x-axis
        self.ax2 = plt.twiny()
        self.ax2.set_xticks(self.top_x_ticks)
        self.ax2.set_xticklabels(self.top_x_tick_labels, fontsize=self.general_fontsize, fontname=self.font, color=self.style_color, weight='bold')
        self.ax2.tick_params(axis='both', which='both', color=self.custom_grid_color, length=self.top_x_tick_length, width=self.major_grid_width)
        self.ax2.set_xlabel("SUCCESSIVE                       CALENDAR                        YEARS",
                            fontname=self.font, fontsize=self.general_fontsize, color=self.style_color, weight="bold", labelpad=self.top_x_label_pad)
        self.trans = transforms.blended_transform_factory(self.ax.transData, self.ax.transAxes)
        for tick in self.top_x_ticks[:-1]:
            year = self.all_dates[tick].year
            self.ax.text(tick + 6, self.year_vert_pos, str(year), transform=self.trans, fontname=self.font, fontsize=self.year_font_size, color=self.style_color, ha="center")

        # Don't show spines for top x-axis
        for spine in self.ax2.spines.values():
            spine.set_visible(False)

        if self.major_grid_on:
            for month in self.top_x_ticks:
                g1 = self.ax.axvline(month, color=self.custom_grid_color, linewidth=self.major_grid_width, visible=True)
                self.major_grid_line_objects.append(g1)
            for power in [0.001, 0.01, 0.1, 1, 10, 100, 1000, 10000, 100000, 1000000]:
                g2 = self.ax.axhline(power, color=self.custom_grid_color, linewidth=self.major_grid_width, visible=True)
                self.major_grid_line_objects.append(g2)
            for power in [0.005, 0.05, 0.5, 5, 50, 500, 5000, 50000, 500000]:
                g3 = self.ax.axhline(power, color=self.custom_grid_color, linewidth=self.major_grid_width * 0.5, visible=True)
                self.major_grid_line_objects.append(g3)

        if self.minor_grid_on:
            self.ax.grid(which="both", visible=self.minor_grid_on, color=self.custom_grid_color, linewidth=self.minor_grid_width)

        for position in self.ax.spines.keys():
            self.ax.spines[position].set_color(self.custom_grid_color)
            self.ax.spines[position].set_linewidth(self.major_grid_width)

        self.ax.set_ylabel(self.y_label, fontname=self.font, fontsize=self.general_fontsize, color=self.style_color, weight="bold")
        self.ax.set_xlabel("SUCCESSIVE CALENDAR MONTHS", fontname=self.font, fontsize=self.general_fontsize, color=self.style_color, weight="bold")

        for label in self.ax.get_yticklabels():
            if '5' in label.get_text():
                label.set_fontsize(self.general_fontsize * 0.8)
            else:
                label.set_fontsize(self.general_fontsize)

        for tick in self.ax.yaxis.get_major_ticks():
            ytick = tick.label1.get_text()
            if '5' in ytick:
                tick.tick1line.set_markeredgewidth(self.major_grid_width * 0.5)

        self.ax.xaxis.set_tick_params(which='both', direction='inout')
        for tick in self.ax.xaxis.get_major_ticks():
            xtick = tick.label1.get_text()
            if xtick and xtick.isdigit() and int(xtick) in self.bottom_x_tick_labels:
                tick.tick1line.set_markeredgewidth(self.major_grid_width)
                tick.tick1line.set_markersize(self.x_tick_length)
            else:
                tick.tick1line.set_markersize(0)


class Monthly(MonthlyTemplate):
    def __init__(self, date_format=None, start_date=None, width=9, major_grid_on=True, minor_grid_on=True, floor_grid_on=False, y_label="COUNT PER WEEK", style_color='#5a93cc', custom_grid_color='#71B8FF'):
        super().__init__(
            date_format=date_format,
            start_date=start_date,
            width=width,
            major_grid_on=major_grid_on,
            minor_grid_on=minor_grid_on,
            floor_grid_on=floor_grid_on,
            y_label=y_label,
            a=1,
            b=2,
            c=5,
            ymin=1 * 0.69,
            ymax=1000000,
            style_color=style_color,
            custom_grid_color=custom_grid_color
        )

        self.vert_pos = 1.03
        self.bottom_x_ticks = np.arange(0, 101, 1)
        self.left_y_ticks = [10 ** e for e in [np.log10(i) for i in [1, 5, 10, 50, 100, 500, 1000, 5000, 10000, 50000, 100000, 500000, 1000000]]]
        self.left_y_labels = [f"{tick:,}" for tick in [1, 5, 10, 50, 100, 500, 1000, 5000, 10000, 50000, 100000, 500000, 1000000]]

        self._setup_axes()


class MonthlyMinute(MonthlyTemplate):
    def __init__(self, date_format=None, start_date=None, width=9, major_grid_on=True, minor_grid_on=True, floor_grid_on=False, y_label="COUNT PER MINUTE", style_color='#5a93cc', custom_grid_color='#71B8FF'):
        super().__init__(
            date_format=date_format,
            start_date=start_date,
            width=width,
            major_grid_on=major_grid_on,
            minor_grid_on=minor_grid_on,
            floor_grid_on=floor_grid_on,
            y_label=y_label,
            a=0.001,
            b=2,
            c=5,
            ymin=0.001 * 0.69,
            ymax=1000,
            style_color=style_color,
            custom_grid_color=custom_grid_color
        )

        self.vert_pos = 1.03
        self.bottom_x_ticks = np.arange(0, 101, 1)
        self.right_y_ticks = [1 / m for m in [10 / 60, 15 / 60, 20 / 60, 30 / 60, 1, 2, 5, 10, 20, 60, 60 * 2, 60 * 4, 60 * 8, 60 * 16]]
        self.right_y_labels = ['10" sec', '15"', '20"', '30"', "1' min", "2'", "5'", "10'", "20'", "1 - h", "2 - h", "4 - h", "8 - h", "16 - h"]
        self.left_y_ticks = [10 ** e for e in [np.log10(i) for i in [0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1, 5, 10, 50, 100, 500, 1000]]]
        self.left_y_labels = ["0.001", "0.005", "0.01", "0.05", "0.1", "0.5", "1", "5", "10", "50", "100", "500", "1000"]

        self._setup_axes()
        self.setup_right_y_axis()

    def setup_right_y_axis(self):
        self.ax3 = plt.twinx()
        self.ax3.set_ylim(self.ymin, self.ymax)
        self.ax3.set_yscale("log")
        self.ax3.set_yticks(self.right_y_ticks)
        self.ax3.set_yticklabels(self.right_y_labels, fontsize=self.right_y_axis_fontsize, fontname=self.font, color=self.style_color)
        self.ax3.tick_params(axis='both', which='minor', length=0)
        self.ax3.tick_params(axis="both", colors=self.style_color)
        self.ax3.spines["top"].set_color(self.custom_grid_color)
        self.ax3.spines["left"].set_color(self.custom_grid_color)
        self.ax3.spines["right"].set_color(self.custom_grid_color)
        self.ax3.spines["bottom"].set_visible(False)

        self.ax3.tick_params(color=self.custom_grid_color)
        for tick in self.ax3.yaxis.get_major_ticks():
            tick_value = tick.label1.get_text()
            tick.label1.set_color('red')
            if tick_value in ["1' min", "10'"]:
                tick.tick1line.set_markeredgewidth(self.major_grid_width)
                tick.tick2line.set_markeredgewidth(self.major_grid_width)
            elif tick_value in ["20'"]:
                tick.tick1line.set_markeredgewidth(self.major_grid_width * 0.5)
                tick.tick2line.set_markeredgewidth(self.major_grid_width * 0.5)


if __name__ == '__main__':
    chart = MonthlyMinute()
    plt.show()