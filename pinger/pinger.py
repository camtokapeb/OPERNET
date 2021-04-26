#!/usr/bin/python3
# fping -C 100 --ipv4 --count=3 -a -i 0 8.8.8.8
# 23 января 2021

import subprocess
import json
import redis
import time
import re
# from collections import Counter
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


def from_file(file):
    """
    Получение списка ip адресов из файла
    :param file:  имя файла
    :return: список ip адресов
    """
    list_ip_address = []
    try:
        list_ip_address = open(file).readlines()
        for n in range(len(list_ip_address)):
            list_ip_address[n] = list_ip_address[n].replace("\n", "")
    except FileNotFoundError as e:
        print(f"нет файла {file}_{e}")
    return list_ip_address


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
            dira = {"ip": substr[0], "delays": substr[1].rstrip(), "timestamp": stamp, "status": p_status}
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
    for _ in sp:
        try:
            if _ == "-":
                fail += 1
            summa += float(_)
        except ValueError:
            pass
    ret = 0
    if fail in [1, 2]:
        ret = 2     # - потери пакетов"
    if fail in [3]:
        ret = 1     # - не пингуется"
    if summa >= 100:
        ret = 3     # - большая задержка
    return ret


def thread(ip_s):

    for i in range(num_threads):
        worker = Thread(target=pinger, args=(i, queue))
        worker.setDaemon(True)
        worker.start()
    print("=========== ЗАПУСК ПОТОКОВ ===============")
    for ip in ip_s:
        # print("IP", ip)
        queue.put(ip)
    # print(queue)
    queue.join()


def prepare_result():
    result = {}

    losses = []     # список плохопингующихся хостов
    active = []     # список доступных хостов
    stupped = []    # список недоступных хостов

    count_all = 0
    act_ip = 0
    loss = 0            # счётчик плохопингующихся хостов
    unavailable = 0     # счётчик недоступных хостов
    bigdelay = 0        # счётчик долгоотвечающих хостов

    for pp in r.keys():
        read_dict = json.loads(r.get(pp).decode())
       # print(read_dict)
        count_all += 1
        if read_dict['status'] == 2:
            # losses.append(read_dict)
            loss += 1

        if read_dict['status'] == 0:
            # active.append(read_dict)
            # print(read_dict['ip'], read_dict['status'])
            act_ip += 1

        if read_dict['status'] == 1:
            # stupped.append(read_dict)
            unavailable += 1

        if read_dict['status'] == 3:
            # stupped.append(read_dict)
            bigdelay += 1
    return {"all": count_all, "loss": loss, "act": act_ip, "unavailable": unavailable, "bigdelay": bigdelay}

if __name__ == "__main__":

    # ips = from_block('212.220.0.0/20')
    ips = from_block('195.19.0.0/16')
    #ips = from_file('list.lst')
    # print(type(ips), ips)
    thread(ips)
    end_time = datetime.now()
    _ = prepare_result()

    print('Count:{}\n Act:{}\n Loss:{}\n BigDelay:{}\n Unavailable:{}\n Duration:{}\n'
          .format(_["all"], _["act"], _["loss"], _["bigdelay"], _["unavailable"], (end_time - start_time)))
    print("================ FINITA =================")