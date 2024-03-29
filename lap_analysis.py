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


import re
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
            yield [] if line is None else [(axis_x(line[i]), axis_y(line[i + 1])) for i in range(0, len(line), 2)]


def process_data(data, epsilon):
    for line in data:
        x, y = zip(*line)
        f = interpolate.interp1d(np.array(x), np.array(y), kind="slinear")
        x1 = np.linspace(x[0], x[-1], int((x[-1] - x[0]) / epsilon))
        yield x1, f(x1)


def align_data(t, epsilon):
    if abs(t[0][0][0] - t[1][0][0]) < epsilon:
        return t
    i = 1
    if t[0][0][0] < t[1][0][0]:
        while t[0][0][i] < t[1][0][0]:
            i += 1
        return [(t[0][0][i:], t[0][1][i:]), t[1]]
    else:
        while t[1][0][i] < t[0][0][0]:
            i += 1
        return [t[0], (t[1][0][i:], t[1][1][i:])]


def lap_time(x, y):
    t = 0
    z = [t]
    for i in range(1, len(x)):
        v = (y[i - 1] + y[i]) * 0.5 * 1000 / 3600
        d = x[i] - x[i - 1]
        t += d / v
        z.append(t)
    return np.array(z)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Time-diff chart for stracker.")
    parser.add_argument("--url", help="url of lap details page", type=str, required=True)
    parser.add_argument("--length", help="circuit length (km)", type=float, required=True)
    parser.add_argument("--lapid", help="lapid of manual selection", type=str)
    parser.add_argument("--xurl", help="url of lap details page (cross server)", type=str)
    parser.add_argument("--epsilon", help="data alignment accuracy (default: 1e-4)", type=float, default=1e-4)
    args = parser.parse_args()

    cookies = None
    if not args.lapid is None:
        m = re.match("^\\s*(https?://\\S+)/", args.url)
        if not m is None:
            r = requests.get(m[1] + "/lapdetails_store_lapid", {
                "lapid": args.lapid
            })
            cookies = r.cookies
    r = requests.get(args.url, cookies=cookies)
    p = LapDataParser()
    p.feed(r.text)
    raw_data = p.data
    if not args.xurl is None:
        r = requests.get(args.xurl)
        p = LapDataParser()
        p.feed(r.text)
        raw_data[1] = p.data[0]
    data = tuple((x, y) for x, y in process_data(raw_data, args.epsilon))
    t = [(x, lap_time(x * args.length * 1000, y)) for x, y in align_data(data, args.epsilon)]
    n = min(len(x) for x, _ in t)
    fig = plt.figure()
    ax0 = fig.add_subplot(111)
    ax0.set_xlabel("Track Position (km)")
    ax0.set_ylabel("Velocity (km/h)")
    for i, (x, y) in enumerate(data):
        ax0.plot(x[:n] * args.length, y[:n], ":", label="serie-%d"%i)
    ax0.legend()
    ax1 = ax0.twinx()
    ax1.set_ylabel("Time Diff (s)")
    ax1.plot(t[0][0][:n] * args.length, t[0][1][:n] - t[1][1][:n], "g", label="time diff")
    ax1.grid(True)
    plt.show()
