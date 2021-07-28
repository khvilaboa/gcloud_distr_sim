
from lxml import etree
import matplotlib
import matplotlib.pyplot as plt
import os
import sys

font = {'family': 'DejaVu Sans',
        'weight': 'normal',
        'size': 18}

matplotlib.rc('font', **font)

TIME_PERC = 0.9
IMG_DIR = "imgs"

def get_args(elem):
    args = []
    for child in elem:
        if child.tag == "constructor-arg":
            args.append(child.attrib["value"])
    return args


def gen_accum_perc_plot(delays, total, out_dir=None):
    fig, ax = plt.subplots(figsize=(12, 7))
    accum = []
    cont = 0

    for delay in delays:
        cont += delay[1]
        accum.append(cont)

    accum_perc = [100*d/total for d in accum]
    ax.plot(range(1, len(delays)+1), accum_perc)
    ax.set_xlabel("Num. atomics")
    ax.set_ylabel("Accumulated porcentual time (%)")

    if out_dir:
        fig.savefig(out_dir)
    else:
        fig.show()


def gen_ind_delays_plot(delays, out_dir=None):
    fig, ax = plt.subplots(figsize=(12, 7))
    delays = [p[1] for p in delays]

    ax.bar(range(1, len(delays)+1), delays)
    ax.set_xlabel("Atomics")
    ax.set_ylabel("Delay (s)")
    plt.show()

    if out_dir:
        fig.savefig(out_dir)
    else:
        fig.show()


fn = sys.argv[1]
assert fn.endswith(".xml")

coupled = etree.parse(open(fn, "r")).getroot()
delays = []
total_delay = 0

for child in coupled:
    if child.tag == "atomic" and child.attrib["name"] != "generator":
        args = get_args(child)[1:]
        assert len(args) == 2
        curr_delay = sum(map(float, args)) * int(child.attrib["name"][1:child.attrib["name"].index("_")])
        delays.append((child.attrib["name"], curr_delay))
        total_delay += curr_delay

threshold = total_delay * TIME_PERC
#delays = [(name, int(name[1:name.index("_")]) * delay) for name, delay in delays]
delays = sorted(delays, key=lambda p: p[1], reverse=True)

os.makedirs(IMG_DIR, exist_ok=True)
gen_accum_perc_plot(delays, total_delay, out_dir=os.path.join(IMG_DIR, "accum_perc.png"))
gen_ind_delays_plot(delays, out_dir=os.path.join(IMG_DIR, "ind_delays.png"))

print("Total:", total_delay, "s")
print("Higher to lower:", delays)

cont = 0

for i, (atomic, delay) in enumerate(delays):
    cont += delay

    if cont > threshold:
        print("Number of atomics to exceed %.2f threshold: %d/%d" % (TIME_PERC, i+1, len(delays)))
        break
