#!/usr/bin/python3

from bs4 import BeautifulSoup
from threading import Thread
from random import randint
from time import ctime
from os import mkdir
import requests
import urllib3
import json


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    mkdir("logs")
    print("%s - INFO - The directory logs created" % ctime())

except FileExistsError:
    print("%s - INFO - The directory logs exist" % ctime())


def write_logs(file, output):
    if file == "error":
        f = open("logs/error.txt", "a")
    elif file == "keys":
        f = open("logs/keys.txt", "a")
    else:
        print("%s - ERROR - Log file don't found: %s" % (ctime(), file))
        return

    output = output + "\n"
    f.write(output)
    f.close()


class Th(Thread):
    def __init__(self, num):
        Thread.__init__(self)
        self.num = num

    def run(self):
        while True:
            page = randint(0, 904625697166532776746648320380374280100293470930272690489102837043110636675)
            try:
                req = requests.get("https://lbc.cryptoguru.org/dio/%s" % page, verify=False)
                if req.status_code == 200:
                    print("%s - Page: %s" % (ctime(), page))
                    content = req.content
                    soup = BeautifulSoup(content, 'html.parser')
                    all_span = soup.find_all(name='span')
                    list_addresses = []
                    for x in all_span:
                        list_addresses.append(x.get_text().split())

                    y = json.dumps(list_addresses)

                    addresses = ""
                    for x in range(0, 256, 2):
                        addresses += str(list_addresses[x][2])

                        if x < 254:
                            addresses += "|"

                    req2 = requests.get("https://blockchain.info/balance?active=%s" % addresses)
                    content2 = req2.content

                    addresses2 = json.loads(content2.decode("utf-8"))
                    for xy in addresses2:
                        if addresses2['%s' % xy]['final_balance'] != 0:
                            for xyz in range(0, 256, 2):
                                if list_addresses[xyz][2] == xy:
                                    output = ("PublicKey:%s Balance:%s PrivateKey:%s" % (
                                        xy, addresses2['%s' % xy]['final_balance'], list_addresses[xyz][1]))
                                    print(output)
                                    write_logs("keys", output)
                        if addresses2['%s' % xy]['total_received'] != 0:
                            for xyz in range(0, 256, 2):
                                if list_addresses[xyz][2] == xy:
                                    output = ("PublicKey:%s Received:%s PrivateKey:%s" % (
                                        xy, addresses2['%s' % xy]['total_received'], list_addresses[xyz][1]))
                                    print(output)
                                    write_logs("keys", output)
                else:
                    output = ("%s - ERROR - Request Code: %s - Page: %s" % (ctime(), req.status_code, page))
                    print(output)
                    write_logs("error", output)

            except TimeoutError:
                output = ("%s - ERROR - TimeoutError - Page: %s" % (ctime(), page))
                print(output)
                write_logs("error", output)


# If you increase the range, maybe you get the request error 503
for x in range(0, 1):
    a = Th(x)
    a.start()
