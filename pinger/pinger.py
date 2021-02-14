#!/usr/bin/python3
# fping -C 100 --ipv4 --count=3 -a -i 0 8.8.8.8
# 23 января 2021

import subprocess
import json
import redis
import time
import re
from collections import Counter
from queue import Queue
from threading import Thread
from datetime import datetime
import ipaddress

start_time = datetime.now()
length = 32
r = redis.Redis(db=3)
r.flushdb()         # Зачистить базу REDIS
num_threads = 500   # Количество потоков
queue = Queue()     #


def from_block(net):
    subnet = ipaddress.ip_network(net)
    return subnet


def from_file():
    ips = ""
    try:
        ips = open('list.lst').readlines()          # Получить ip адреса из файла
        for n in range(len(ips)):
            ips[n] = ips[n].replace("\n", "")
    except Exception as e:
        print("нет файла")
    return ips


def pinger(i, q):

    while True:
        ip = q.get()
        p = subprocess.Popen("fping -C 3 -b {} -q {}".format(length, ip),
                             shell=True, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT)
        data = p.communicate()[0].decode('utf8').strip()            # тут строка
        substr = re.findall(r'(\S+)\s+:\s+([0-9.\s\-]+)', data)[0]  # тут кортеж

        if substr is not None:
            stamp = int(time.time())
            p_status = judge(substr[1])
            dira = {"ip": substr[0], "sourse": substr[1].rstrip(), "timestamp": stamp, "status": p_status}
            vl = json.dumps(dira)
            r.set(substr[0], vl)                    # результат в редис
        q.task_done()                               # Завершили пинговать


def judge(fping):
    """
    :param fping:   список ответов от хоста
    :return:        0 - всё хорошо, 1 - не пигуется, 2 - потери пакетов, 3 - большая задержка
    """
    sp = fping.split()
    summa = 0
    fail = 0
    for l in sp:
        try:
            if l == "-":
                fail += 1
            summa += float(l)
        except ValueError:
            pass
    ret = 0
    if fail in [1, 2]: ret = 2  # - потери пакетов"
    if fail in [3]: ret = 1     # - не пингуется"
    if summa >= 1000: ret = 3   # - большая задержка
    return ret


def thread(ips):

    for i in range(num_threads):
        worker = Thread(target=pinger, args=(i, queue))
        worker.setDaemon(True)
        worker.start()
    print("=======================================")
    for ip in ips:
        # print("IP", ip)
        queue.put(ip)
    # print(queue)
    queue.join()


if __name__ == "__main__":

    ips = from_block('212.220.0.0/20')
    thread(ips)
    count_all = 0
    count_act_ip = 0
    losses = []     # список плохопингующихся хостов
    active = []     # список доступных хостов
    stupped = []    # список недоступных хостов
    count_loss = 0
    unavailable = 0
    for pp in r.keys():
        read_dict = json.loads(r.get(pp).decode())
        count_all += 1
        if read_dict['status'] == 2:
            # losses.append(read_dict)
            count_loss += 1

        if read_dict['status'] == 0:
            # active.append(read_dict)
            # print(read_dict['ip'], read_dict['status'])
            count_act_ip += 1

        if read_dict['status'] == 1:
            # stupped.append(read_dict)
            unavailable += 1

    end_time = datetime.now()
    print('{}\n Count:{}\n Act:{}\n Loss:{}\n Unavailable:{}\n Duration:{}\n'
          .format(ips, count_all, count_act_ip, count_loss, unavailable, (end_time - start_time)))
