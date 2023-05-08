import argparse
import requests
import numpy as np
import matplotlib.pyplot as plt
from scipy import interpolate
from enum import Enum
from html.parser import HTMLParser


class LapDataParser(HTMLParser):
    Status = Enum("Status", ["INIT", "PLOT", "LINE", "DOT", "DATA", "DONE"])

    def __init__(self, **kwargs):
        super(LapDataParser, self).__init__(**kwargs)
        self.__status = LapDataParser.Status.INIT
        self.__index = None
        self.__data = ([], [])

    @property
    def data(self):
        return self.__data

    def handle_starttag(self, tag, attrs):
        if self.__status == LapDataParser.Status.INIT:
            if tag == "g":
                for k, v in attrs:
                    if k == "class" and v == "plot overlay":
                        self.__status = LapDataParser.Status.PLOT
                        break
        elif self.__status == LapDataParser.Status.PLOT:
            if tag == "g":
                self.__status = LapDataParser.Status.LINE
                for k, v in attrs:
                    if k == "class":
                        if v == "series serie-0 color-0":
                            self.__index = 0
                        elif v == "series serie-1 color-1":
                            self.__index = 1
                        break
        elif self.__status == LapDataParser.Status.LINE:
            if tag == "g":
                self.__status = LapDataParser.Status.DOT
        elif self.__status == LapDataParser.Status.DOT:
            if tag == "desc":
                for k, v in attrs:
                    if k == "class" and v == "value":
                        self.__status = LapDataParser.Status.DATA
                        break

    def handle_endtag(self, tag):
        if self.__status == LapDataParser.Status.PLOT:
            if tag == "g":
                self.__status = LapDataParser.Status.DONE
        elif self.__status == LapDataParser.Status.LINE:
            if tag == "g":
                self.__status = LapDataParser.Status.PLOT
        elif self.__status == LapDataParser.Status.DOT:
            if tag == "g":
                self.__status = LapDataParser.Status.LINE
        elif self.__status == LapDataParser.Status.DATA:
            if tag == "desc":
                self.__status = LapDataParser.Status.DOT

    def handle_data(self, data):
        if self.__status == LapDataParser.Status.DATA and not self.__index is None:
            self.__data[self.__index].append(tuple(float(v) for v in data.split(":")))


def process(data):
    for line in data:
        x, y = zip(*([line[0]] + [line[i] for i in range(1, len(line)) if line[i][0] > line[i - 1][0]]))
        for i in range(1, len(x)):
            if x[i - 1] >= x[i]:
                print(i)
        f = interpolate.interp1d(np.array(x), np.array(y),kind="slinear")
        x1 = np.linspace(x[0], x[-1], int((x[-1] - x[0]) * 1000))
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Improved lap chart for stracker.")
    parser.add_argument("--url", help="url of lap details page", type=str, required=True)
    parser.add_argument("--length", help="circuit length (km)", type=float, required=True)
    args = parser.parse_args()

    r = requests.get(args.url)
    p = LapDataParser()
    p.feed(r.text)
    data = tuple((x, y) for x, y in process(p.data))
    plt.subplot(2, 1, 1)
    for i, (x, y) in enumerate(data):
        plt.plot(x * args.length, y, label="serie-%d"%i)
    plt.grid(True)
    plt.legend()
    plt.subplot(2, 1, 2)
    t = [(x, lap_time(x * args.length * 1000, y)) for x, y in data]
    n = min(len(x) for x, _ in t)
    plt.plot(t[0][0][:n] * args.length, t[0][1][:n] - t[1][1][:n], label="time diff")
    plt.grid(True)
    plt.legend()
    plt.show()
