#   lap_analysis - Use the lap details page of stracker to generate a time-difference chart
#   Copyright (C) 2023  RangerUFO
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <https://www.gnu.org/licenses/>.


import argparse
import requests
import numpy as np
import matplotlib.pyplot as plt
from scipy import interpolate
from enum import Enum
from html.parser import HTMLParser


class Axis:
    def __init__(self):
        self.__x = []
        self.__y = []

    def append_x(self, x):
        self.__x.append(x)

    def append_y(self, y):
        self.__y.append(y)

    def __call__(self):
        w, b = np.polyfit(self.__x, self.__y, 1)
        return lambda x: w * x + b


class LapDataParser(HTMLParser):
    Status = Enum("Status", ["INIT", "PLOT", "AXIS_X", "GUIDE_X", "TEXT_X", "AXIS_Y", "GUIDE_Y", "TEXT_Y", "LINE", "DONE"])

    def __init__(self, **kwargs):
        super(LapDataParser, self).__init__(**kwargs)
        self.__status = LapDataParser.Status.INIT
        self.__axis_x = Axis()
        self.__axis_y = Axis()
        self.__index = None
        self.__data = [None, None]

    @property
    def data(self):
        axis_x = self.__axis_x()
        axis_y = self.__axis_y()
        return [line for line in self.__data_impl(axis_x, axis_y)]

    def handle_starttag(self, tag, attrs):
        if self.__status == LapDataParser.Status.INIT:
            if tag == "g":
                for k, v in attrs:
                    if k == "class" and v == "plot":
                        self.__status = LapDataParser.Status.PLOT
                        break
        elif self.__status == LapDataParser.Status.PLOT:
            if tag == "g":
                for k, v in attrs:
                    if k == "class":
                        if v == "axis x":
                            self.__status = LapDataParser.Status.AXIS_X
                        elif v == "axis y":
                            self.__status = LapDataParser.Status.AXIS_Y
                        elif v == "series serie-0 color-0":
                            self.__status = LapDataParser.Status.LINE
                            self.__index = 0
                        elif v == "series serie-1 color-1":
                            self.__status = LapDataParser.Status.LINE
                            self.__index = 1
                        break
        elif self.__status == LapDataParser.Status.AXIS_X:
            if tag == "g":
                self.__status = LapDataParser.Status.GUIDE_X
        elif self.__status == LapDataParser.Status.GUIDE_X:
            if tag == "path":
                for k, v in attrs:
                    if k == "d":
                        self.__axis_x.append_x(float(v.split(" ")[0][1:]))
            elif tag == "text":
                self.__status = LapDataParser.Status.TEXT_X
        elif self.__status == LapDataParser.Status.AXIS_Y:
            if tag == "g":
                self.__status = LapDataParser.Status.GUIDE_Y
        elif self.__status == LapDataParser.Status.GUIDE_Y:
            if tag == "path":
                for k, v in attrs:
                    if k == "d":
                        self.__axis_y.append_x(float(v.split(" ")[1]))
            elif tag == "text":
                self.__status = LapDataParser.Status.TEXT_Y
        elif self.__status == LapDataParser.Status.LINE:
            if tag == "path":
                for k, v in attrs:
                    if k == "d":
                        self.__data[self.__index] = [float(x) if x[0].isdigit() else float(x[1:]) for x in v.split(" ")]

    def handle_endtag(self, tag):
        if self.__status == LapDataParser.Status.PLOT:
            if tag == "g":
                self.__status = LapDataParser.Status.DONE
        elif self.__status == LapDataParser.Status.AXIS_X:
            if tag == "g":
                self.__status = LapDataParser.Status.PLOT
        elif self.__status == LapDataParser.Status.GUIDE_X:
            if tag == "g":
                self.__status = LapDataParser.Status.AXIS_X
        elif self.__status == LapDataParser.Status.TEXT_X:
            if tag == "text":
                self.__status = LapDataParser.Status.GUIDE_X
        elif self.__status == LapDataParser.Status.AXIS_Y:
            if tag == "g":
                self.__status = LapDataParser.Status.PLOT
        elif self.__status == LapDataParser.Status.GUIDE_Y:
            if tag == "g":
                self.__status = LapDataParser.Status.AXIS_Y
        elif self.__status == LapDataParser.Status.TEXT_Y:
            if tag == "text":
                self.__status = LapDataParser.Status.GUIDE_Y
        elif self.__status == LapDataParser.Status.LINE:
            if tag == "g":
                self.__status = LapDataParser.Status.PLOT

    def handle_data(self, data):
        if self.__status == LapDataParser.Status.TEXT_X:
            self.__axis_x.append_y(float(data))
        elif self.__status == LapDataParser.Status.TEXT_Y:
            self.__axis_y.append_y(float(data))


    def __data_impl(self, axis_x, axis_y):
        for line in self.__data:
            yield [(axis_x(line[i]), axis_y(line[i + 1])) for i in range(0, len(line), 2)]


def process_data(data):
    for line in data:
        x, y = zip(*line)
        f = interpolate.interp1d(np.array(x), np.array(y), kind="slinear")
        x1 = np.linspace(x[0], x[-1], int((x[-1] - x[0]) * 10000))
        yield x1, f(x1)


def lap_time(x, y):
    t = 0
    z = [t]
    for i in range(1, len(x)):
        v = (y[i - 1] + y[i]) * 0.5 * 1000 / 3600
        d = x[i] - x[i - 1]
        t += d / v
        z.append(t)
    return np.array(z)


def align(t):
    if t[0][0][0] < t[1][0][0]:
        i = 1
        while t[0][0][i] < t[1][0][0]:
            i += 1
        return [(t[0][0][i:], t[0][1][i:]), t[1]]
    else:
        i = 0
        while t[1][0][i] < t[0][0][0]:
            i += 1
        return [t[0], (t[1][0][i:], t[1][1][i:])]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Improved lap chart for stracker.")
    parser.add_argument("--url", help="url of lap details page", type=str, required=True)
    parser.add_argument("--length", help="circuit length (km)", type=float, required=True)
    args = parser.parse_args()

    r = requests.get(args.url)
    p = LapDataParser()
    p.feed(r.text)
    data = tuple((x, y) for x, y in process_data(p.data))
    t = [(x, lap_time(x * args.length * 1000, y)) for x, y in align(data)]
    n = min(len(x) for x, _ in t)
    plt.subplot(2, 1, 1)
    for i, (x, y) in enumerate(data):
        plt.plot(x[:n] * args.length, y[:n], label="serie-%d"%i)
    plt.grid(True)
    plt.legend()
    plt.subplot(2, 1, 2)
    plt.plot(t[0][0][:n] * args.length, t[0][1][:n] - t[1][1][:n], label="time diff")
    plt.grid(True)
    plt.legend()
    plt.show()
