#!/usr/bin/python3
# SPDX-License-Identifier: BSD-3-Clause
# Copyright(c) 2010-2014 Intel Corporation
# Copyright(c) 2017 Cavium, Inc. All rights reserved.
# Copyright(c) 2024 Lazaros Koromilas

# Outputs a snaphot of running tasks on the CPU layout.
#
# The script takes as arguments a list of program names,
# and it presents the result in a formatted table.
# Sibling CPUs are displayed one next to the other.
# Isolated CPUs are annotated with an asterisk.

import os
import sys
from tabulate import tabulate, SEPARATING_LINE


def get_pids(program):
    """Collects all process identifiers for programs of name
    """
    pids = []
    for pid in os.listdir("/proc"):
        try:
            fd = open("/proc/{}/comm".format(pid))
        except IOError:
            continue
        name = fd.read().strip()
        fd.close()
        if name == program:
            pids.append(int(pid))
    return pids


def expand_range_list(str):
    """Converts a list of integer ranges string to list of numbers

    >>> expand_range_list("5,1-3")
    [5, 1, 2, 3]
    >>> expand_range_list("4")
    [4]
    >>> expand_range_list("")
    []
    """
    if not str:
        return []
    expanded = []
    for member in str.split(","):
        edges = member.split("-")
        if len(edges) == 1:
            item = int(edges[0])
            expanded.append(item)
        if len(edges) == 2:
            left, right = edges
            for item in range(int(left), int(right) + 1):
                expanded.append(item)
    return expanded


programs = sys.argv[1:]
program_pid_list = []
for program in programs:
    for pid in get_pids(program):
        program_pid_list.append((program, pid))

task_map = {}
for program, pid in program_pid_list:
    for tid in os.listdir("/proc/{}/task".format(pid)):
        try:
            fd = open("/proc/{}/task/{}/comm".format(pid, tid))
        except IOError:
            continue
        task = fd.read().strip()
        fd.close()
        name = "{}:{}".format(program, task)
        fd = open("/proc/{}/task/{}/stat".format(pid, tid))
        cpu = int(fd.read().split(" ")[38])
        fd.close()
        if cpu in task_map:
            task_map[cpu].append(name)
        else:
            task_map[cpu] = [name]

sockets = []
cores = []
core_map = {}
base_path = "/sys/devices/system/cpu"
fd = open("{}/kernel_max".format(base_path))
max_cpus = int(fd.read())
fd.close()
for cpu in range(max_cpus + 1):
    try:
        fd = open("{}/cpu{}/topology/core_id".format(base_path, cpu))
    except IOError:
        continue
    core = int(fd.read())
    fd.close()
    fd = open("{}/cpu{}/topology/physical_package_id".format(base_path, cpu))
    socket = int(fd.read())
    fd.close()
    if core not in cores:
        cores.append(core)
    if socket not in sockets:
        sockets.append(socket)
    key = (socket, core)
    if key not in core_map:
        core_map[key] = []
    core_map[key].append(cpu)

fd = open("{}/isolated".format(base_path))
isolated = expand_range_list(fd.read().strip())
fd.close()

headers = ['Socket', 'Core']
colalign = ("right", "right")
cpus = core_map[(0, 0)]
for cpu in cpus:
    headers += ('CPU', 'Tasks')
    colalign += ("right", "left")
table = []
for s in sorted(sockets):
    for c in sorted(cores):
        if (s, c) not in core_map:
            continue
        cpus = core_map[(s, c)]
        if not cpus:
            continue
        row = [s, c]
        for cpu in cpus:
            tasks = task_map.get(cpu) or []
            tasks = sorted(tasks, key=str.lower)
            if cpu in isolated:
                row.append("*{}".format(cpu))
            else:
                row.append("{}".format(cpu))
            row.append('\n'.join(tasks))
        table.append(row)
    table.append(SEPARATING_LINE)
print(tabulate(table, headers, colalign=colalign, tablefmt="simple"))
