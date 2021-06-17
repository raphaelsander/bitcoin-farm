#!/usr/bin/python3

from threading import Thread
from random import randint
from time import ctime
from bitcoin import *
from os import mkdir
import requests
import urllib3
import json


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

total = 0

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


def generate_addresses():
    addresses = []

    for address in range(0, 128):
        random_wallet = str(randint(0, 115792089237316195423570985008687907852837564279074904382605163141518161494337))
        wallet = [sha256(random_wallet), pubtoaddr(privtopub(sha256(random_wallet)))]
        addresses.append(wallet)

    return addresses


def create_url(addresses):
    public_keys = ""

    for i in range(0, 128):
        public_keys += addresses[i][1]

        if i < 127:
            public_keys += "|"

    url = "https://blockchain.info/balance?active=" + public_keys
    return url


class Th(Thread):
    def __init__(self, num):
        Thread.__init__(self)
        self.num = num

    def run(self):
        global total

        while True:
            try:
                addresses = generate_addresses()
                url = create_url(addresses)

                req2 = requests.get(url)
                if req2.status_code == 200:
                    content2 = req2.content

                    addresses2 = json.loads(content2.decode("utf-8"))
                    for xy in addresses2:
                        if addresses2['%s' % xy]['final_balance'] != 0:
                            for xyz in range(0, 128):
                                if addresses[xyz][1] == xy:
                                    output = ("PublicKey:%s Balance:%s PrivateKey:%s" % (
                                        xy, addresses2['%s' % xy]['final_balance'], addresses[xyz][0]))
                                    print(output)
                                    write_logs("keys", output)
                        if addresses2['%s' % xy]['total_received'] != 0:
                            for xyz in range(0, 128):
                                if addresses[xyz][1] == xy:
                                    output = ("PublicKey:%s Received:%s PrivateKey:%s" % (
                                        xy, addresses2['%s' % xy]['total_received'], addresses[xyz][0]))
                                    print(output)
                                    write_logs("keys", output)
                    total += 128

                else:
                    print("Error - %s" % url)

            except TimeoutError:
                output = ("%s - ERROR - TimeoutError - URL: %s" % (ctime(), url))
                print(output)
                write_logs("error", output)


for x in range(0, 4):
    a = Th(x)
    a.start()

while True:
    time.sleep(10)
    print("%s - INFO - Total verified: %s" % (ctime(), total))
